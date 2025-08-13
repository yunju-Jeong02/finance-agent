# finance_agent/nodes/sql_generator_node.py
from typing import Dict
from langchain_core.prompts import ChatPromptTemplate
import re
from finance_agent.database import DatabaseManager
from finance_agent.llm import LLM
from finance_agent.prompts import sql_generation_prompt as prompt


class SqlGeneratorNode:    
    def __init__(self):
        self.llm = LLM()
        self.db_manager = DatabaseManager()
    
    def process(self, state: Dict) -> Dict:
        user_query = state["user_query"]
        parsed_query = state.get("parsed_query", {})
        ticker = parsed_query.get("ticker", "")
        market = parsed_query.get("market", "")

        ticker_hint = f"ticker = '{ticker}'" if ticker else ""
        market_hint = (
            "ticker LIKE '%.KS'" if market == "KOSPI"
            else "ticker LIKE '%.KQ'" if market == "KOSDAQ"
            else ""
        )

        latest_date = self._get_latest_available_date()
        
        try:
            prompt_text = prompt.format(
                user_query=user_query,
                latest_date=latest_date,
                ticker_hint=ticker_hint,
                market_hint=market_hint
            )
            llm_response = self.llm.run(prompt_text)
            sql_query = self._parse_sql(llm_response)

            # print(f"[SQL Generation] LLM response: {llm_response}")  # 디버깅용

            # 약간의 하드코딩..
            if ticker_hint:
                if not self._ticker_hint_exists(sql_query, ticker_hint):
                    # 한글 ticker가 있다면 교체
                    sql_query = self._replace_korean_ticker(sql_query, ticker_hint) 
                # 여전히 ticker 조건이 없다면 삽입
                if not self._ticker_hint_exists(sql_query, ticker_hint):
                    sql_query = self._ensure_ticker_filter(sql_query, ticker_hint)
            
            state["sql_query"] = sql_query
            state["sql_attempts"] = 1

            try:
                results = self.db_manager.execute_query(sql_query)
                state["query_results"] = results
                state["sql_error"] = ""
            except Exception as e:
                state["query_results"] = []
                state["sql_error"] = str(e)

        except Exception as e:
            state["sql_query"] = ""
            state["query_results"] = []
            state["sql_error"] = f"SQL 생성 오류: {str(e)}"

        return state

    def _parse_sql(self, sql_text: str) -> str:
        """Clean markdown/codeblock from SQL"""
        sql_query = sql_text.strip()
        sql_query = re.sub(r"(```sql|'''sql)", "", sql_query, flags=re.IGNORECASE)
        sql_query = re.sub(r"(```|''')", "", sql_query)
        return sql_query.strip()

    def _get_latest_available_date(self) -> str:
        try:
            dates = self.db_manager.get_available_dates(1)
            return dates[0] if dates else "2025-07-09"
        except Exception:
            return "2025-07-09"
        
    def _ticker_hint_exists(self, sql_query: str, ticker_hint: str) -> bool:
        """
        ticker 조건이 SQL 쿼리에 이미 존재하는지 확인
        """
        normalized_sql = re.sub(r"\s+", " ", sql_query).lower()
        normalized_hint = ticker_hint.lower()
        return normalized_hint in normalized_sql

    def _replace_korean_ticker(self, sql_query: str, ticker_hint: str) -> str:
        # 패턴: ticker = '현대사료' → ticker = '016790.KQ'
        sql_query = re.sub(r"ticker\s*=\s*['\"][가-힣]+['\"]", ticker_hint, sql_query)
        return sql_query
    
    def _ensure_ticker_filter(self, sql_query: str, ticker_hint: str) -> str:
        if ticker_hint and ticker_hint not in sql_query:
            # ticker LIKE 가 있는 경우 AND로 ticker = ... 추가
            if "ticker LIKE" in sql_query:
                sql_query = re.sub(
                    r"(WHERE\s+.*?ticker\s+LIKE\s+'[^']+')",
                    rf"\1 AND {ticker_hint}",
                    sql_query,
                    flags=re.IGNORECASE | re.DOTALL
                )
            else:
                # ticker 조건 자체가 없으면 그냥 WHERE 뒤에 추가
                sql_query = re.sub(
                    r"(WHERE\s+)",
                    rf"\1{ticker_hint} AND ",
                    sql_query,
                    flags=re.IGNORECASE
                )
        return sql_query