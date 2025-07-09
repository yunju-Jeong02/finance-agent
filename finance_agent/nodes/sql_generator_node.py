"""
SQL Generator Node
Generates SQL queries from user input
"""

from typing import Dict
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import re
from config.config import Config
from finance_agent.database import DatabaseManager


class SqlGeneratorNode:
    """Node for generating SQL queries"""
    
    def __init__(self):
        self.config = Config()
        self.llm = ChatOpenAI(
            temperature=0.1,
            model="gpt-4o-mini",
            openai_api_key=self.config.OPENAI_API_KEY
        )
        self.db_manager = DatabaseManager()
    
    def process(self, state: Dict) -> Dict:
        """Generate SQL query from user input"""
        user_query = state["user_query"]
        
        # Get latest available date
        latest_date = self._get_latest_available_date()
        
        prompt = ChatPromptTemplate.from_template("""
        다음 한국어 질문을 krx_stockprice 테이블에 대한 SQL 쿼리로 변환해주세요.
        
        질문: {query}
        
        규칙:
        1. 날짜가 없으면 최신 날짜 {latest_date} 사용
        2. KOSPI: ticker LIKE '%.KS'
        3. KOSDAQ: ticker LIKE '%.KQ'
        4. 가장 비싼: ORDER BY Close DESC
        5. 상승: price_change_pct > 0
        6. 하락: price_change_pct < 0
        7. 거래량: Volume 컬럼
        8. 회사명: company_name 컬럼
        9. SELECT 문만 사용
        10. 결과만 반환 (설명 없이)
        
        SQL:
        """)
        
        try:
            response = self.llm.invoke(prompt.format(
                query=user_query,
                latest_date=latest_date
            ))
            
            sql_query = self._clean_sql(response.content)
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
    
    def _clean_sql(self, sql_text: str) -> str:
        """Clean SQL query text"""
        sql_query = sql_text.strip()
        sql_query = re.sub(r'```sql\n?', '', sql_query)
        sql_query = re.sub(r'```\n?', '', sql_query)
        return sql_query.strip()
    
    def _get_latest_available_date(self) -> str:
        """Get latest available date from database"""
        try:
            dates = self.db_manager.get_available_dates(1)
            return dates[0] if dates else "2025-07-09"
        except:
            return "2025-07-09"