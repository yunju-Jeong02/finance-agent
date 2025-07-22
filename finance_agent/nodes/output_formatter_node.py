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
        if not results:
            return "조회된 데이터가 없습니다."
        
        columns = list(results[0].keys())
        header = " | ".join(columns)
        sep = "-|-".join(['-' * len(col) for col in columns])
        rows = [" | ".join(str(row.get(col, "")) for col in columns) for row in results]
        table = f"{header}\n{sep}\n" + "\n".join(rows)
        
        return f"\n [결과]\n{table}"