import re, uuid, requests
from bs4 import BeautifulSoup
from typing import Dict
from finance_agent.llm import LLM
from finance_agent.database import DatabaseManager
from finance_agent.prompts import sql_generation_prompt, news_summary_prompt
from config.config import Config
from datetime import datetime


class SqlGeneratorNode:
    def __init__(self):
        self.llm = LLM()
        self.finance_db = DatabaseManager(db_type="finance")
        self.news_db = DatabaseManager(db_type="news")
        self._clova_host = Config.CLOVA_HOST
        self._api_key = Config.CLOVA_API_KEY
        self._hyperclova_host = "https://" + Config.CLOVA_HOST
        self._model_endpoint = "/v3/chat-completions/HCX-005"

    def _fetch_news_content(self, url: str) -> str:
        try:
            res = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            if res.status_code != 200:
                return ""
            soup = BeautifulSoup(res.text, "html.parser")
            for selector in ["#dic_area", "#articleBody", ".article-body", ".news-article", "div.content"]:
                div = soup.select_one(selector)
                if div:
                    return div.get_text(" ", strip=True)
            # fallback: 모든 <p> 태그 조합
            paragraphs = soup.select("p")
            text = " ".join(p.get_text(" ", strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30)
            return text.strip()
        except:
            return ""

    def _summarize_with_clova(self, title: str, content: str, url: str) -> str:
        prompt_text = news_summary_prompt.format(title=title, content=content, url=url)
        headers = {
            'Authorization': f'Bearer {self._api_key}',
            'X-NCP-CLOVASTUDIO-REQUEST-ID': str(uuid.uuid4()),
            'Content-Type': 'application/json; charset=utf-8'
        }
        payload = {
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt_text}]}],
            "topP": 0.8, "temperature": 0.2, "maxTokens": 500
        }
        try:
            resp = requests.post(self._hyperclova_host + self._model_endpoint, headers=headers, json=payload, timeout=10)
            data = resp.json()
            content = data.get("result", {}).get("message", {}).get("content", "")
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list) and content:
                first = content[0]
                return first.get("text", "").strip() if isinstance(first, dict) else str(first).strip()
            return "[요약 오류] Clova 응답 없음"
        except Exception as e:
            return f"[요약 실패] {e}"

    def _handle_news_summary(self, state: Dict) -> Dict:
        parsed = state.get("parsed_query", {})
        intent = parsed.get("intent", "")
        date = parsed.get("date", "")
        keywords = parsed.get("keywords", [])

        # 1) today_news_request → 무조건 네이버 뉴스 크롤링
        if intent == "today_news_request":
            news = self.news_db._crawl_naver_news(
                company=keywords[0] if keywords else "",
                extra_keywords=keywords[1:] if len(keywords) > 1 else [],
                date=datetime.now().strftime("%Y-%m-%d"),
                limit=3
            )
        else:
            # 2) DB 우선 검색 → 없으면 크롤링 백업
            news = self.news_db.search_news(keywords=keywords, date=date, limit=3)
            if not news:
                news = self.news_db._crawl_naver_news(
                    company=keywords[0] if keywords else "",
                    extra_keywords=keywords[1:] if len(keywords) > 1 else [],
                    date=date,
                    limit=3
                )

        if news:
            summaries = []
            for n in news:
                title, url, content = n["title"], n["link"], n.get("content", "")
                if not content:
                    content = self._fetch_news_content(url)
                summary = self._summarize_with_clova(title, content, url)
                summaries.append(f"- {title}\n{summary}\n출처: {url}")
            state["final_output"] = "📰 뉴스 요약\n" + "\n\n".join(summaries)
        else:
            state["final_output"] = "❗ 관련 뉴스를 찾을 수 없습니다."
        state["is_complete"] = True
        return state

    # ----------- 주식 SQL 처리 -----------
    def process(self, state: Dict) -> Dict:
        parsed = state.get("parsed_query", {})
        intent = parsed.get("intent", "")
        user_query = state.get("user_query", "")

        if intent.endswith("_summary_request") or intent.endswith("_news_request"):
            return self._handle_news_summary(state)

        ticker = parsed.get("ticker", "")
        market = parsed.get("market", "")
        ticker_hint = f"ticker = '{ticker}'" if ticker else ""
        market_hint = (
            "ticker LIKE '%.KS'" if market == "KOSPI"
            else "ticker LIKE '%.KQ'" if market == "KOSDAQ"
            else ""
        )
        latest_date = self._get_latest_date()

        try:
            prompt_text = sql_generation_prompt.format(
                user_query=user_query,
                latest_date=latest_date,
                ticker_hint=ticker_hint,
                market_hint=market_hint
            )
            llm_resp = self.llm.run(prompt_text)
            sql_query = self._clean_sql(llm_resp)
            if ticker_hint and ticker_hint not in sql_query:
                sql_query = self._ensure_ticker(sql_query, ticker_hint)

            state["sql_query"] = sql_query
            state["sql_attempts"] = 1
            try:
                results = self.finance_db.execute_query(sql_query)
                state["query_results"] = results
                state["sql_error"] = ""
            except Exception as e:
                state["query_results"] = []
                state["sql_error"] = str(e)
        except Exception as e:
            state["sql_query"] = ""
            state["query_results"] = []
            state["sql_error"] = f"SQL 생성 오류: {e}"
        return state

    def _clean_sql(self, text: str) -> str:
        return re.sub(r"(```sql|```|'''sql|''')", "", text).strip()

    def _ensure_ticker(self, sql: str, ticker_hint: str) -> str:
        if "WHERE" in sql:
            return re.sub(r"(WHERE\s+)", rf"\1{ticker_hint} AND ", sql, flags=re.IGNORECASE)
        return sql + f" WHERE {ticker_hint}"

    def _get_latest_date(self) -> str:
        try:
            dates = self.finance_db.get_available_dates(1)
            if dates:
                return dates[0]
            return datetime.today().strftime("%Y-%m-%d")
        except:
            return datetime.today().strftime("%Y-%m-%d")



