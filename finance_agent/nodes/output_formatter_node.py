import pandas as pd
from typing import Dict, List


COLUMN_NAME_MAPPING = {
    "ticker": "회사명",
    "open": "시가",
    "close": "종가",
    "high": "고가",
    "low": "저가",
    "adj_close": "수정 종가",
    "volume": "거래량",
    "price_change_pct": "등락률 (%)",
    "volume_change_pct": "거래량 변화율 (%)",
    "ma_5": "5일 이동평균",
    "ma_20": "20일 이동평균",
    "ma_60": "60일 이동평균",
    "ma_vol_20": "20일 평균 거래량",
    "volume_ratio_20": "거래량 비율 (20일 평균 대비)",
    "rsi_14": "RSI (14일)",
    "signal_bollinger_upper": "볼린저 상단 돌파",
    "signal_bollinger_lower": "볼린저 하단 돌파",
    "golden_cross": "골든크로스",
    "dead_cross": "데드크로스",
}

class OutputFormatterNode:    
    def __init__(self):
        self.company_df = pd.read_csv("./data/stock/krx_tickers.csv")
    
    def process(self, state: Dict) -> Dict:
        user_query = state["user_query"]
        results = state["query_results"]
        
        if not results:
            state["final_output"] = "조건에 맞는 데이터가 없습니다."
            state["is_complete"] = True
            return state
        
        formatted_output = self._format_output(user_query, results)
        state["final_output"] = formatted_output
        state["is_complete"] = True
        return state
    

    def _format_output(self, user_query: str, results: List[Dict]) -> str:
        if not results:
            return "조건에 맞는 데이터가 없습니다."
        
        columns = list(results[0].keys())

        ticker_to_name = {}
        if "ticker" in columns:
            ticker_to_name = {row["ticker"]: row["company_name"] for _, row in self.company_df.iterrows()}

        output_lines = []
        for i, row in enumerate(results, start=1):
            line_parts = []
            for col in columns:
                val = row[col]
                label = COLUMN_NAME_MAPPING.get(col, col)

                # 종목명
                if col == "ticker":
                    company_name = ticker_to_name.get(val, val)
                    line_parts.append(f"{label}: {company_name}")

                # 가격 관련
                elif col in {"open", "close", "high", "low", "adj_close"}:
                    line_parts.append(f"{label}: {val:,.0f}원" if val is not None else f"{label}: -")

                # 거래량
                elif col == "volume":
                    line_parts.append(f"{label}: {val:,}주" if val is not None else f"{label}: -")

                # 퍼센트 또는 비율
                elif "pct" in col or "ratio" in col:
                    line_parts.append(f"{label}: {val:.2f}" if val is not None else f"{label}: -")

                elif "count" in col:
                    line_parts.append(f"{label}: {val:,.0f}개" if val is not None else f"{label}: -")

                # 기타
                else:
                    line_parts.append(f"{label}: {val}")
            
            output_lines.append(f"{i}. " + " / ".join(line_parts))
        
        return "\n".join(output_lines)