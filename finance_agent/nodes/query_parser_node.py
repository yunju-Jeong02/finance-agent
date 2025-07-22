import pandas as pd
from typing import Dict
from finance_agent.llm import LLM
from finance_agent.prompts import query_parser_prompt as prompt
from finance_agent.parsers import extract_json_from_response
import datetime

class QueryParserNode:
    def __init__(self):
        self.llm = LLM()
        self.company_df = pd.read_csv("./data/stock/krx_tickers.csv")

    def get_day_label(self, date: datetime.datetime) -> str:
        if date.weekday() == 5:
            return "토요일"
        elif date.weekday() == 6:
            return "일요일"
        else:
            return "평일"
        # todo: 공휴일 로직 추가 (예: KRX API 또는 local holiday DB)

    def lookup_ticker(self, company_name: str) -> str:
        company_name = company_name.strip()
        ticker_row = self.company_df[self.company_df['회사명'] == company_name]
        return ticker_row['ticker'].values[0] if not ticker_row.empty else None

    def process(self, state: Dict) -> Dict:
        user_query = state.get("user_query", "")
        try:
            response = self.llm.run(prompt.format(user_query=user_query))
            parsed = extract_json_from_response(response)

            # 날짜 파싱 및 요일 판별
            date_str = parsed.get("date")
            date, date_day = None, None
            if date_str:
                try:
                    date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                    date_day = self.get_day_label(date)
                except ValueError:
                    print(f"Invalid date format: {date_str}")

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