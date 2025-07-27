import pandas as pd
import pymysql
from typing import Dict, List
from config.config import Config

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
        self.company_df = self.load_krx_tickers_from_db()

    def load_krx_tickers_from_db(self) -> pd.DataFrame:
        try:
            conn = pymysql.connect(
                host=Config.MYSQL_HOST,
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD,
                database=Config.MYSQL_DATABASE,
                port=Config.MYSQL_PORT,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            df = pd.read_sql("SELECT company_name, ticker FROM krx_tickers", conn)
            conn.close()
            return df
        except Exception as e:
            print(f"[OutputFormatterNode] DB Load Error: {e}")
            return pd.DataFrame(columns=["company_name", "ticker"])

    def process(self, state: Dict) -> Dict:
        
        # SQL 결과를 포맷팅하거나, 뉴스 요약(intent)이면 그대로 반환.
        
        # 뉴스 요약인 경우 포맷터는 건너뛴다.
        if state.get("parsed_query", {}).get("intent", "").endswith("_news_request") or \
           state.get("parsed_query", {}).get("intent", "").endswith("_summary_request"):
            # final_output은 SqlGeneratorNode에서 이미 채워짐
            state["is_complete"] = True
            return state

        # 주식 데이터 쿼리 결과 포맷팅
        results = state.get("query_results", [])
        if not results:
            state["final_output"] = "조건에 맞는 데이터가 없습니다."
            state["is_complete"] = True
            return state

        formatted_output = self._format_output(state["user_query"], results)
        state["final_output"] = formatted_output
        state["is_complete"] = True
        return state

    def _format_output(self, user_query: str, results: List[Dict]) -> str:
        if not results:
            return "조건에 맞는 데이터가 없습니다."

        columns = list(results[0].keys())
        ticker_to_name = {}
        if "ticker" in columns:
            ticker_to_name = dict(zip(self.company_df["ticker"], self.company_df["company_name"]))

        output_lines = []
        for i, row in enumerate(results, start=1):
            line_parts = []
            for col in columns:
                val = row[col]
                label = COLUMN_NAME_MAPPING.get(col, col)

                if col == "ticker":
                    company_name = ticker_to_name.get(val, val)
                    line_parts.append(f"{label}: {company_name}")
                elif col in {"open", "close", "high", "low", "adj_close"}:
                    line_parts.append(f"{label}: {val:,.0f}원" if val is not None else f"{label}: -")
                elif col == "volume":
                    line_parts.append(f"{label}: {val:,}주" if val is not None else f"{label}: -")
                elif "pct" in col or "ratio" in col:
                    line_parts.append(f"{label}: {val:.2f}" if val is not None else f"{label}: -")
                elif "count" in col:
                    line_parts.append(f"{label}: {val:,.0f}개" if val is not None else f"{label}: -")
                else:
                    line_parts.append(f"{label}: {val}")

            output_lines.append(f"{i}. " + " / ".join(line_parts))

        return "\n".join(output_lines)