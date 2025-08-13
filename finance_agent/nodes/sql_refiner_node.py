# finance_agent/nodes/sql_refiner_node.py
"""
SQL Refiner Node
Refines SQL queries when they fail (max 3 attempts)
"""

from typing import Dict
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import re
from finance_agent.database import DatabaseManager
from finance_agent.llm import LLM
from finance_agent.prompts import sql_refinement_prompt as prompt


class SqlRefinerNode:
    def __init__(self):
        self.llm = LLM()
        self.db_manager = DatabaseManager()
    
    def process(self, state: Dict) -> Dict:
        if state["sql_attempts"] >= 3:
            state["final_output"] = "쿼리 실행에 실패했습니다."
            state["is_complete"] = True
            return state
        
        original_query = state["sql_query"]
        error_message = state["sql_error"]
        user_query = state["user_query"]
           
        try:
            latest_date = self._get_latest_available_date()
            response = self.llm.run(prompt.format(
                user_query=user_query,
                original_query=original_query,
                error=error_message,
                latest_date=latest_date
            ))
            
            refined_query = self._parse_sql(response)
            state["sql_query"] = refined_query
            state["sql_attempts"] += 1
            
            # Execute refined query
            try:
                results = self.db_manager.execute_query(refined_query)
                state["query_results"] = results
                state["sql_error"] = ""
            except Exception as e:
                state["sql_error"] = str(e)
                state["query_results"] = []
                
        except Exception as e:
            state["sql_error"] = f"SQL 수정 오류: {str(e)}"
        
        return state
    
    def _parse_sql(self, sql_text: str) -> str:
        # '''sql, ```sql, ``` 등 다양한 포맷 모두 제거
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