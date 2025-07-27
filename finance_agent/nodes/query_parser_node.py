import http.client, json, uuid, requests, re
import pandas as pd
import datetime, pymysql
from typing import Dict
from config.config import Config
# from finance_agent.utils import is_url
from finance_agent.llm import LLM
from finance_agent.prompts import query_parser_prompt as prompt


def is_url(text: str) -> bool:
    # 문장 안 어디에 있든 URL이 있으면 True
    url_pattern = re.compile(r'https?://[^\s]+')
    return bool(url_pattern.search(text))



class QueryParserNode:
    def __init__(self):
        self.llm = LLM()
        self.company_df = self.load_krx_tickers_from_db()

        # Clova intent 분류기용 설정
        self._clova_host = Config.CLOVA_HOST
        self._api_key = Config.CLOVA_API_KEY
        self._hyperclova_host = "https://" + Config.CLOVA_HOST
        self._model_endpoint = "/v3/chat-completions/HCX-005"

    def load_krx_tickers_from_db(self) -> pd.DataFrame:
        try:
            conn = pymysql.connect(
                host=Config.MYSQL_HOST,
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD,
                database=Config.MYSQL_DATABASE,
                port=Config.MYSQL_PORT,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            df = pd.read_sql("SELECT 회사명, ticker FROM krx_tickers", conn)
            conn.close()
            return df
        except Exception as e:
            print(f"[QueryParserNode] DB Load Error: {e}")
            return pd.DataFrame(columns=['회사명', 'ticker'])

    def classify_summary_intent(self, user_query: str) -> str:
        """
        Clova를 이용해 뉴스 요약 관련 intent만 판별.
        """
        # URL이 있으면 무조건 URL 요약
        if is_url(user_query):
            return "url_summary_request"

        # 뉴스/요약 키워드 포함 여부 빠르게 체크
        keywords = ["뉴스", "요약", "핫한", "오늘"]
        if not any(k in user_query for k in keywords):
            return "not_summary"  # 요약 관련 아님

        # Clova에게 intent 판별 요청
        prompt_text = f"""
        사용자의 요청이 뉴스 요약과 관련된지 판별하고, 아래 4개 중 하나로 JSON만 출력.
        - "url_summary_request"
        - "today_news_request"
        - "news_summary_request"
        - "hot_news_request"

        만약 뉴스 요약과 무관하다면 "not_summary"로 답변.
        입력: "{user_query}"
        """
        headers = {
            'Authorization': f'Bearer {self._api_key}',
            'X-NCP-CLOVASTUDIO-REQUEST-ID': str(uuid.uuid4()),
            'Content-Type': 'application/json; charset=utf-8'
        }
        payload = {
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt_text}]}],
            "topP": 0.8, "temperature": 0.2, "maxTokens": 100
        }
        try:
            resp = requests.post(self._hyperclova_host + self._model_endpoint, headers=headers, json=payload)
            raw = resp.json().get("result", {}).get("message", {}).get("content", [{}])[0].get("text", "")
            match = re.search(r'\{.*\}', raw)
            if match:
                return json.loads(match.group(0)).get("intent", "not_summary")
        except:
            pass
        return "not_summary"

    def get_day_label(self, date: datetime.datetime) -> str:
        return "토요일" if date.weekday() == 5 else "일요일" if date.weekday() == 6 else "평일"

    def lookup_ticker(self, company_name: str) -> str:
        row = self.company_df[self.company_df['회사명'] == company_name.strip()]
        return row['ticker'].values[0] if not row.empty else None

    def process(self, state: Dict) -> Dict:
        user_query = state.get("user_query", "")

        # 1. 요약 intent 판별
        intent = self.classify_summary_intent(user_query)
        if intent != "not_summary":
            # 뉴스 요약 플로우용 parsed_query 저장 (나머지는 SqlGeneratorNode에서 처리)
            state["parsed_query"] = {
                "intent": intent,
                "date": "", "company_name": "", "market": ""
            }
            return state

        # 2. 주식 데이터 질의 처리 (기존 query_parser_prompt 이용)
        try:
            response = self.llm.run(prompt.format(user_query=user_query))
            parsed = self._parse_json(response)

            # 날짜/요일 처리
            date_str = parsed.get("date")
            date, date_day = None, None
            if date_str:
                try:
                    date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                    date_day = self.get_day_label(date)
                except:
                    pass

            company_name = parsed.get("company_name")
            ticker = self.lookup_ticker(company_name) if company_name else None
            state["parsed_query"] = {
                "intent": "stock_query",
                "company_name": company_name,
                "ticker": ticker,
                "date": date.strftime("%Y-%m-%d") if date else None,
                "date_day": date_day,
                "market": parsed.get("market", "")
            }
            if date_day in {"토요일", "일요일"}:
                state["final_output"] = f"{date.strftime('%Y-%m-%d')}는 {date_day}로 휴장일입니다."
                state["is_complete"] = True
        except Exception as e:
            state["parsed_query"] = {"intent": "unknown"}
        return state

    def _parse_json(self, response: str) -> Dict:
        try:
            match = re.search(r"```json\s*(.*?)```", response, re.DOTALL)
            return json.loads(match.group(1).strip()) if match else {}
        except:
            return {}






