import re, json, pymysql
import pandas as pd
from datetime import datetime
from typing import Dict
from config.config import Config
from finance_agent.llm import LLM
from finance_agent.utils import is_url, is_today_related, extract_date, extract_keywords
from finance_agent.prompts import query_parser_prompt as prompt


class QueryParserNode:
    def __init__(self):
        self.llm = LLM()
        self.company_df = self._load_krx_tickers()
        self._clova_host = Config.CLOVA_HOST
        self._api_key = Config.CLOVA_API_KEY
        self._hyperclova_host = "https://" + Config.CLOVA_HOST
        self._model_endpoint = "/v3/chat-completions/HCX-005"

    def _load_krx_tickers(self) -> pd.DataFrame:
        try:
            conn = pymysql.connect(
                host=Config.MYSQL_HOST, user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD, database=Config.MYSQL_DATABASE,
                port=Config.MYSQL_PORT, charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            df = pd.read_sql("SELECT 회사명, ticker FROM krx_tickers", conn)
            conn.close()
            return df
        except:
            return pd.DataFrame(columns=["회사명", "ticker"])

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

    def lookup_ticker(self, name: str) -> str:
        row = self.company_df[self.company_df["회사명"] == name.strip()]
        return row["ticker"].values[0] if not row.empty else None

    def process(self, state: Dict) -> Dict:
        query = state.get("user_query", "")
        intent = self.classify_intent(query)
        print(f"[DEBUG:QueryParserNode] User query: {query}, Intent: {intent}")

        if intent != "not_summary":
            # 날짜 추출
            date = datetime.now().strftime("%Y-%m-%d") if intent == "today_news_request" else extract_date(query)

            # 키워드 추출 + 날짜 문자열 제거
            raw_keywords = extract_keywords(query)
            keywords = [
                kw for kw in raw_keywords
                if not re.search(
                    r'(\d{4}[-./년\s]?\d{1,2}([-./월\s]?\d{1,2})?)'  # 연도 포함
                    r'|(\d{1,2}[-./월\s]?\d{1,2}일?)',               # 월-일
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

        # ----------- 주식 데이터 질의 -----------
        try:
            response = self.llm.run(prompt.format(user_query=query))
            parsed = self._parse_json(response)
            date_str = parsed.get("date")
            date = None
            if date_str:
                try:
                    date = datetime.strptime(date_str, "%Y-%m-%d")
                except:
                    date = None

            company = parsed.get("company_name")
            ticker = self.lookup_ticker(company) if company else None
            state["parsed_query"] = {
                "intent": "stock_query",
                "company_name": company,
                "ticker": ticker,
                "date": date.strftime("%Y-%m-%d") if date else None,
                "market": parsed.get("market", "")
            }
        except:
            state["parsed_query"] = {"intent": "unknown"}
        return state

    def _parse_json(self, text: str) -> Dict:
        try:
            match = re.search(r"```json\s*(.*?)```", text, re.DOTALL)
            return json.loads(match.group(1).strip()) if match else {}
        except:
            return {}