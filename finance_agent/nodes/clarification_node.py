"""
Clarification Node
Handles clarification questions for ambiguous queries
"""

from typing import Dict


class ClarificationNode:
    """Node for handling clarification"""
    
    def __init__(self):
        pass
    
    def process(self, state: Dict) -> Dict:
        """Process clarification request"""
        state["final_output"] = state["clarification_question"]
        state["is_complete"] = False
        state["needs_user_input"] = True
        return state