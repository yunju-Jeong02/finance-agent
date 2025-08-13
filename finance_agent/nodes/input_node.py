# finance_agent/nodes/input_node.py (이 코드로 파일 전체를 교체하세요)

import json, re
from typing import Dict, List, Sequence
from langchain_core.messages import BaseMessage
from finance_agent.prompts import clarification_prompt 
from finance_agent.llm import LLM

def format_chat_history(chat_history: Sequence[BaseMessage]) -> str:
    """대화 기록을 LLM 프롬프트에 맞는 문자열 형식으로 변환합니다."""
    formatted_history = []
    for msg in chat_history:
        role = "사용자" if msg.type == "human" else "어시스턴트"
        formatted_history.append(f"{role}: {msg.content}")
    return "\n".join(formatted_history)

class InputNode:
    def __init__(self):
        pass
    
    def process(self, state: Dict) -> Dict:
        # ✨ state에서 user_query와 chat_history를 모두 가져옵니다.
        user_query = state["user_query"]
        chat_history = state["chat_history"]

        # ✨ _check_query_clarity 함수에 chat_history도 전달합니다.
        clarification = self._check_query_clarity(user_query, chat_history)
        
        state["clarification_needed"] = clarification["clarification_needed"]
        state["clarification_question"] = clarification["clarification_question"]

        if state["clarification_needed"]:
            state["is_complete"] = False
            state["needs_user_input"] = True
        
        return state
    
    # ✨ _check_query_clarity가 chat_history를 받도록 수정
    def _check_query_clarity(self, query: str, chat_history: Sequence[BaseMessage]) -> Dict:
        llm = LLM()
        
        # ✨ 프롬프트에 chat_history도 포맷팅하여 전달
        formatted_history = format_chat_history(chat_history)
        prompt = clarification_prompt.format(
            user_query=query, 
            chat_history=formatted_history
        )
        response = llm.run(prompt)

        response_json = self._parse_json(response)
        
        return {
            "clarification_needed": bool(response_json.get("clarification_needed", False)),
            "clarification_question": response_json.get("clarification_question", "")
        }
    
    def _parse_json(self, response: str) -> Dict:
        match = re.search(r"```json\s*(.*?)```", response, re.DOTALL)
        if not match:
            # JSON 블록이 없는 경우, 응답 전체를 파싱 시도
            json_str = response.strip()
        else:
            json_str = match.group(1).strip()

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"[DEBUG:input_node] JSON 파싱 실패: {e}, 원본: {json_str[:200]}")
            return {}