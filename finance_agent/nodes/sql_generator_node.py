import http.client, json, uuid, requests, re
from bs4 import BeautifulSoup
from typing import Dict
from finance_agent.llm import LLM
from finance_agent.database import DatabaseManager
from finance_agent.prompts import sql_generation_prompt, news_summary_prompt
from config.config import Config


class SqlGeneratorNode:
    def __init__(self):
        self.llm = LLM()
        self.db_manager = DatabaseManager()

        # Clova API 설정
        self._clova_host = Config.CLOVA_HOST
        self._api_key = Config.CLOVA_API_KEY
        self._hyperclova_host = "https://" + Config.CLOVA_HOST
        self._model_endpoint = "/v3/chat-completions/HCX-005"

    def _fetch_news_content(self, url: str) -> str:
        """
        네이버 뉴스 등에서 본문 크롤링 (간단히 #dic_area 기준)
        """
        try:
            res = requests.get(url, timeout=5)
            if res.status_code != 200:
                return ""
            soup = BeautifulSoup(res.text, "html.parser")
            content_div = soup.select_one("#dic_area")
            if content_div:
                return content_div.get_text(" ", strip=True)
            return ""
        except Exception as e:
            print(f"[ERROR] 뉴스 본문 크롤링 실패: {e}")
            return ""
    def _summarize_news(self, title: str, content: str, url: str) -> str:
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

            # JSON 응답 구조를 안전하게 파싱
            content = data.get("result", {}).get("message", {}).get("content", "")

            # content가 문자열인 경우
            if isinstance(content, str):
                return content.strip()

            # content가 리스트인 경우
            if isinstance(content, list) and content:
                first_item = content[0]
                if isinstance(first_item, dict):
                    return first_item.get("text", "").strip()
                elif isinstance(first_item, str):
                    return first_item.strip()

            return "[요약 오류] Clova 응답을 이해할 수 없습니다."

        except Exception as e:
            return f"[요약 실패] {e}"


    def process(self, state: Dict) -> Dict:
        parsed = state.get("parsed_query", {})
        intent = parsed.get("intent", "")
        user_query = state.get("user_query", "")

        # 뉴스 URL 요약 요청 처리
        if intent == "url_summary_request":
            url = user_query.strip()  # 입력된 URL 그대로 사용
            # 1. 뉴스 본문 크롤링
            content = self._fetch_news_content(url)
            if not content:
                state["final_output"] = f"❗ 뉴스 본문을 가져올 수 없습니다: {url}"
                state["is_complete"] = True
                return state

            # 2. Clova로 요약
            summary = self._summarize_news(title="해당 뉴스", content=content, url=url)
            state["final_output"] = f"📰 뉴스 요약\n{summary}"
            state["is_complete"] = True
            return state

        # 주식 관련 질의(SQL 생성) 처리 (기존 로직 유지)
        ticker = parsed.get("ticker", "")
        market = parsed.get("market", "")
        ticker_hint = f"ticker = '{ticker}'" if ticker else ""
        market_hint = (
            "ticker LIKE '%.KS'" if market == "KOSPI"
            else "ticker LIKE '%.KQ'" if market == "KOSDAQ"
            else ""
        )

        latest_date = self._get_latest_available_date()
        try:
            prompt_text = sql_generation_prompt.format(
                user_query=user_query,
                latest_date=latest_date,
                ticker_hint=ticker_hint,
                market_hint=market_hint
            )
            llm_response = self.llm.run(prompt_text)
            sql_query = self._parse_sql(llm_response)

            if ticker_hint and not self._ticker_hint_exists(sql_query, ticker_hint):
                sql_query = self._ensure_ticker_filter(sql_query, ticker_hint)

            state["sql_query"] = sql_query
            state["sql_attempts"] = 1

            try:
                results = self.db_manager.execute_query(sql_query)
                state["query_results"] = results
                state["sql_error"] = ""
            except Exception as e:
                state["query_results"] = []
                state["sql_error"] = str(e)

        except Exception as e:
            state["sql_query"] = ""
            state["query_results"] = []
            state["sql_error"] = f"SQL 생성 오류: {str(e)}"

        return state

    def _parse_sql(self, sql_text: str) -> str:
        sql_query = re.sub(r"(```sql|```|'''sql|''')", "", sql_text).strip()
        return sql_query

    def _ticker_hint_exists(self, sql_query: str, ticker_hint: str) -> bool:
        normalized_sql = re.sub(r"\s+", " ", sql_query).lower()
        return ticker_hint.lower() in normalized_sql

    def _ensure_ticker_filter(self, sql_query: str, ticker_hint: str) -> str:
        if ticker_hint and ticker_hint not in sql_query:
            if "ticker LIKE" in sql_query:
                sql_query = re.sub(
                    r"(WHERE\s+.*?ticker\s+LIKE\s+'[^']+')",
                    rf"\1 AND {ticker_hint}",
                    sql_query,
                    flags=re.IGNORECASE | re.DOTALL
                )
            else:
                sql_query = re.sub(r"(WHERE\s+)", rf"\1{ticker_hint} AND ", sql_query, flags=re.IGNORECASE)
        return sql_query

    def _get_latest_available_date(self) -> str:
        try:
            dates = self.db_manager.get_available_dates(1)
            return dates[0] if dates else "2025-07-25"
        except:
            return "2025-07-25"






