"""
Daily Stock Price Update System
매일 주가 데이터를 업데이트하는 시스템
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
from sqlalchemy import create_engine
import mysql.connector
from mysql.connector import Error
import time
import os
from config.config import Config


class DailyStockUpdater:
    """매일 주가 데이터를 업데이트하는 클래스"""
    
    def __init__(self):
        self.config = Config()
        self.logger = self._setup_logger()
        self.engine = self._create_engine()
        self.connection = None
        self.tickers_df = None
        
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger('DailyStockUpdater')
        logger.setLevel(logging.INFO)
        
        # 파일 핸들러
        file_handler = logging.FileHandler('logs/daily_update.log')
        file_handler.setLevel(logging.INFO)
        
        # 콘솔 핸들러
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 포맷터
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def _create_engine(self):
        """SQLAlchemy 엔진 생성"""
        try:
            connection_string = (
                f"mysql+pymysql://{self.config.MYSQL_USER}:{self.config.MYSQL_PASSWORD}@"
                f"{self.config.MYSQL_HOST}:{self.config.MYSQL_PORT}/{self.config.MYSQL_DATABASE}"
            )
            return create_engine(connection_string)
        except Exception as e:
            self.logger.error(f"엔진 생성 실패: {e}")
            return None
    
    def _connect_mysql(self):
        """MySQL 연결"""
        try:
            self.connection = mysql.connector.connect(
                host=self.config.MYSQL_HOST,
                port=self.config.MYSQL_PORT,
                user=self.config.MYSQL_USER,
                password=self.config.MYSQL_PASSWORD,
                database=self.config.MYSQL_DATABASE
            )
            if self.connection.is_connected():
                self.logger.info("MySQL 데이터베이스 연결 성공")
        except Error as e:
            self.logger.error(f"MySQL 연결 실패: {e}")
            raise e
    
    def load_tickers(self) -> pd.DataFrame:
        """KRX 종목 코드 로드"""
        try:
            # 데이터베이스에서 종목 코드 가져오기
            query = "SELECT ticker, company_name FROM krx_tickers"
            self.tickers_df = pd.read_sql(query, self.engine)
            
            if self.tickers_df.empty:
                # 파일에서 종목 코드 가져오기 (fallback)
                self.tickers_df = pd.read_csv("data/stock/krx_tickers.csv")
                self.tickers_df.rename(columns={"회사명": "company_name"}, inplace=True)
            
            self.logger.info(f"종목 코드 로드 완료: {len(self.tickers_df)}개 종목")
            return self.tickers_df
            
        except Exception as e:
            self.logger.error(f"종목 코드 로드 실패: {e}")
            raise e
    
    def get_latest_date_in_db(self) -> Optional[str]:
        """데이터베이스에서 최신 날짜 조회"""
        try:
            query = "SELECT max(date) as latest_date FROM krx_stockprice"
            result = pd.read_sql(query, self.engine)
            latest_date = result['latest_date'].iloc[0]
            
            if latest_date:
                return latest_date.strftime('%Y-%m-%d')
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"최신 날짜 조회 실패: {e}")
            return None
    
    def fetch_stock_data(self, ticker: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """개별 종목 데이터 가져오기"""
        try:
            # yfinance를 사용하여 데이터 가져오기
            stock = yf.Ticker(ticker)
            df = stock.history(start=start_date, end=end_date)
            
            if df.empty:
                return None
            
            # 데이터 정리
            df = df.reset_index()
            df['ticker'] = ticker
            df['Date'] = pd.to_datetime(df['Date']).dt.date
            
            # 컬럼 이름 정리
            df.rename(columns={
                'Date': 'date',
                'Open': 'open',
                'High': 'high', 
                'Low': 'low',
                'close': 'close',
                'volume': 'volume',
                'Adj close': 'adj_close'
            }, inplace=True)
            
            # 필요한 컬럼만 선택
            df = df[['date', 'open', 'high', 'low', 'close', 'volume', 'adj_close', 'ticker']]
            
            return df
            
        except Exception as e:
            self.logger.warning(f"종목 {ticker} 데이터 가져오기 실패: {e}")
            return None
    
    def fetch_all_stocks_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """모든 종목 데이터 가져오기"""
        all_data = []
        total_tickers = len(self.tickers_df)
        
        self.logger.info(f"데이터 수집 시작: {start_date} ~ {end_date}")
        
        for idx, row in self.tickers_df.iterrows():
            ticker = row['ticker']
            company_name = row['company_name']
            
            # 진행률 표시
            if idx % 50 == 0:
                self.logger.info(f"진행률: {idx}/{total_tickers} ({idx/total_tickers*100:.1f}%)")
            
            # 데이터 가져오기
            stock_data = self.fetch_stock_data(ticker, start_date, end_date)
            
            if stock_data is not None:
                stock_data['company_name'] = company_name
                all_data.append(stock_data)
            
            # API 호출 제한을 위한 딜레이
            time.sleep(0.1)
        
        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            self.logger.info(f"데이터 수집 완료: {len(combined_df)}개 레코드")
            return combined_df
        else:
            self.logger.warning("수집된 데이터가 없습니다.")
            return pd.DataFrame()
    
    def compute_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """기술적 지표 계산 (기존 upload.py 코드 참조)"""
        if df.empty:
            return df
        
        self.logger.info("기술적 지표 계산 시작")
        
        # 날짜순 정렬
        df = df.sort_values(by=["ticker", "Date"]).copy()
        
        # 등락률 계산
        df["price_change_pct"] = df.groupby("ticker")["close"].pct_change() * 100
        df["volume_change_pct"] = df.groupby("ticker")["volume"].pct_change() * 100
        
        # 이동평균선
        df["ma_5"] = df.groupby("ticker")["close"].transform(lambda x: x.rolling(5).mean())
        df["ma_20"] = df.groupby("ticker")["close"].transform(lambda x: x.rolling(20).mean())
        df["ma_60"] = df.groupby("ticker")["close"].transform(lambda x: x.rolling(60).mean())
        
        # 거래량 평균
        df["ma_VOL_20"] = df.groupby("ticker")["volume"].transform(lambda x: x.rolling(20).mean())
        df["volume_Ratio_20"] = df["volume"] / (df["ma_VOL_20"] + 1e-6)
        
        # RSI 계산
        def calc_rsi(series, period=14):
            delta = series.diff()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            avg_gain = gain.rolling(period).mean()
            avg_loss = loss.rolling(period).mean()
            rs = avg_gain / (avg_loss + 1e-6)
            return 100 - (100 / (1 + rs))
        
        df["rsi_14"] = df.groupby("ticker")["close"].transform(calc_rsi)
        
        # bollinger Bands
        ma20 = df["ma_20"]
        std20 = df.groupby("ticker")["close"].transform(lambda x: x.rolling(20).std())
        df["bollinger_upper"] = ma20 + 2 * std20
        df["bollinger_lower"] = ma20 - 2 * std20
        df["bollinger_mid"] = ma20
        
        # 볼린저 밴드 시그널
        df["signal_bollinger_upper"] = df["close"] > df["bollinger_upper"]
        df["signal_bollinger_lower"] = df["close"] < df["bollinger_lower"]
        
        # 골든/데드 크로스
        df["ma_diff"] = df["ma_5"] - df["ma_20"]
        df["prev_diff"] = df.groupby("ticker")["ma_diff"].shift(1)
        df["golden_cross"] = (df["prev_diff"] < 0) & (df["ma_diff"] > 0)
        df["dead_cross"] = (df["prev_diff"] > 0) & (df["ma_diff"] < 0)
        
        # 무한값 처리
        df = df.replace([np.inf, -np.inf], np.nan)
        
        self.logger.info("기술적 지표 계산 완료")
        return df
    
    def save_to_database(self, df: pd.DataFrame):
        """데이터베이스에 저장"""
        try:
            if df.empty:
                self.logger.warning("저장할 데이터가 없습니다.")
                return
            
            # 날짜 컬럼 형식 변환
            df['date'] = pd.to_datetime(df['date'])
            
            # 데이터베이스에 저장
            df.to_sql("krx_stockprice", con=self.engine, if_exists="append", index=False)
            
            self.logger.info(f"데이터베이스 저장 완료: {len(df)}개 레코드")
            
        except Exception as e:
            self.logger.error(f"데이터베이스 저장 실패: {e}")
            raise e
    
    def get_update_date_range(self) -> tuple:
        """업데이트할 날짜 범위 계산"""
        latest_date = self.get_latest_date_in_db()
        today = datetime.now().date()
        
        if latest_date:
            # 최신 날짜 다음날부터 오늘까지
            start_date = (datetime.strptime(latest_date, '%Y-%m-%d') + timedelta(days=1)).date()
        else:
            # 데이터가 없으면 30일 전부터
            start_date = today - timedelta(days=30)
        
        # 시작일이 오늘 이후면 업데이트 불필요
        if start_date > today:
            return None, None
        
        return start_date.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')
    
    def update_daily_data(self):
        """매일 주가 데이터 업데이트"""
        try:
            self.logger.info("=== 매일 주가 데이터 업데이트 시작 ===")
            
            # 1. 종목 코드 로드
            self.load_tickers()
            
            # 2. 업데이트 날짜 범위 계산
            start_date, end_date = self.get_update_date_range()
            
            if not start_date:
                self.logger.info("업데이트할 데이터가 없습니다.")
                return
            
            self.logger.info(f"업데이트 날짜 범위: {start_date} ~ {end_date}")
            
            # 3. 데이터 수집
            stock_data = self.fetch_all_stocks_data(start_date, end_date)
            
            if stock_data.empty:
                self.logger.warning("수집된 데이터가 없습니다.")
                return
            
            # 4. 기술적 지표 계산
            stock_data = self.compute_technical_indicators(stock_data)
            
            # 5. 데이터베이스에 저장
            self.save_to_database(stock_data)
            
            self.logger.info("=== 매일 주가 데이터 업데이트 완료 ===")
            
        except Exception as e:
            self.logger.error(f"업데이트 실패: {e}")
            raise e
    
    def force_update_all_data(self, days: int = 30):
        """전체 데이터 강제 업데이트"""
        try:
            self.logger.info(f"=== 전체 데이터 강제 업데이트 시작 ({days}일) ===")
            
            # 1. 종목 코드 로드
            self.load_tickers()
            
            # 2. 날짜 범위 설정
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=days)
            
            # 3. 기존 데이터 삭제
            if self.engine:
                with self.engine.connect() as conn:
                    conn.execute(f"DELETE FROM krx_stockprice WHERE Date >= '{start_date}'")
                    conn.commit()
            
            # 4. 데이터 수집
            stock_data = self.fetch_all_stocks_data(
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d')
            )
            
            if stock_data.empty:
                self.logger.warning("수집된 데이터가 없습니다.")
                return
            
            # 5. 기술적 지표 계산
            stock_data = self.compute_technical_indicators(stock_data)
            
            # 6. 데이터베이스에 저장
            self.save_to_database(stock_data)
            
            self.logger.info("=== 전체 데이터 강제 업데이트 완료 ===")
            
        except Exception as e:
            self.logger.error(f"강제 업데이트 실패: {e}")
            raise e
    
    def close_connection(self):
        """연결 종료"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            self.logger.info("MySQL 연결 종료")
        
        if self.engine:
            self.engine.dispose()
            self.logger.info("엔진 종료")


def main():
    """메인 실행 함수"""
    # 로그 디렉토리 생성
    os.makedirs("logs", exist_ok=True)
    
    updater = DailyStockUpdater()
    
    try:
        # 매일 업데이트 실행
        updater.update_daily_data()
        
    except Exception as e:
        print(f"업데이트 실패: {e}")
        return 1
    
    finally:
        updater.close_connection()
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())