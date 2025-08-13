import pandas as pd
from typing import Dict, Optional
import re, json
from finance_agent.llm import LLM
from finance_agent.prompts import query_parser_prompt as prompt
from finance_agent.utils import is_url, is_today_related, extract_date, extract_keywords
import datetime

class QueryParserNode:
    def __init__(self):
        self.llm = LLM()
        self.company_df = pd.read_csv("./data/krx_tickers.csv")

    def get_day_label(self, date: datetime.datetime) -> str:
        # 0=월 ... 6=일
        if date.weekday() == 5:
            return "토요일"
        elif date.weekday() == 6:
            return "일요일"
        else:
            return "평일"

    def classify_intent(self, query: str) -> str:
        # ✅ 우선순위: URL → "핫한" → 오늘 관련 → 일반 뉴스/요약
        if is_url(query):
            return "url_summary_request"
        if "핫한" in query:
            return "hot_news_request"
        if is_today_related(query):
            return "today_news_request"
        if any(k in query for k in ["뉴스", "요약"]):
            return "news_summary_request"
        return "not_summary"
    
    def lookup_ticker(self, company_name: str) -> Optional[str]:
        company_name = (company_name or "").strip()
        row = self.company_df[self.company_df['company_name'] == company_name]
        return row['ticker'].values[0] if not row.empty else None

    def process(self, state: Dict) -> Dict:
        state["needs_user_input"] = False
        user_query = state.get("user_query", "")
        intent = self.classify_intent(user_query)
        print(f"[DEBUG:QueryParserNode] User query: {user_query}, Intent: {intent}")

        # 1) URL 요약
        if intent == "url_summary_request":
            url_match = re.search(r'https?://[^\s]+', user_query)
            url = url_match.group(0) if url_match else ""
            print(f"[DEBUG:QueryParserNode] Extracted URL: {url}")
            state["parsed_query"] = {
                "intent": intent,
                "date": None,               # URL엔 날짜 불필요
                "keywords": [url],          # 원본 URL 그대로
                "company_name": "",
                "market": ""
            }
            return state

        # 2) 오늘 뉴스
        if intent == "today_news_request":
            keywords = extract_keywords(user_query)
            date = datetime.datetime.now().strftime("%Y-%m-%d")
            print(f"[DEBUG:QueryParserNode] Extracted date: {date}, Keywords: {keywords}")
            state["parsed_query"] = {
                "intent": intent,
                "date": date,
                "keywords": keywords,
                "company_name": "",
                "market": ""
            }
            return state
        
        # 3) 핫뉴스 — ✅ 날짜/키워드 파싱하지 않음
        if intent == "hot_news_request":
            print("[DEBUG:QueryParserNode] Hot news: skip date/keywords extraction")
            state["parsed_query"] = {
                "intent": intent,
                "date": None,
                "keywords": [],             # 키워드는 NewsHandler가 제시
                "company_name": "",
                "market": ""
            }
            return state

        # 4) 일반 뉴스/요약 — 날짜/키워드 파싱 유지
        if intent == "news_summary_request":
            date = extract_date(user_query)
            raw_keywords = extract_keywords(user_query)
            # 날짜 토큰 제거
            keywords = [
                kw for kw in raw_keywords
                if not re.fullmatch(
                    r'(\d{1,2}\s*[월])|(\d{1,2}\s*일)|'
                    r'\d{4}\s*[./년-]?\s*\d{1,2}\s*[./월-]?\s*\d{1,2}\s*일?|'
                    r'\d{4}\s*[./년-]?\s*\d{1,2}\s*[월]?|'
                    r'\d{1,2}\s*[월./-]?\s*\d{1,2}\s*일?',
                    kw
                )
            ]
            print(f"[DEBUG:QueryParserNode] Extracted date: {date}, Keywords: {keywords}")
            state["parsed_query"] = {
                "intent": intent,
                "date": date,
                "keywords": keywords,
                "company_name": "",
                "market": ""
            }
            return state

        # 5) 그 외 — LLM 기반 파싱
        try:
            response = self.llm.run(prompt.format(user_query=user_query))
            parsed = self._parse_json(response)

            date_str = parsed.get("date")
            date_obj = None
            date_day = None
            if isinstance(date_str, str) and date_str:
                try:
                    date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                    date_day = self.get_day_label(date_obj)
                except ValueError:
                    pass

            company_name = parsed.get("company_name")
            ticker = self.lookup_ticker(company_name) if company_name else None

            state["parsed_query"] = {
                "company_name": company_name,
                "ticker": ticker,
                "date": date_obj.strftime("%Y-%m-%d") if date_obj else None,
                "date_day": date_day,
                "market": parsed.get("market", "")
            }
            # 주말 휴장 안내 (date가 있을 때만)
            if date_obj and date_day in {"토요일", "일요일"}:
                state["final_output"] = f"{date_obj.strftime('%Y-%m-%d')}는 {date_day}로 휴장일입니다."
                state["is_complete"] = True
                state["needs_user_input"] = False
                    
        except Exception as e:
            print(f"[QueryParserNode] Parsing error: {e}")
            state["parsed_query"] = {
                "company_name": None,
                "ticker": None,
                "date": None,
                "date_day": None,
                "market": ""
            }
        return state

    def _parse_json(self, response: str) -> Dict:
        """Extract JSON from LLM response"""
        try:
            match = re.search(r"```json\s*(.*?)```", response, re.DOTALL)
            if not match:
                raise ValueError("No JSON block found")
            json_str = match.group(1).strip()
            return json.loads(json_str)
        except (ValueError, json.JSONDecodeError) as e:
            print(f"JSON parsing error: {e}")
            return {}