"""
from typing import Dict
from langchain_core.prompts import ChatPromptTemplate
import re
from finance_agent.database import DatabaseManager
from finance_agent.llm import LLM
from finance_agent.prompts import sql_generation_prompt as prompt


class SqlGeneratorNode:    
    def __init__(self):
        self.llm = LLM()
        self.db_manager = DatabaseManager()
    
    def process(self, state: Dict) -> Dict:
        user_query = state["user_query"]
        parsed_query = state.get("parsed_query", {})
        ticker = parsed_query.get("ticker", "")
        market = parsed_query.get("market", "")

        ticker_hint = f"ticker = '{ticker}'" if ticker else ""
        market_hint = (
            "ticker LIKE '%.KS'" if market == "KOSPI"
            else "ticker LIKE '%.KQ'" if market == "KOSDAQ"
            else ""
        )

        latest_date = self._get_latest_available_date()
        
        try:
            prompt_text = prompt.format(
                user_query=user_query,
                latest_date=latest_date,
                ticker_hint=ticker_hint,
                market_hint=market_hint
            )
            llm_response = self.llm.run(prompt_text)
            sql_query = self._parse_sql(llm_response)

            # print(f"[SQL Generation] LLM response: {llm_response}")  # 디버깅용

            # 약간의 하드코딩..
            if ticker_hint:
                if not self._ticker_hint_exists(sql_query, ticker_hint):
                    # 한글 ticker가 있다면 교체
                    sql_query = self._replace_korean_ticker(sql_query, ticker_hint) 
                # 여전히 ticker 조건이 없다면 삽입
                if not self._ticker_hint_exists(sql_query, ticker_hint):
                    sql_query = self._ensure_ticker_filter(sql_query, ticker_hint)
            
            state["sql_query"] = sql_query
            state["sql_attempts"] = 1

            try:
                results = self.db_manager.execute_query(sql_query)
                state["query_results"] = results
                state["sql_error"] = ""
            except Exception as e:
                state["query_results"] = []
                state["sql_error"] = str(e)

        except Exception as e:
            state["sql_query"] = ""
            state["query_results"] = []
            state["sql_error"] = f"SQL 생성 오류: {str(e)}"

        return state

    def _parse_sql(self, sql_text: str) -> str:
        # Clean markdown/codeblock from SQL
        sql_query = sql_text.strip()
        sql_query = re.sub(r"(```sql|'''sql)", "", sql_query, flags=re.IGNORECASE)
        sql_query = re.sub(r"(```|''')", "", sql_query)
        return sql_query.strip()

    def _get_latest_available_date(self) -> str:
        try:
            dates = self.db_manager.get_available_dates(1)
            return dates[0] if dates else "2025-07-09"
        except Exception:
            return "2025-07-09"
        
    def _ticker_hint_exists(self, sql_query: str, ticker_hint: str) -> bool:
        
        # ticker 조건이 SQL 쿼리에 이미 존재하는지 확인
        normalized_sql = re.sub(r"\s+", " ", sql_query).lower()
        normalized_hint = ticker_hint.lower()
        return normalized_hint in normalized_sql

    def _replace_korean_ticker(self, sql_query: str, ticker_hint: str) -> str:
        # 패턴: ticker = '현대사료' → ticker = '016790.KQ'
        sql_query = re.sub(r"ticker\s*=\s*['\"][가-힣]+['\"]", ticker_hint, sql_query)
        return sql_query
    
    def _ensure_ticker_filter(self, sql_query: str, ticker_hint: str) -> str:
        if ticker_hint and ticker_hint not in sql_query:
            # ticker LIKE 가 있는 경우 AND로 ticker = ... 추가
            if "ticker LIKE" in sql_query:
                sql_query = re.sub(
                    r"(WHERE\s+.*?ticker\s+LIKE\s+'[^']+')",
                    rf"\1 AND {ticker_hint}",
                    sql_query,
                    flags=re.IGNORECASE | re.DOTALL
                )
            else:
                # ticker 조건 자체가 없으면 그냥 WHERE 뒤에 추가
                sql_query = re.sub(
                    r"(WHERE\s+)",
                    rf"\1{ticker_hint} AND ",
                    sql_query,
                    flags=re.IGNORECASE
                )
        return sql_query

"""