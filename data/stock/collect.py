from tqdm import tqdm
import yfinance as yf
import pandas as pd
import time

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text

from config.config import Config
MYSQL_URI = f"mysql+pymysql://{Config.MYSQL_USER}:{Config.MYSQL_PASSWORD}@{Config.MYSQL_HOST}:{Config.MYSQL_PORT}/{Config.MYSQL_DATABASE}"

ticker_df = pd.read_csv('./data/stock/krx_tickers.csv')
tickers = ticker_df['ticker'].tolist() 
tickers = list(set(tickers)) # 중복제거

combined = []

df = yf.download(tickers, period="5y", interval="1d", auto_adjust=False)

df_tidy = df.stack(level=1, future_stack=True).reset_index()
df_tidy = df_tidy.rename(columns={"Ticker": "ticker",
                                  "Date": "date",
                                  "Adj Close": "adj_close",
                                  "Close": "close",
                                  "High": "high",
                                  "Low": "low",
                                  "Open": "open",
                                  "Volume": "volume"
                                })
df_tidy.columns = ['date', 'ticker', 'adj_close', 'close', 'high', 'low', 'open', 'volume']

def compute_technical_indicators( df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
        
    # 날짜순 정렬
    df = df.sort_values(by=["ticker", "date"]).copy()
    
    # 등락률 계산
    df["price_change_pct"] = df.groupby("ticker")["adj_close"].pct_change() * 100
    df["volume_change_pct"] = df.groupby("ticker")["volume"].pct_change() * 100
    
    # 이동평균선
    df["ma_5"] = df.groupby("ticker")["adj_close"].transform(lambda x: x.rolling(5).mean())
    df["ma_20"] = df.groupby("ticker")["adj_close"].transform(lambda x: x.rolling(20).mean())
    df["ma_60"] = df.groupby("ticker")["adj_close"].transform(lambda x: x.rolling(60).mean())
    
    # 거래량 평균
    df["ma_vol_20"] = df.groupby("ticker")["volume"].transform(lambda x: x.rolling(20).mean())
    df["volume_ratio_20"] = df["volume"] / (df["ma_vol_20"] + 1e-6)
    
    # RSI 계산
    def calc_rsi(series, period=14):
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()
        rs = avg_gain / (avg_loss + 1e-6)
        return 100 - (100 / (1 + rs))
    
    df["rsi_14"] = df.groupby("ticker")["adj_close"].transform(calc_rsi)
    
    # bollinger Bands
    ma20 = df["ma_20"]
    std20 = df.groupby("ticker")["adj_close"].transform(lambda x: x.rolling(20).std())
    df["bollinger_upper"] = ma20 + 2 * std20
    df["bollinger_lower"] = ma20 - 2 * std20
    df["bollinger_mid"] = ma20
    
    # 볼린저 밴드 시그널
    df["signal_bollinger_upper"] = df["adj_close"] > df["bollinger_upper"]
    df["signal_bollinger_lower"] = df["adj_close"] < df["bollinger_lower"]
    
    # 골든/데드 크로스: 20일 이동평균선에서 5일 이동평균선을 비교
    df["ma_diff"] = df["ma_5"] - df["ma_20"]
    df["prev_diff"] = df.groupby("ticker")["ma_diff"].shift(1)
    df["golden_cross"] = (df["prev_diff"] < 0) & (df["ma_diff"] > 0)
    df["dead_cross"] = (df["prev_diff"] > 0) & (df["ma_diff"] < 0)
    
    # 무한값 처리
    df = df.replace([np.inf, -np.inf], np.nan)
    return df

df_tidy = compute_technical_indicators(df_tidy)

engine = create_engine(MYSQL_URI)

# ticker_df.to_sql("krx_tickers", con=engine, if_exists="replace", index=False)
# print("Ticker Table uploaded to MySQL database successfully.")

df_tidy.to_sql("krx_stockprice", con=engine, if_exists="replace", index=False)
print("Stockprice Data uploaded to MySQL database successfully.")

