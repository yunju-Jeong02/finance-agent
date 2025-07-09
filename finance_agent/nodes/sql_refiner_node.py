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


class SqlRefinerNode:
    """Node for refining SQL queries"""
    
    def __init__(self):
        self.config = Config()
        self.llm = ChatOpenAI(
            temperature=0.1,
            model="gpt-4o-mini",
            openai_api_key=self.config.OPENAI_API_KEY
        )
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
        
        prompt = ChatPromptTemplate.from_template("""
        다음 SQL 쿼리에서 오류가 발생했습니다. 오류를 수정해주세요.
        
        원래 질문: {user_query}
        오류 쿼리: {original_query}
        오류 메시지: {error}
        
        수정 규칙:
        1. krx_stockprice 테이블 사용
        2. 컬럼명 확인: Date, Close, Volume, company_name, ticker, price_change_pct
        3. KOSPI: ticker LIKE '%.KS'
        4. KOSDAQ: ticker LIKE '%.KQ'
        5. 문법 오류 수정
        
        수정된 SQL:
        """)
        
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
        sql_query = sql_text.strip()
        sql_query = re.sub(r'```sql\n?', '', sql_query)
        sql_query = re.sub(r'```\n?', '', sql_query)
        return sql_query.strip()