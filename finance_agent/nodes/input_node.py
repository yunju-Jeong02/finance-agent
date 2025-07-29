import json
from typing import Dict
from finance_agent.prompts import clarification_prompt
from finance_agent.parsers import extract_json_from_response
from finance_agent.llm import LLM

class InputNode:
    def __init__(self):
        pass

    def process(self, state: Dict) -> Dict:
        query = state["user_query"]
        pending_action = state.get("pending_action", None)
        clarification = self._check_query_clarity(query, pending_action)
        state.update(clarification)
        return state

    def _check_query_clarity(self, query: str, pending_action=None) -> Dict:
        """
        Clarification 판단 로직
        - 핫뉴스 키워드 선택(pending_action=hot_news_select) 또는 숫자 입력(query.isdigit())일 경우 Clarification 무조건 생략
        - "핫한"이 포함된 경우에도 Clarification 생략
        """
        if (pending_action and pending_action.get("type") == "hot_news_select") or query.isdigit() or "핫한" in query:
            return {"clarification_needed": False, "clarification_question": ""}

        llm = LLM()
        prompt = clarification_prompt.format(user_query=query)
        response = llm.run(prompt)

        try:
            result = extract_json_from_response(response)
        except Exception as e:
            print(f"[DEBUG:_check_query_clarity] JSON 파싱 실패: {e} / 원본: {response[:200]}")
            result = {}

        return {
            "clarification_needed": bool(result.get("clarification_needed", False)),
            "clarification_question": result.get("clarification_question", "")
        }
