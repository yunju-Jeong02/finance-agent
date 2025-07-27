import pymysql
import re
from typing import List, Dict, Optional
import pandas as pd
from sqlalchemy import create_engine, text
from config.config import Config
import requests
from bs4 import BeautifulSoup



class DatabaseManager:
    """
    Database manager supporting:
      - finance_db (주식 데이터: krx_stockprice)
      - news_db (뉴스 데이터: News 테이블)
    """

    def __init__(self, db_type: str = "finance"):
        """
        db_type:
            "finance" -> finance_db (기본, 주식 데이터)
            "news"    -> NEWS_DB (뉴스 데이터)
        """
        self.config = Config()
        self.db_type = db_type
        self.connection = None
        self.engine = None
        self.connect()

    # ----------------- 연결 -----------------
    def connect(self):
        """Connect to MySQL database based on db_type"""
        try:
            db_name = self._get_db_name()
            self.connection = pymysql.connect(
                host=self.config.MYSQL_HOST,
                port=self.config.MYSQL_PORT,
                user=self.config.MYSQL_USER,
                password=self.config.MYSQL_PASSWORD,
                database=db_name,
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor
            )
            # SQLAlchemy 엔진 (pandas.read_sql 사용용)
            self.engine = create_engine(
                f"mysql+pymysql://{self.config.MYSQL_USER}:{self.config.MYSQL_PASSWORD}"
                f"@{self.config.MYSQL_HOST}:{self.config.MYSQL_PORT}/{db_name}"
            )
        except Exception as e:
            print(f"[DatabaseManager] DB 연결 실패 ({self.db_type}): {e}")
            raise e

    def _get_db_name(self) -> str:
        """Return proper database name for given db_type"""
        return self.config.MYSQL_DATABASE2 if self.db_type == "news" else self.config.MYSQL_DATABASE

    # ----------------- 공통 SQL 실행 -----------------
    def execute_query(self, query: str, params: Optional[List] = None) -> List[Dict]:
        """Execute SQL query and return results as list of dicts"""
        if not self.connection:
            self.connect()
        cursor = self.connection.cursor()
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            results = cursor.fetchall()
            return self._format_results(results)
        except Exception as e:
            print(f"[DatabaseManager] SQL 실행 오류: {e}")
            raise e
        finally:
            cursor.close()

    def _format_results(self, results: List[Dict]) -> List[Dict]:
        """Convert datetime/Decimal to str/float for JSON-friendly results"""
        formatted = []
        for row in results:
            new_row = {}
            for k, v in row.items():
                if hasattr(v, "strftime"):  # datetime
                    new_row[k] = v.strftime("%Y-%m-%d")
                elif hasattr(v, "__float__"):  # Decimal
                    new_row[k] = float(v)
                else:
                    new_row[k] = v
            formatted.append(new_row)
        return formatted

    def execute_query_single(self, query: str, params: Optional[List] = None) -> Optional[Dict]:
        """Execute SQL query and return single row (dict)"""
        results = self.execute_query(query, params)
        return results[0] if results else None

        # ----------------- 뉴스 DB 전용 -----------------
    def search_news(self, keywords=None, date=None, limit=5) -> List[Dict]:
        if self.db_type != "news":
            raise ValueError("search_news는 뉴스 DB 전용입니다.")

        # --- 1) DB 검색 ---
        conditions, params = [], {}

        # 날짜를 YYYYMMDD로 변환
        if date:
            date_yyyymmdd = re.sub(r'[^0-9]', '', date)  # 숫자만 추출
            if len(date_yyyymmdd) == 8:
                date = date_yyyymmdd
                conditions.append("date = :date")
                params["date"] = date
            else:
                date = ""  # 날짜 형식이 맞지 않으면 필터 제거

        # 키워드에서 날짜 패턴 제거
        clean_keywords = []
        if keywords:
            for kw in (keywords if isinstance(keywords, (list, tuple)) else [keywords]):
                if not re.search(r'\d{4}[-./]?\d{1,2}[-./]?\d{0,2}', kw):
                    clean_keywords.append(kw)

        for i, kw in enumerate(clean_keywords):
            conditions.append(f"title LIKE :kw{i}")
            params[f"kw{i}"] = f"%{kw}%"

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # DISTINCT로 중복 제거
        query_with_content = text(f"""
            SELECT DISTINCT title, link, date, content
            FROM News
            WHERE {where_clause}
            ORDER BY date DESC
            LIMIT :limit;
        """)
        query_no_content = text(f"""
            SELECT DISTINCT title, link, date, NULL as content
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

        # DB에서 결과가 있으면 반환
        if not df.empty:
            return df.to_dict(orient="records")

        # --- 2) Fallback: 네이버 HTML 크롤링 ---
        company = clean_keywords[0] if clean_keywords else ""
        extra_keywords = clean_keywords[1:] if len(clean_keywords) > 1 else []
        return self._crawl_naver_news(company, extra_keywords, date, limit)



    def _crawl_naver_news(self, company: str, extra_keywords: list, date: Optional[str], limit: int = 5) -> List[Dict]:
            """
            네이버 뉴스 HTML 크롤링 (기업명 + 추가 키워드 + 날짜)
            - DB에 뉴스가 없거나 today_news_request일 때 사용.
            - 본문은 content=""로 두고 나중에 fetch.
            """
            # 키워드 조합
            keyword_query = " ".join([company] + (extra_keywords or [])) if company else " ".join(extra_keywords or [])

            # 네이버 뉴스 검색 URL (날짜 필터링 지원)
            if date:
                ds = de = date.replace("-", ".")
                yyyymmdd = date.replace("-", "")
                url = (
                    f"https://search.naver.com/search.naver"
                    f"?where=news&query={keyword_query}&sm=tab_opt&sort=1"
                    f"&ds={ds}&de={de}&nso=so%3Ar%2Cp%3Afrom{yyyymmdd}to{yyyymmdd}"
                )
            else:
                url = f"https://search.naver.com/search.naver?where=news&query={keyword_query}&sort=1"

            try:
                res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
                if res.status_code != 200:
                    return []

                soup = BeautifulSoup(res.text, "html.parser")
                articles = []
                for a_tag in soup.select("a.news_tit")[:limit]:
                    title = a_tag.get("title", "").strip()
                    link = a_tag.get("href", "").strip()
                    articles.append({
                        "title": title,
                        "link": link,
                        "date": date or "",  # 날짜 없으면 공백
                        "content": ""        # 본문은 나중에 fetch
                    })

                return articles
            except Exception as e:
                print(f"[DatabaseManager] 네이버 뉴스 크롤링 실패: {e}")
                return []
    # ----------------- 주식 DB 전용 -----------------
    def get_table_schema(self) -> str:
        """Fetch schema info for krx_stockprice (finance DB only)"""
        if self.db_type != "finance":
            return "Schema 조회는 finance DB 전용입니다."
        query = """
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_COMMENT
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'krx_stockprice'
        ORDER BY ORDINAL_POSITION;
        """
        try:
            results = self.execute_query(query, [self.config.MYSQL_DATABASE])
            schema = "Table: krx_stockprice\nColumns:\n"
            for col in results:
                schema += f"- {col['COLUMN_NAME']} ({col['DATA_TYPE']}): {col['COLUMN_COMMENT'] or 'No comment'}\n"
            return schema
        except Exception as e:
            print(f"[DatabaseManager] 스키마 조회 실패: {e}")
            return self._get_default_schema()

    def _get_default_schema(self) -> str:
        return """
        Table: krx_stockprice
        Columns:
        - date: 거래 일자 (YYYY-MM-DD)
        - adj_close: 수정 종가
        - close: 종가
        - high: 당일 최고가
        - low: 당일 최저가
        - open: 당일 시가
        - volume: 당일 거래량
        - ticker: 종목 코드 (예: 005930.KS)
        - company_name: 회사명
        - price_change_pct: 전일 대비 등락률 (%)
        - volume_change_pct: 전일 대비 거래량 변화율 (%)
        - ma_5, ma_20, ma_60: 5/20/60일 이동평균
        - ma_vol_20: 20일 평균 거래량
        - volume_ratio_20: 거래량 비율
        - rsi_14: RSI (14일)
        - bollinger_upper/lower: 볼린저 밴드
        - golden_cross/dead_cross: 크로스 신호
        """

    def get_sample_data(self, limit: int = 5) -> List[Dict]:
        """Fetch sample rows (finance DB only)"""
        if self.db_type != "finance":
            return []
        query = f"SELECT * FROM krx_stockprice ORDER BY date DESC LIMIT {limit}"
        try:
            return self.execute_query(query)
        except:
            return []

    def get_companies_by_name(self, name_pattern: str) -> List[Dict]:
        """Search companies by partial name (finance DB only)"""
        if self.db_type != "finance":
            return []
        query = """
        SELECT DISTINCT ticker, company_name
        FROM krx_stockprice
        WHERE company_name LIKE %s
        ORDER BY company_name
        """
        try:
            return self.execute_query(query, [f"%{name_pattern}%"])
        except:
            return []

    def get_available_dates(self, limit: int = 10) -> List[str]:
        """Return recent dates (both DB types supported)"""
        table = "News" if self.db_type == "news" else "krx_stockprice"
        query = f"SELECT DISTINCT date FROM {table} ORDER BY date DESC LIMIT {limit}"
        try:
            rows = self.execute_query(query)
            return [row["date"] for row in rows]
        except:
            return []

    # ----------------- 유틸 -----------------
    def validate_query(self, query: str) -> bool:
        """Validate SQL query (only SELECT)"""
        try:
            q = query.upper().strip()
            if not q.startswith("SELECT"):
                return False
            if any(k in q for k in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE"]):
                return False
            if self.connection:
                cursor = self.connection.cursor()
                try:
                    cursor.execute(f"EXPLAIN {query}")
                    cursor.fetchall()
                    return True
                except:
                    return False
                finally:
                    cursor.close()
            return True
        except:
            return False

    def close_connection(self):
        if self.connection:
            self.connection.close()

    def __del__(self):
        self.close_connection()


