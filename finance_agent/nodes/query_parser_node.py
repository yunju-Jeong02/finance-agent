import pandas as pd
from typing import Dict
import re, json
from finance_agent.llm import LLM
from finance_agent.prompts import query_parser_prompt as prompt
from finance_agent.utils import is_url, is_today_related, extract_date, extract_keywords
import datetime
import pymysql
import pandas as pd
from config.config import Config


class QueryParserNode:
    def __init__(self):
        self.llm = LLM()
        self.company_df = pd.read_csv("./data/krx_tickers.csv")

    def get_day_label(self, date: datetime.datetime) -> str:
        if date.weekday() == 5:
            return "토요일"
        elif date.weekday() == 6:
            return "일요일"
        else:
            return "평일"
        # todo: 공휴일 로직 추가 (예: KRX API 또는 local holiday DB)

    def classify_intent(self, query: str) -> str:
        if is_url(query):
            return "url_summary_request"
        if is_today_related(query):
            return "today_news_request"
        if "핫한" in query:
            return "hot_news_request"
        if any(k in query for k in ["뉴스", "요약"]):
            return "news_summary_request"
        return "not_summary"
    
    def lookup_ticker(self, company_name: str) -> str:
        company_name = company_name.strip()
        ticker_row = self.company_df[self.company_df['company_name'] == company_name]
        return ticker_row['ticker'].values[0] if not ticker_row.empty else None

    def process(self, state: Dict) -> Dict:
        state["needs_user_input"] = False
        user_query = state.get("user_query", "")
        intent = self.classify_intent(user_query)
        print(f"[DEBUG:QueryParserNode] User query: {user_query}, Intent: {intent}")

        if intent != "not_summary":
            # 날짜 추출
            date = datetime.now().strftime("%Y-%m-%d") if intent == "today_news_request" else extract_date(user_query)

            # 키워드 추출 + 날짜 문자열 제거
            raw_keywords = extract_keywords(user_query)
            keywords = [
                kw for kw in raw_keywords
                if not re.fullmatch(
                    r'(\d{1,2}\s*[월])|(\d{1,2}\s*일)|'
                    r'\d{4}\s*[./년-]?\s*\d{1,2}\s*[./월-]?\s*\d{1,2}\s*일?|'  # YYYY-MM-DD
                    r'\d{4}\s*[./년-]?\s*\d{1,2}\s*[월]?|'                     # YYYY-MM
                    r'\d{1,2}\s*[월./-]?\s*\d{1,2}\s*일?',                     # MM-DD
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
        try:
            response = self.llm.run(prompt.format(user_query=user_query))
            parsed = self._parse_json(response)
            # print(f"[QueryParserNode] Parsed response: {parsed}")  # 디버깅용

            # 날짜 파싱 및 요일 판별
            date_str = parsed.get("date")
            if isinstance(date_str, str):
                date, date_day = None, None
                if date_str:
                    try:
                        date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                        date_day = self.get_day_label(date)
                    except ValueError:
                        # print(f"Invalid date format: {date_str}")
                        date = None
                        date_day = None
            else:
                date, date_day = None, None

            # 회사명 및 티커 추출
            company_name = parsed.get("company_name")
            ticker = self.lookup_ticker(company_name) if company_name else None

            # 파싱된 결과 저장
            state["parsed_query"] = {
                "company_name": company_name,
                "ticker": ticker,
                "date": date.strftime("%Y-%m-%d") if date else None,
                "date_day": date_day,
                "market": parsed.get("market", "")
            }
            if date_day in {"토요일", "일요일"}:
                state["final_output"] = f"{date.strftime('%Y-%m-%d')}는 {date_day}로 휴장일입니다."
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
        