"""
import re, uuid, requests
from bs4 import BeautifulSoup
from typing import Dict
from finance_agent.llm import LLM
from finance_agent.database import DatabaseManager
from finance_agent.prompts import sql_generation_prompt, news_summary_prompt
from config.config import Config
from datetime import datetime


class SqlGeneratorNode:
    def __init__(self):
        self.llm = LLM()
        self.finance_db = DatabaseManager(db_type="finance")
        self.news_db = DatabaseManager(db_type="news")
        self._clova_host = Config.CLOVA_HOST
        self._api_key = Config.CLOVA_API_KEY
        self._hyperclova_host = "https://" + Config.CLOVA_HOST
        self._model_endpoint = "/v3/chat-completions/HCX-005"

    # ---------------- 뉴스 처리 ----------------
    def _fetch_news_content(self, url: str) -> str:
        try:
            res = requests.get(url, timeout=5)
            if res.status_code != 200:
                return ""
            soup = BeautifulSoup(res.text, "html.parser")

            # 1) 네이버 뉴스
            for selector in ["#dic_area", "#articleBody", ".article-body", ".news-article", "div.content"]:
                content_div = soup.select_one(selector)
                if content_div:
                    return content_div.get_text(" ", strip=True)

            # 2) fallback: 본문으로 추정되는 <p> 태그 모음
            paragraphs = soup.select("p")
            text = " ".join(p.get_text(" ", strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30)
            return text.strip()
        except:
            return ""

    def _summarize_with_clova(self, title: str, content: str, url: str) -> str:
        prompt_text = news_summary_prompt.format(title=title, content=content, url=url)
        headers = {
            'Authorization': f'Bearer {self._api_key}',
            'X-NCP-CLOVASTUDIO-REQUEST-ID': str(uuid.uuid4()),
            'Content-Type': 'application/json; charset=utf-8'
        }
        payload = {
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt_text}]}],
            "topP": 0.8, "temperature": 0.2, "maxTokens": 500
        }
        try:
            resp = requests.post(self._hyperclova_host + self._model_endpoint, headers=headers, json=payload, timeout=10)
            data = resp.json()
            content = data.get("result", {}).get("message", {}).get("content", "")
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list) and content:
                first = content[0]
                return first.get("text", "").strip() if isinstance(first, dict) else str(first).strip()
            return "[요약 오류] Clova 응답 없음"
        except Exception as e:
            return f"[요약 실패] {e}"

    def _handle_news_summary(self, state: Dict) -> Dict:
        parsed = state.get("parsed_query", {})
        intent = parsed.get("intent", "")
        date = parsed.get("date", "")
        keywords = parsed.get("keywords", [])

        # URL 요약
        if intent == "url_summary_request":
            url = state["user_query"].strip()
            content = self._fetch_news_content(url)
            if not content:
                state["final_output"] = f"❗ 뉴스 본문을 가져올 수 없습니다: {url}"
                state["is_complete"] = True
                return state
            summary = self._summarize_with_clova("해당 뉴스", content, url)
            state["final_output"] = f"📰 뉴스 요약\n{summary}"
            state["is_complete"] = True
            return state

        # 뉴스 DB 검색
        news = self.news_db.search_news(keywords=keywords, date=date, limit=3)
        if news:
            summaries = []
            for n in news:
                title, url, content = n["title"], n["link"], n.get("content", "")
                if not content:
                    content = self._fetch_news_content(url)
                summary = self._summarize_with_clova(title, content, url)
                summaries.append(f"- {title}\n{summary}\n출처: {url}")
            state["final_output"] = "📰 뉴스 요약\n" + "\n\n".join(summaries)
        else:
            state["final_output"] = "❗ 관련 뉴스를 찾을 수 없습니다."
        state["is_complete"] = True
        return state

    # ---------------- 주식 SQL 처리 ----------------
    def process(self, state: Dict) -> Dict:
        parsed = state.get("parsed_query", {})
        intent = parsed.get("intent", "")
        user_query = state.get("user_query", "")

        # 뉴스 요약 플로우
        if intent.endswith("_summary_request") or intent.endswith("_news_request"):
            return self._handle_news_summary(state)

        # 주식 SQL 처리
        ticker = parsed.get("ticker", "")
        market = parsed.get("market", "")
        ticker_hint = f"ticker = '{ticker}'" if ticker else ""
        market_hint = (
            "ticker LIKE '%.KS'" if market == "KOSPI"
            else "ticker LIKE '%.KQ'" if market == "KOSDAQ"
            else ""
        )
        latest_date = self._get_latest_date()

        try:
            prompt_text = sql_generation_prompt.format(
                user_query=user_query,
                latest_date=latest_date,
                ticker_hint=ticker_hint,
                market_hint=market_hint
            )
            llm_resp = self.llm.run(prompt_text)
            sql_query = self._clean_sql(llm_resp)
            if ticker_hint and ticker_hint not in sql_query:
                sql_query = self._ensure_ticker(sql_query, ticker_hint)

            state["sql_query"] = sql_query
            state["sql_attempts"] = 1
            try:
                results = self.finance_db.execute_query(sql_query)
                state["query_results"] = results
                state["sql_error"] = ""
            except Exception as e:
                state["query_results"] = []
                state["sql_error"] = str(e)
        except Exception as e:
            state["sql_query"] = ""
            state["query_results"] = []
            state["sql_error"] = f"SQL 생성 오류: {e}"
        return state

    def _clean_sql(self, text: str) -> str:
        return re.sub(r"(```sql|```|'''sql|''')", "", text).strip()

    def _ensure_ticker(self, sql: str, ticker_hint: str) -> str:
        if "WHERE" in sql:
            return re.sub(r"(WHERE\s+)", rf"\1{ticker_hint} AND ", sql, flags=re.IGNORECASE)
        return sql + f" WHERE {ticker_hint}"

    def _get_latest_date(self) -> str:
        try:
            dates = self.finance_db.get_available_dates(1)
            if dates:
                return dates[0]
            # DB에 데이터 없으면 오늘 날짜 반환
            return datetime.today().strftime("%Y-%m-%d")
        except:
            return datetime.today().strftime("%Y-%m-%d")
"""