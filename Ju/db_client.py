import pandas as pd
from sqlalchemy import create_engine, text
from config import Config

class DBClient:
    def __init__(self):
        self.engine = create_engine(
            f"mysql+pymysql://{Config.DB_USER}:{Config.DB_PASSWORD}@{Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}"
        )

    def search_news(self, keywords=None, date=None, limit=1):
        """
        DB에서 뉴스 검색 (키워드 리스트와 날짜 적용, 안전한 SQL)
        """
        conditions = []
        params = {}

        if date:
            conditions.append("date >= :date")
            params["date"] = date

        if keywords:
            if isinstance(keywords, str):
                conditions.append("title LIKE :kw0")
                params["kw0"] = f"%{keywords}%"
            elif isinstance(keywords, (list, tuple)):
                for i, kw in enumerate(keywords):
                    conditions.append(f"title LIKE :kw{i}")
                    params[f"kw{i}"] = f"%{kw}%"

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query_with_content = text(f"""
            SELECT title, link, date, content
            FROM News
            WHERE {where_clause}
            ORDER BY date DESC
            LIMIT :limit;
        """)
        query_no_content = text(f"""
            SELECT title, link, date, NULL as content
            FROM News
            WHERE {where_clause}
            ORDER BY date DESC
            LIMIT :limit;
        """)
        params["limit"] = limit

        try:
            df = pd.read_sql(query_with_content, self.engine, params=params)
        except Exception:
            df = pd.read_sql(query_no_content, self.engine, params=params)

        return df.to_dict(orient="records")