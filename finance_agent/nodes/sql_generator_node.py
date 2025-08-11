import re, uuid, requests
import traceback
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
            if resp.status_code != 200:
                return f"[요약 실패] Clova status {resp.status_code}: {resp.text[:100]}"
            try:
                data = resp.json()
            except ValueError:
                return f"[요약 실패] Clova JSON 파싱 오류: {resp.text[:200]}"
            
            content_resp = data.get("result", {}).get("message", {}).get("content", "")
            if isinstance(content_resp, str):
                return content_resp.strip()
            if isinstance(content_resp, list) and content_resp:
                first = content_resp[0]
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
                    content = self.news_db._fetch_news_content(url)  # 이 부분 함수는 별도로 존재해야 함
                summary = self._summarize_with_clova(title, content, url)
                summaries.append(f"- {title}\n{summary}\n출처: {url}")
            state["final_output"] = "📰 뉴스 요약\n" + "\n\n".join(summaries)
        else:
            state["final_output"] = "❗ 관련 뉴스를 찾을 수 없습니다."
        state["is_complete"] = True
        return state
    def _handle_hot_news(self, state: Dict) -> Dict:
        try:
            print("[DEBUG:hot_news] 핫 뉴스 처리 시작")
            df = self.news_db.get_recent_news_titles(limit=100)
            print(f"[DEBUG:hot_news] 최근 뉴스 로드: {len(df)}개")
            if df.empty:
                state["final_output"] = "❌ 최근 뉴스가 없습니다."
                state["is_complete"] = True
                return state

            top_keywords = self.news_db.extract_top_keywords(df['title'])
            print(f"[DEBUG:hot_news] 추출된 키워드: {top_keywords}")
            if not top_keywords:
                state["final_output"] = "❌ 주요 키워드를 찾지 못했습니다."
                state["is_complete"] = True
                return state

            keywords_list = "\n".join(f"{i+1}. {kw}" for i, kw in enumerate(top_keywords))
            print(f"[DEBUG:hot_news] 키워드 목록:\n{keywords_list}")

            state["final_output"] = (
                f"🔥 최근 자주 언급된 키워드:\n{keywords_list}\n\n"
                f"요약할 키워드 번호(1~{len(top_keywords)})를 입력해주세요."
            )
            state["is_complete"] = False
            state["pending_action"] = {"type": "hot_news_select", "keywords": top_keywords}
            return state
        except Exception as e:
            tb_str = traceback.format_exc()
            print(f"[DEBUG:hot_news] 예외 발생: {e}")
            print(tb_str)
            state["final_output"] = f"핫 뉴스 처리 중 오류가 발생했습니다: {e}"
            state["is_complete"] = True
            return state

    def handle_hot_news_selection(self, state: Dict, selection: int) -> Dict:
        """
        선택한 키워드 기반으로 최신 뉴스 요약 (Clova 요약 API 사용)
        """
        pending = state.get("pending_action", {})
        keywords = pending.get("keywords", [])
        if not keywords or not (1 <= selection <= len(keywords)):
            state["final_output"] = "❗ 잘못된 선택입니다."
            state["is_complete"] = True
            return state

        selected_kw = keywords[selection - 1]
        df = self.news_db.get_recent_news_titles(limit=100)

        # 선택한 키워드가 포함된 뉴스 중 최신 기사
        match = df[df['title'].str.contains(selected_kw, na=False)]
        if match.empty:
            state["final_output"] = f"❌ {selected_kw} 관련 뉴스가 없습니다."
            state["is_complete"] = True
            return state

        latest = match.iloc[0]  # 최신 기사 (정렬된 상태)

        # content 컬럼이 없으므로 title을 그대로 사용
        title = latest.get('title', '')
        content = title  # 요약 대상도 title로
        summary = self._summarize_with_clova(title, content, "")

        state["final_output"] = (
            f"📰 기사 제목: {title}\n\n"
            f"📌 요약:\n{summary}"
        )
        state["is_complete"] = True
        state["pending_action"] = {}
        return state

    # ----------- 주식 SQL 처리 -----------
    def process(self, state: Dict) -> Dict:
        parsed = state.get("parsed_query", {})
        intent = parsed.get("intent", "")
        user_query = state.get("user_query", "")
        # Hot 뉴스 요약
        if intent == "hot_news_request":
            return self._handle_hot_news(state)

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
        return re.sub(r"(``````|'''sql|''')", "", text).strip()

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