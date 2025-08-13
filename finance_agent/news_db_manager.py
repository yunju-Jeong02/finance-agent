# news_db_manager.py
"""
Database manager for News DB (News table) with optional Naver crawl fallback
"""

import re
import time
from typing import List, Dict, Optional, Union
from collections import Counter

import pymysql
import pandas as pd
import requests
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from config.config import Config


class NewsDatabaseManager:
    """News DB 전용 매니저 (검색/크롤링 보조)"""
    
    def __init__(self):
        self.config = Config()
        self.connection = None
        self.engine = None
        self.connect()
    
    # ----------------- 연결 -----------------
    def connect(self):
        try:
            # pymysql connection (dict cursor로 변환은 실행 시 지정)
            self.connection = pymysql.connect(
                host=self.config.MYSQL_HOST,
                port=self.config.MYSQL_PORT,
                user=self.config.MYSQL_USER,
                password=self.config.MYSQL_PASSWORD,
                database=self.config.MYSQL_DATABASE2,  # 뉴스 DB
                charset="utf8mb4",
            )
            # SQLAlchemy engine (pandas.read_sql 용)
            self.engine = create_engine(
                f"mysql+pymysql://{self.config.MYSQL_USER}:{self.config.MYSQL_PASSWORD}"
                f"@{self.config.MYSQL_HOST}:{self.config.MYSQL_PORT}/{self.config.MYSQL_DATABASE2}"
            )
        except Exception as e:
            print(f"[NewsDatabaseManager] DB 연결 실패: {e}")
            raise e

    # ----------------- 공통 SELECT -----------------
    def execute_query(self, query: str, params: Optional[List] = None) -> List[Dict]:
        if not self.connection:
            self.connect()
        cursor = self.connection.cursor(pymysql.cursors.DictCursor)
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            rows = cursor.fetchall()
            formatted = []
            for row in rows:
                out = {}
                for k, v in row.items():
                    if hasattr(v, "strftime"):
                        out[k] = v.strftime("%Y-%m-%d")
                    elif hasattr(v, "__float__"):
                        out[k] = float(v)
                    else:
                        out[k] = v
                formatted.append(out)
            return formatted
        except Exception as e:
            print(f"[NewsDatabaseManager] SQL 실행 오류: {e}")
            raise e
        finally:
            cursor.close()

    # ----------------- 뉴스 검색 (DB 우선, 없으면 크롤링) -----------------
    def search_news(self, keywords: Optional[Union[str, List[str]]] = None, start_date: Optional[str] = None, end_date: Optional[str] = None, date: Optional[str] = None, limit: int = 5) -> List[Dict]:
        conditions, params = [], {}
        
        # ✨ 1. 기간 검색(start_date, end_date)과 단일일 검색(date)을 모두 처리하도록 로직 수정
        if date and not start_date and not end_date:
            start_date = end_date = date
        
        if start_date:
            # 날짜 형식에서 숫자만 추출 (예: '2025-08-06' -> '20250806')
            conditions.append("date >= :start_date")
            params["start_date"] = re.sub(r"[^0-9]", "", start_date)
        if end_date:
            conditions.append("date <= :end_date")
            params["end_date"] = re.sub(r"[^0-9]", "", end_date)

        # 키워드 정리
        clean_keywords: List[str] = []
        if keywords:
            if isinstance(keywords, str): keywords = [keywords]
            for kw in keywords:
                if not re.search(r"\d{4}[-./]?\d{1,2}[-./]?\d{0,2}", kw):
                    clean_keywords.append(kw)
        
        for i, kw in enumerate(clean_keywords):
            conditions.append(f"title LIKE :kw{i}")
            params[f"kw{i}"] = f"%{kw}%"

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params["limit"] = limit

        query = text(f"""
            SELECT DISTINCT title, link, date, NULL as content
            FROM News WHERE {where_clause}
            ORDER BY date DESC, id DESC LIMIT :limit;
        """)
        
        try:
            df = pd.read_sql(query, self.engine, params=params)
        except Exception as e:
            print(f"[NewsDatabaseManager] DB 조회 실패: {e}")
            df = pd.DataFrame()

        # DB 검색 결과가 있으면 바로 반환
        if not df.empty:
            return df.to_dict(orient="records")

        # ---- DB에 없으면 크롤링 fallback (참고: 크롤링은 기간 검색을 지원하지 않음) ----
        company = clean_keywords[0] if clean_keywords else ""
        extras = clean_keywords[1:] if len(clean_keywords) > 1 else []
        norm_date = re.sub(r"[^0-9]", "", date) if date else None
        return self._crawl_naver_news(company=company, extra_keywords=extras, date=norm_date, limit=limit)

    # ----------------- 크롤링 & 본문 -----------------
    def _crawl_naver_news(self, company: str, extra_keywords: List[str], date: Optional[str] = None, limit: int = 3) -> List[Dict]:
        keyword_query = " ".join([company] + (extra_keywords or [])).strip()

        if date:
            # date: YYYYMMDD
            ds = de = f"{date[:4]}.{date[4:6]}.{date[6:]}"
            yyyymmdd = date
            url = (
                f"https://search.naver.com/search.naver"
                f"?where=news&query={keyword_query}&sm=tab_opt&sort=0"
                f"&ds={ds}&de={de}&nso=so%3Ar%2Cp%3Afrom{yyyymmdd}to{yyyymmdd}"
            )
        else:
            url = f"https://search.naver.com/search.naver?where=news&query={keyword_query}&sort=0"

        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        driver = webdriver.Chrome(options=options)
        try:
            driver.get(url)
            time.sleep(3)

            elements = driver.find_elements(By.CSS_SELECTOR, 'a[target="_blank"][href^="http"]')
            articles, seen = [], set()

            for el in elements:
                href = el.get_attribute("href")
                title = (el.get_attribute("title") or el.text or "").strip()

                if not href or href in seen:
                    continue
                if any(b in href for b in ["/main/static/", "channelPromotion", "/main/vod/", "news/home", "opinion"]):
                    continue
                if not ("news.naver.com" in href or "n.news.naver.com" in href or "did=NA" in href or "Read" in href):
                    continue

                seen.add(href)
                articles.append({
                    "title": title,
                    "link": href,
                    "date": date or "",
                    "content": "",  # fetch 후 채움
                })
                if len(articles) >= limit:
                    break
        finally:
            driver.quit()

        # 본문 fetch
        for a in articles:
            a["content"] = self._fetch_news_content(a["link"])
        return articles

    def _fetch_news_content(self, url: str) -> str:
        try:
            res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
            if res.status_code != 200:
                return ""
            soup = BeautifulSoup(res.text, "html.parser")
            for selector in ["#dic_area", "#articleBody", ".article-body", ".news-article", "div.content"]:
                div = soup.select_one(selector)
                if div:
                    return div.get_text(" ", strip=True)
            paragraphs = soup.select("p")
            text = " ".join(p.get_text(" ", strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30)
            return text.strip()
        except Exception:
            return ""

    # ----------------- 유틸 -----------------
    def get_recent_news_titles(self, limit: int = 100) -> pd.DataFrame:
        query = f"""
            SELECT title
            FROM News
            ORDER BY date DESC, id DESC
            LIMIT {limit}
        """
        try:
            return pd.read_sql(query, con=self.engine)
        except Exception as e:
            print(f"[NewsDatabaseManager] 최근 뉴스 조회 실패: {e}")
            return pd.DataFrame()

    def extract_top_keywords(self, titles: pd.Series, top_n: int = 5) -> List[str]:
        try:
            text = " ".join(map(str, titles))
            words = re.sub(r"[^가-힣a-zA-Z0-9\s]", "", text).split()
            stopwords = {"그리고", "하지만", "그래서", "때문에", "있다", "하다", "되다", "않다", "수", "것", "들", "등"}
            counter = Counter([w for w in words if w not in stopwords and len(w) > 1])
            return [w for w, _ in counter.most_common(top_n)]
        except Exception as e:
            print(f"[NewsDatabaseManager] 키워드 추출 실패: {e}")
            return []

    def get_available_dates(self, limit: int = 10) -> List[str]:
        query = f"SELECT DISTINCT date FROM News ORDER BY date DESC LIMIT {limit}"
        try:
            rows = self.execute_query(query)
            return [r["date"] for r in rows]
        except:
            return []

    def validate_query(self, query: str) -> bool:
        try:
            q = query.upper().strip()
            if not q.startswith("SELECT"):
                return False
            for kw in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE"]:
                if kw in q:
                    return False
            if self.connection:
                cur = self.connection.cursor()
                try:
                    cur.execute(f"EXPLAIN {query}")
                    cur.fetchall()
                    return True
                except:
                    return False
                finally:
                    cur.close()
            return True
        except:
            return False

    def close_connection(self):
        if self.connection:
            self.connection.close()

    def __del__(self):
        self.close_connection()