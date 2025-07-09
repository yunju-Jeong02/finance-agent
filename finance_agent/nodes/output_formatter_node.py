"""
Output Formatter Node
Formats query results according to specifications
"""

from typing import Dict, List


class OutputFormatterNode:
    """Node for formatting output"""
    
    def __init__(self):
        pass
    
    def process(self, state: Dict) -> Dict:
        """Format final output"""
        user_query = state["user_query"]
        results = state["query_results"]
        
        if not results:
            state["final_output"] = "조회된 데이터가 없습니다."
            state["is_complete"] = True
            return state
        
        # Format based on query type
        formatted_output = self._format_output(user_query, results)
        state["final_output"] = formatted_output
        state["is_complete"] = True
        return state
    
    def _format_output(self, user_query: str, results: List[Dict]) -> str:
        """Format output according to specifications"""
        if not results:
            return "조회된 데이터가 없습니다."
        
        query_lower = user_query.lower()
        
        # Count queries (몇 개)
        if "몇 개" in query_lower:
            count = results[0].get('count', len(results))
            return f"{count}개입니다."
        
        # Volume queries (거래량)
        if "거래량" in query_lower:
            return self._format_volume_output(results)
        
        # Price queries (가격, 종가, 비싼)
        if any(word in query_lower for word in ["가격", "종가", "비싼", "높은", "최고가"]):
            return self._format_price_output(user_query, results)
        
        # Company list queries
        return self._format_company_output(results)
    
    def _format_volume_output(self, results: List[Dict]) -> str:
        """Format volume data as 00,000개"""
        if len(results) == 1:
            volume = results[0].get('Volume', 0)
            return f"거래량은 {volume:,}개입니다."
        else:
            output = []
            for result in results:
                company = result.get('company_name', '')
                volume = result.get('Volume', 0)
                output.append(f"{company}: {volume:,}개")
            return "\n".join(output)
    
    def _format_price_output(self, user_query: str, results: List[Dict]) -> str:
        """Format price data as 00,000원"""
        if len(results) == 1:
            company = results[0].get('company_name', '')
            price = results[0].get('Close', 0)
            return f"{company}의 가격은 {price:,.0f}원입니다."
        else:
            # Extract context from query
            context = self._extract_context(user_query)
            companies = []
            for result in results:
                company = result.get('company_name', '')
                if company:
                    companies.append(company)
            
            if context:
                return f"{context} {', '.join(companies)}입니다."
            else:
                return f"{', '.join(companies)}입니다."
    
    def _format_company_output(self, results: List[Dict]) -> str:
        """Format company data as comma-separated list"""
        companies = []
        for result in results:
            company = result.get('company_name', '')
            if company:
                companies.append(company)
        
        if companies:
            return f"{', '.join(companies)}입니다."
        else:
            return "조회된 회사가 없습니다."
    
    def _extract_context(self, user_query: str) -> str:
        """Extract context from user query for formatting"""
        query_lower = user_query.lower()
        
        # Extract date
        date_match = None
        for part in user_query.split():
            if any(char in part for char in ['-', '2024', '2025']):
                date_match = part
                break
        
        # Extract market
        market = ""
        if "kospi" in query_lower:
            market = "KOSPI"
        elif "kosdaq" in query_lower:
            market = "KOSDAQ"
        
        # Extract criteria
        criteria = ""
        if "가장 비싼" in query_lower or "최고가" in query_lower:
            criteria = "가장 비싼"
        elif "상승률" in query_lower:
            criteria = "상승률 높은"
        elif "하락률" in query_lower:
            criteria = "하락률 높은"
        elif "거래량" in query_lower:
            criteria = "거래량 많은"
        
        # Extract count
        count = ""
        if "3개" in query_lower:
            count = "3개"
        elif "5개" in query_lower:
            count = "5개"
        elif "10개" in query_lower:
            count = "10개"
        
        # Build context
        context_parts = []
        if date_match:
            context_parts.append(date_match)
        if market:
            context_parts.append(f"{market}에서")
        if criteria:
            context_parts.append(criteria)
        if count:
            context_parts.append(f"종목 {count}는")
        else:
            context_parts.append("종목은")
        
        return " ".join(context_parts) if context_parts else ""