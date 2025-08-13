# finance_agent/nodes/query_parser_node.py (이 코드로 파일 전체를 교체하세요)

import pandas as pd
from typing import Dict, Sequence
import re, json
from langchain_core.messages import BaseMessage
from finance_agent.llm import LLM
from finance_agent.prompts import query_parser_prompt as prompt
import datetime

def format_chat_history(chat_history: Sequence[BaseMessage]) -> str:
    """대화 기록을 LLM 프롬프트에 맞는 문자열 형식으로 변환합니다."""
    formatted_history = []
    for msg in chat_history:
        role = "사용자" if msg.type == "human" else "어시스턴트"
        formatted_history.append(f"{role}: {msg.content}")
    return "\n".join(formatted_history)

class QueryParserNode:
    def __init__(self):
        self.llm = LLM()
        self.company_df = pd.read_csv("./data/stock/krx_tickers.csv")

    def get_day_label(self, date: datetime.datetime) -> str:
        # ... (기존과 동일) ...
        return "평일"

    def lookup_ticker(self, company_name: str) -> str:
        # ... (기존과 동일) ...
        return None

    def process(self, state: Dict) -> Dict:
        state["needs_user_input"] = False
        # ✨ state에서 user_query와 chat_history를 모두 가져옵니다.
        user_query = state.get("user_query", "")
        chat_history = state.get("chat_history", [])
        
        try:
            # ✨ 프롬프트에 chat_history도 포맷팅하여 전달
            formatted_history = format_chat_history(chat_history)
            response = self.llm.run(prompt.format(
                user_query=user_query, 
                chat_history=formatted_history
            ))
            
            parsed = self._parse_json(response)

            # 사용자의 프롬프트 출력 형식에 맞게 entities 추출
            entities = parsed.get("entities", parsed)
            
            date_str = entities.get("date")
            # ... (이하 날짜 파싱 및 티커 추출 로직은 기존과 거의 동일) ...
            
            company_name = entities.get("company_name")
            ticker = self.lookup_ticker(company_name) if company_name else None

            state["parsed_query"] = {
                "company_name": company_name,
                "ticker": ticker,
                "date": date_str, # 날짜 형식은 LLM 결과에 따름
                "market": entities.get("market", "")
            }
            # ... (이하 휴장일 처리 로직 등) ...
        except Exception as e:
            print(f"[QueryParserNode] Parsing error: {e}")
            state["parsed_query"] = {}
        return state

    def _parse_json(self, response: str) -> Dict:
        match = re.search(r"```json\s*(.*?)```", response, re.DOTALL)
        if not match:
            json_str = response.strip()
        else:
            json_str = match.group(1).strip()
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"[DEBUG:query_parser_node] JSON 파싱 실패: {e}")
            return {}