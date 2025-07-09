"""
Input Processing Node
Handles user input and determines if clarification is needed
"""

from typing import Dict


class InputNode:
    """Node for processing user input"""
    
    def __init__(self):
        pass
    
    def process(self, state: Dict) -> Dict:
        """Process user input and determine clarity"""
        user_query = state["user_query"]
        
        # Simple rule-based clarification check
        needs_clarification = self._check_query_clarity(user_query)
        
        state["clarification_needed"] = needs_clarification
        
        if needs_clarification:
            state["clarification_question"] = self._generate_clarification_question(user_query)
        
        return state
    
    def _check_query_clarity(self, query: str) -> bool:
        """Check if query needs clarification"""
        query_lower = query.lower()
        
        # Clear patterns
        clear_patterns = [
            "가장 비싼 종목",
            "최고가 종목", 
            "상승률 높은",
            "하락률 높은",
            "거래량 많은",
            "종목 3개",
            "종목 5개",
            "종목 10개"
        ]
        
        # Date patterns
        has_date = any(pattern in query for pattern in [
            "2024", "2025", "어제", "오늘", "지난주", 
            "-01-", "-02-", "-03-", "-04-", "-05-", "-06-", 
            "-07-", "-08-", "-09-", "-10-", "-11-", "-12-"
        ])
        
        # Market patterns
        has_market = any(market in query_lower for market in ["kospi", "kosdaq", "시장"])
        
        # If clear patterns and market, no clarification needed
        if any(pattern in query_lower for pattern in clear_patterns) and has_market:
            return False
            
        # Vague patterns need clarification
        vague_patterns = ["종목은?", "주식은?", "어떤", "무엇", "알려줘"]
        
        if any(pattern in query_lower for pattern in vague_patterns) and not has_date:
            return True
            
        return False
    
    def _generate_clarification_question(self, query: str) -> str:
        """Generate clarification question"""
        query_lower = query.lower()
        missing_info = []
        
        # Check missing date
        if not any(pattern in query_lower for pattern in [
            "2024", "2025", "어제", "오늘", "지난주", 
            "-01-", "-02-", "-03-", "-04-", "-05-", "-06-", 
            "-07-", "-08-", "-09-", "-10-", "-11-", "-12-"
        ]):
            missing_info.append("날짜")
        
        # Check missing market
        if not any(market in query_lower for market in ["kospi", "kosdaq", "시장"]):
            missing_info.append("시장 (KOSPI/KOSDAQ)")
        
        # Check missing count
        if "몇 개" not in query_lower and not any(num in query_lower for num in ["3개", "5개", "10개"]):
            missing_info.append("조회할 개수")
        
        if missing_info:
            return f"다음 정보를 추가로 알려주세요: {', '.join(missing_info)}"
        else:
            return "더 구체적인 정보를 제공해주세요."