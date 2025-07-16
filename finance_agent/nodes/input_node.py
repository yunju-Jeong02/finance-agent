"""
Input Processing Node
# 애매하면 되묻기 노드
"""

from typing import Dict, List
from finance_agent.prompts import clarification_prompt 
from finance_agent.llm import LLM


class InputNode:
    """Node for processing user input"""
    def __init__(self):
        pass
    
    def process(self, state: Dict) -> Dict:
        """Process user input and determine clarity"""
        query_history = state["user_query"]
        clarification = self._check_query_clarity(query_history)
        state.update(clarification)
        return state
    
    def _check_query_clarity(self, query: str) -> Dict:
        llm = LLM()
        response = llm.run(clarification_prompt.format(user_query=query))
        return {
            "clarification_needed": response["clarification_needed"],
            "clarification_question": response["clarification_question"],
        }
    