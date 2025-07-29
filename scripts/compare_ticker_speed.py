import pandas as pd
import time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from finance_agent.database import DatabaseManager

def load_tickers_from_csv(csv_path):
    start = time.time()
    df = pd.read_csv(csv_path)
    tickers = df['ticker'].unique().tolist()  # 'ticker' 컬럼명 확인!
    end = time.time()
    print(f"[CSV] ticker 개수: {len(tickers)} | 소요 시간: {end - start:.4f}초")
    return tickers

def load_tickers_from_db():
    db = DatabaseManager(db_type="finance")
    query = "SELECT DISTINCT ticker FROM krx_stockprice"
    start = time.time()
    results = db.execute_query(query)
    tickers = [row["ticker"] for row in results]
    end = time.time()
    print(f"[DB] ticker 개수: {len(tickers)} | 소요 시간: {end - start:.4f}초")
    return tickers

if __name__ == "__main__":
    csv_path = "data/krx_tickers.csv"  # 필요시 경로 수정
    csv_tickers = load_tickers_from_csv(csv_path)
    db_tickers = load_tickers_from_db()

    # 추가 비교 (선택)
    overlap = set(csv_tickers) & set(db_tickers)
    only_in_csv = set(csv_tickers) - set(db_tickers)
    only_in_db = set(db_tickers) - set(csv_tickers)

    print(f"✔️ 공통 ticker 수: {len(overlap)}")
    print(f"📁 CSV에만 있는 ticker 수: {len(only_in_csv)}")
    print(f"🗄️ DB에만 있는 ticker 수: {len(only_in_db)}")