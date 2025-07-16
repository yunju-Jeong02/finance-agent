"""
SQL Refiner Node
Refines SQL queries when they fail (max 3 attempts)
"""

from typing import Dict
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import re
from config.config import Config
from finance_agent.database import DatabaseManager
from finance_agent.llm import LLM
from finance_agent.prompts import sql_refinement_prompt as prompt


class SqlRefinerNode:
    """Node for refining SQL queries"""
    
    def __init__(self):
        self.config = Config()
        self.llm = LLM()
        self.db_manager = DatabaseManager()
    
    def process(self, state: Dict) -> Dict:
        """Refine SQL query if there was an error"""
        if state["sql_attempts"] >= 3:
            state["final_output"] = "쿼리 실행에 실패했습니다."
            state["is_complete"] = True
            return state
        
        original_query = state["sql_query"]
        error_message = state["sql_error"]
        user_query = state["user_query"]
           
        try:
            response = self.llm.invoke(prompt.format(
                user_query=user_query,
                original_query=original_query,
                error=error_message
            ))
            
            refined_query = self._clean_sql(response.content)
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
    
    def _clean_sql(self, sql_text: str) -> str:
        """Clean SQL query text"""
        # '''sql, ```sql, ``` 등 다양한 포맷 모두 제거
        sql_query = sql_text.strip()
        sql_query = re.sub(r"(```sql|'''sql)", "", sql_query, flags=re.IGNORECASE)
        sql_query = re.sub(r"(```|''')", "", sql_query)
        return sql_query.strip()