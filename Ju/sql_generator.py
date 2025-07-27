"""
SQL Generator Node (Clova + DBClient 기반)
사용자 질문을 바탕으로 SQL을 자동 생성하고, 실행 후 결과 반환
"""

import re
from typing import Dict
from clova_client import ClovaClient
from db_client import DBClient


class SqlGeneratorNode:
    def __init__(self):
        self.clova = ClovaClient()
        self.db = DBClient()

    def process(self, state: Dict) -> Dict:
        """사용자 입력으로 SQL 생성 및 실행"""
        user_query = state.get("user_query", "")
        latest_date = self._get_latest_date()

        # SQL 생성 프롬프트
        prompt_text = f"""
        다음 사용자 질문을 기반으로 MySQL 쿼리를 생성해.
        - 뉴스는 News 테이블에서 찾고, title, link, date, content 컬럼이 있다고 가정해.
        - {latest_date} 이전의 데이터도 허용하되, 최신순으로 정렬.
        - WHERE 절에는 키워드(title LIKE '%...%')와 날짜(date >= ...) 조건을 모두 반영.
        - LIMIT 10으로 결과를 제한.
        - SQL만 출력하고 다른 문장은 넣지 마.

        사용자 질문: {user_query}
        """

        try:
            # Clova 모델로 SQL 생성
            raw_sql = self.clova.clarify(prompt_text)
            sql_query = self._clean_sql(raw_sql)
            state["sql_query"] = sql_query

            # SQL 실행
            try:
                results = self.db.engine.execute(sql_query).fetchall()
                # fetchall()을 dict 형태로 변환
                cols = results[0].keys() if results else []
                state["query_results"] = [dict(zip(cols, row)) for row in results]
                state["sql_error"] = ""
            except Exception as e:
                state["query_results"] = []
                state["sql_error"] = f"SQL 실행 오류: {e}"

        except Exception as e:
            state["sql_query"] = ""
            state["query_results"] = []
            state["sql_error"] = f"SQL 생성 오류: {e}"

        return state

    def _clean_sql(self, sql_text: str) -> str:
        """코드 블록, 불필요한 문자 제거"""
        sql_query = sql_text.strip()
        sql_query = re.sub(r"(```sql|'''sql|```|''')", "", sql_query, flags=re.IGNORECASE)
        return sql_query.strip()

    def _get_latest_date(self) -> str:
        """DB에서 최신 날짜 가져오기"""
        try:
            result = self.db.engine.execute("SELECT MAX(date) as max_date FROM News").fetchone()
            return result["max_date"] if result and result["max_date"] else "2025-07-13"
        except:
            return "2025-07-13"
