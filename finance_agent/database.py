
import pymysql
import re
from typing import List, Dict, Optional
import pandas as pd
from sqlalchemy import create_engine, text
from config.config import Config
import requests
from bs4 import BeautifulSoup
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from collections import Counter


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

        conditions, params = [], {}

        # 날짜를 YYYYMMDD로 변환
        if date:
            date_yyyymmdd = re.sub(r'[^0-9]', '', date)
            if len(date_yyyymmdd) == 8:
                date = date_yyyymmdd
                conditions.append("date = :date")
                params["date"] = date
            else:
                date = ""

        # 키워드 정리
        clean_keywords = []
        if keywords:
            for kw in (keywords if isinstance(keywords, (list, tuple)) else [keywords]):
                if not re.search(r'\d{4}[-./]?\d{1,2}[-./]?\d{0,2}', kw):
                    clean_keywords.append(kw)

        for i, kw in enumerate(clean_keywords):
            conditions.append(f"title LIKE :kw{i}")
            params[f"kw{i}"] = f"%{kw}%"

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query_with_content = text(f"""
            SELECT DISTINCT title, link, date, content
            FROM News
            WHERE {where_clause}
            ORDER BY date DESC
            LIMIT :limit;
        """)
        params["limit"] = limit

        # 디버깅 로그 추가
        print(f"[DEBUG:search_news] date param: {date}, keywords: {clean_keywords}")
        print(f"[DEBUG:search_news] SQL: {query_with_content}")
        print(f"[DEBUG:search_news] Params: {params}")

        try:
            df = pd.read_sql(query_with_content, self.engine, params=params)
        except Exception as e:
            print(f"[DEBUG:search_news] with_content 실패: {e}")
            query_no_content = text(f"""
                SELECT DISTINCT title, link, date, NULL as content
                FROM News
                WHERE {where_clause}
                ORDER BY date DESC
                LIMIT :limit;
            """)
            df = pd.read_sql(query_no_content, self.engine, params=params)

        print(f"[DEBUG:search_news] DB 결과 {len(df)}건")
        if not df.empty:
            return df.to_dict(orient="records")

        # --- fallback 크롤링 ---
        company = clean_keywords[0] if clean_keywords else ""
        extra_keywords = clean_keywords[1:] if len(clean_keywords) > 1 else []
        print(f"[DEBUG:search_news] DB 결과 없음, 크롤링 시도 -> company={company}, extra={extra_keywords}, date={date}")
        return self._crawl_naver_news(company, extra_keywords, date, limit)


    def _crawl_naver_news(self, company: str, extra_keywords: list, date: str = None, limit: int = 3):
        keyword_query = " ".join([company] + (extra_keywords or [])) if company else ""

        if date:
            # date가 "20250601" 같이 순수 숫자 8자리면,
            #  -> "2025.06.01" 형태로 변환 필요
            if len(date) == 8 and date.isdigit():
                ds = de = f"{date[:4]}.{date[4:6]}.{date[6:]}"
                yyyymmdd = date
            else:
                # "2025-06-01" 등일 때
                ds = de = date.replace("-", ".")
                yyyymmdd = date.replace("-", "")
            url = (
                f"https://search.naver.com/search.naver"
                f"?where=news&query={keyword_query}&sm=tab_opt&sort=0"
                f"&ds={ds}&de={de}&nso=so%3Ar%2Cp%3Afrom{yyyymmdd}to{yyyymmdd}"
            )
        else:
            url = f"https://search.naver.com/search.naver?where=news&query={keyword_query}&sort=0"
        options = Options()
        # 필요에 따라 headless 켜거나 끕니다
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                             "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        driver = webdriver.Chrome(options=options)
        driver.get(url)
        time.sleep(3)  # 렌더링 대기

        elements = driver.find_elements(By.CSS_SELECTOR, 'a[target="_blank"][href^="http"]')

        articles = []
        seen = set()

        for el in elements:
            href = el.get_attribute("href")
            title = el.get_attribute("title") or el.text

            if not href or href in seen:
                continue
            if any(block in href for block in ["/main/static/", "channelPromotion", "/main/vod/", "news/home", "opinion"]):
                continue
            if not ("news.naver.com" in href or "n.news.naver.com" in href or "did=NA" in href or "Read" in href):
                continue

            seen.add(href)
            articles.append({
                "title": title.strip(),
                "link": href,
                "date": date or "",
                "content": "",  # 본문은 나중에 개별 fetch
            })
            if len(articles) >= limit:
                break

        driver.quit()
        return articles

    def _fetch_news_content(self, url: str) -> str:
        """
        뉴스 기사 URL에서 본문 크롤링. BS4로 주요 본문 영역 추출.
        """
        try:
            res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
            if res.status_code != 200:
                return ""
            soup = BeautifulSoup(res.text, "html.parser")
            for selector in ["#dic_area", "#articleBody", ".article-body", ".news-article", "div.content"]:
                div = soup.select_one(selector)
                if div:
                    return div.get_text(" ", strip=True)
            # fallback: 모든 <p> 태그 중 내용이 충분한 문장 합침
            paragraphs = soup.select("p")
            text = " ".join(p.get_text(" ", strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30)
            return text.strip()
        except Exception:
            return ""

    def _crawl_and_summarize_news(self, company: str, extra_keywords: list, date: str = None, limit: int = 3) -> list:
        """
        1) Selenium 크롤링으로 뉴스 리스트 가져오기
        2) 각 뉴스 URL에서 본문 크롤링
        3) 요약 API 호출(외부 함수)로 요약 생성
        4) 리스트 형태로 요약 결과 반환

        요약 API 호출함수는 SqlGeneratorNode 클래스 내 구현 예정이므로 인자로 받거나 콜백 활용 가능.
        """
        articles = self._crawl_naver_news(company, extra_keywords, date, limit)

        # 요약 API 호출은 외부에서 처리할 수 있도록 content만 채워둠
        # 예시로 빈 내용 반환 후 요약 담당자 호출 권장
        for article in articles:
            article["content"] = self._fetch_news_content(article["link"])

        return articles
    
    def get_recent_news_titles(self, limit=100):
        if self.db_type != "news":
            raise ValueError("get_recent_news_titles는 뉴스 DB 전용입니다.")
        query = f"""
            SELECT title
            FROM News 
            ORDER BY date DESC, id DESC 
            LIMIT {limit}
        """
        try:
            df = pd.read_sql(query, con=self.engine)
            if df.empty:
                print("[DatabaseManager] 최근 뉴스 조회 결과가 없습니다.")
            return df
        except Exception as e:
            print(f"[DatabaseManager] 최근 뉴스 조회 실패: {e}")
            return pd.DataFrame()

    def extract_top_keywords(self, titles: pd.Series, top_n=5):
        try:
            text = ' '.join(titles)
            words = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', text).split()
            stopwords = {'그리고','하지만','그래서','때문에','있다','하다','되다','않다','수','것','들','등'}
            counter = Counter([w for w in words if w not in stopwords and len(w) > 1])
            return [w for w, _ in counter.most_common(top_n)]
        except Exception as e:
            print(f"[DatabaseManager] 키워드 추출 실패: {e}")
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