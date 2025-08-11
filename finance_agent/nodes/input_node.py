"""
Input Processing Node
# 애매하면 되묻기 노드
"""

import json, re
from typing import Dict, List
from finance_agent.prompts import clarification_prompt 
from finance_agent.llm import LLM

class InputNode:
    def __init__(self):
        pass
    
    def process(self, state: Dict) -> Dict:
        query_history = state["user_query"]
        clarification = self._check_query_clarity(query_history)
        state["clarification_needed"] = clarification["clarification_needed"]
        state["clarification_question"] = clarification["clarification_question"]

        if state["clarification_needed"]:
            state["is_complete"] = False
            state["needs_user_input"] = True
        # print(state)
        return state
    
    def _check_query_clarity(self, query: str) -> Dict:
        llm = LLM()
        prompt = clarification_prompt.format(user_query=query)
        response = llm.run(prompt)

        # JSON 파싱
        response = self._parse_json(response)
        # print(response)

        return {
            "clarification_needed": bool(response.get("clarification_needed", False)),
            "clarification_question": response.get("clarification_question", "")
        }
    
    def _parse_json(self, response: str) -> Dict:
        """
        LLM 응답에서 ```json ... ``` 블록을 추출하고,
        홑따옴표(')가 섞인 경우에도 JSON으로 변환할 수 있게 처리.
        """
        match = re.search(r"```json\s*(.*?)```", response, re.DOTALL)
        if not match:
            raise ValueError("No JSON block found")
        json_str = match.group(1).strip()

        if "'" in json_str and '"' not in json_str:
            json_str = json_str.replace("'", '"')

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"[DEBUG:input_node] JSON 파싱 실패: {e}, 원본: {json_str[:200]}")
            return {}

        