"""
import pandas as pd
from typing import Dict
import re, json
from finance_agent.llm import LLM
from finance_agent.prompts import query_parser_prompt as prompt
import datetime
import pymysql
from config.config import Config

class QueryParserNode:
    def __init__(self):
        self.llm = LLM()
        self.company_df = self.load_krx_tickers_from_db()

    def load_krx_tickers_from_db(self) -> pd.DataFrame:
        try:
            conn = pymysql.connect(
                host=Config.MYSQL_HOST,
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD,
                database=Config.MYSQL_DATABASE,
                port=Config.MYSQL_PORT,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            query = "SELECT 회사명, ticker FROM krx_tickers"
            df = pd.read_sql(query, conn)
            conn.close()
            return df
        except Exception as e:
            print(f"[QueryParserNode] DB Load Error: {e}")
            # 에러 시 빈 DataFrame 반환 (회사명, ticker 컬럼 포함)
            return pd.DataFrame(columns=['회사명', 'ticker'])

    def get_day_label(self, date: datetime.datetime) -> str:
        if date.weekday() == 5:
            return "토요일"
        elif date.weekday() == 6:
            return "일요일"
        else:
            return "평일"
        # todo: 공휴일 로직 추가 (예: KRX API 또는 local holiday DB)

    def lookup_ticker(self, company_name: str) -> str:
        company_name = company_name.strip()
        ticker_row = self.company_df[self.company_df['회사명'] == company_name]
        return ticker_row['ticker'].values[0] if not ticker_row.empty else None

    def process(self, state: Dict) -> Dict:
        user_query = state.get("user_query", "")
        try:
            response = self.llm.run(prompt.format(user_query=user_query))
            parsed = self._parse_json(response)
            # print(f"[QueryParserNode] Parsed response: {parsed}")  # 디버깅용

            # 날짜 파싱 및 요일 판별
            date_str = parsed.get("date")
            if isinstance(date_str, str):
                date, date_day = None, None
                if date_str:
                    try:
                        date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                        date_day = self.get_day_label(date)
                    except ValueError:
                        print(f"Invalid date format: {date_str}")
                        date = None
                        date_day = None
            else:
                date, date_day = None, None

            # 회사명 및 티커 추출
            company_name = parsed.get("company_name")
            ticker = self.lookup_ticker(company_name) if company_name else None

            # 파싱된 결과 저장
            state["parsed_query"] = {
                "company_name": company_name,
                "ticker": ticker,
                "date": date.strftime("%Y-%m-%d") if date else None,
                "date_day": date_day,
                "market": parsed.get("market", "")
            }
            if date_day in {"토요일", "일요일"}:
                state["final_output"] = f"{date.strftime('%Y-%m-%d')}는 {date_day}로 휴장일입니다."
                state["is_complete"] = True
                state["needs_user_input"] = False
                
        except Exception as e:
            print(f"[QueryParserNode] Parsing error: {e}")
            state["parsed_query"] = {
                "company_name": None,
                "ticker": None,
                "date": None,
                "date_day": None,
                "market": ""
            }
        return state

    def _parse_json(self, response: str) -> Dict:
        Extract JSON from LLM response
        try:
            match = re.search(r"```json\s*(.*?)```", response, re.DOTALL)
            if not match:
                raise ValueError("No JSON block found")
            json_str = match.group(1).strip()
            return json.loads(json_str)
        except (ValueError, json.JSONDecodeError) as e:
            print(f"JSON parsing error: {e}")
            return {}

"""