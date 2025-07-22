"""
SQL Generator Node
# SQL 생성
"""

from typing import Dict
from langchain_core.prompts import ChatPromptTemplate
import re
from finance_agent.database import DatabaseManager
from finance_agent.llm import LLM
from finance_agent.prompts import sql_generation_prompt as prompt


class SqlGeneratorNode:
    """Node for generating SQL queries"""
    
    def __init__(self):
        self.llm = LLM()
        self.db_manager = DatabaseManager()
    
    def process(self, state: Dict) -> Dict:
        """Generate SQL query from user input"""
        user_query = state["user_query"]
        parsed_query = state.get("parsed_query", {})
        company_name = parsed_query.get("company_name", "")
        ticker = parsed_query.get("ticker", "")
        market = parsed_query.get("market", "")
        print(f"parsed_query: {parsed_query}")  # 디버깅용

        latest_date = self._get_latest_available_date()
        
        try:
            prompt_text = prompt.format(user_query=user_query, latest_date=latest_date, company_name=company_name, ticker=ticker, market=market)
            llm_content = self.llm.run(prompt_text)
            sql_query = self._parse_sql(llm_content)
            state["sql_query"] = sql_query
            state["sql_attempts"] = 1
            
            # Execute query
            try:
                results = self.db_manager.execute_query(sql_query)
                state["query_results"] = results
                state["sql_error"] = ""
            except Exception as e:
                state["sql_error"] = str(e)
                state["query_results"] = []
        except Exception as e:
            state["sql_error"] = f"SQL 생성 오류: {str(e)}"
            state["sql_query"] = ""
            state["query_results"] = []
        
        return state
    
    def _parse_sql(self, sql_text: str) -> str:
        """parse SQL query text"""
        # '''sql, ```sql, ``` 등 다양한 포맷 모두 제거
        sql_query = sql_text.strip()
        sql_query = re.sub(r"(```sql|'''sql)", "", sql_query, flags=re.IGNORECASE)
        sql_query = re.sub(r"(```|''')", "", sql_query)
        return sql_query.strip()
    
    def _get_latest_available_date(self) -> str:
        """Get latest available date from database"""
        try:
            dates = self.db_manager.get_available_dates(1)
            return dates[0] if dates else "2025-07-09"
        except Exception:
            return "2025-07-09"