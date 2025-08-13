# finance_agent/database.py
"""
Database manager for krx_stockprice table
"""

import pymysql
from typing import List, Dict, Optional
from config.config import Config


class DatabaseManager:
    """Database manager for executing SQL queries against krx_stockprice table"""
    
    def __init__(self):
        self.config = Config()
        self.connection = None
        self.connect()
    
    def connect(self):
        """Establish connection to MySQL database"""
        try:
            self.connection = pymysql.connect(
                host=self.config.MYSQL_HOST,
                port=self.config.MYSQL_PORT,
                user=self.config.MYSQL_USER,
                password=self.config.MYSQL_PASSWORD,
                database=self.config.MYSQL_DATABASE,
                charset="utf8mb4",
            )
        except Exception as e:
            print(f"Error connecting to MySQL: {e}")
            raise e
    
    def execute_query(self, query: str, params: Optional[List] = None) -> List[Dict]:
        if not self.connection:
            self.connect()
        
        cursor = self.connection.cursor(pymysql.cursors.DictCursor)
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            results = cursor.fetchall()
            formatted = []
            for row in results:
                out = {}
                for k, v in row.items():
                    if hasattr(v, "strftime"):
                        out[k] = v.strftime("%Y-%m-%d")
                    elif hasattr(v, "__float__"):
                        out[k] = float(v)
                    else:
                        out[k] = v
                formatted.append(out)
            return formatted
        except Exception as e:
            raise e
        finally:
            cursor.close()
    
    def execute_query_single(self, query: str, params: Optional[List] = None) -> Optional[Dict]:
        res = self.execute_query(query, params)
        return res[0] if res else None
    
    def get_table_schema(self) -> str:
        """Get krx_stockprice table schema information"""
        query = """
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_COMMENT
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'krx_stockprice'
        ORDER BY ORDINAL_POSITION
        """
        try:
            results = self.execute_query(query, [self.config.MYSQL_DATABASE])
            schema_info = "Table: krx_stockprice\nColumns:\n"
            for col in results:
                schema_info += f"- {col['COLUMN_NAME']} ({col['DATA_TYPE']}): {col['COLUMN_COMMENT'] or 'No comment'}\n"
            return schema_info
        except Exception as e:
            print(f"Error getting table schema: {e}")
            return self._get_default_schema()
    
    def _get_default_schema(self) -> str:
        """Return default schema if unable to fetch from database"""
        return """
        Table: krx_stockprice
        Columns:
        - date: 거래 일자 (YYYY-MM-DD)
        - adj_close: 수정 종가
        - close: 종가
        - high: 당일 최고가
        - low: 당일 최저가
        - open: 당일 시가
        - volume: 당일 거래량 (주식 수)
        - ticker: 종목 코드 (예: 005930.KS)
        - company_name: 종목의 회사명
        - price_change_pct: 전일 대비 등락률 (%)
        - volume_change_pct: 전일 대비 거래량 변화율 (%)
        - ma_5, ma_20, ma_60: 5/20/60일 단순 이동평균선
        - ma_vol_20: 20일 거래량 평균
        - volume_ratio_20: 현재 거래량 / 20일 평균 거래량
        - rsi_14: 14일 기준 RSI
        - bollinger_mid: 20일 이동평균선
        - bollinger_upper: 볼린저 상단 밴드
        - bollinger_lower: 볼린저 하단 밴드
        - signal_bollinger_upper: 종가가 상단 밴드 초과시 True
        - signal_bollinger_lower: 종가가 하단 밴드 이하시 True
        - ma_diff: ma_5 - ma_20
        - prev_diff: 전날의 ma_diff
        - golden_cross: 골든크로스 발생시 True
        - dead_cross: 데드크로스 발생시 True
        """
    
    def test_connection(self) -> bool:
        try:
            return len(self.execute_query("SELECT 1")) > 0
        except:
            return False
    
    def get_sample_data(self, limit: int = 5) -> List[Dict]:
        query = f"""
        SELECT *
        FROM krx_stockprice
        ORDER BY date DESC
        LIMIT {limit}
        """
        try:
            return self.execute_query(query)
        except Exception as e:
            print(f"Error getting sample data: {e}")
            return []
    
    def get_companies_by_name(self, name_pattern: str) -> List[Dict]:
        """DB에서 회사명 부분일치로 ticker, company_name 조회"""
        query = """
        SELECT DISTINCT ticker, company_name
        FROM krx_stockprice
        WHERE company_name LIKE %s
        ORDER BY company_name
        """
        try:
            return self.execute_query(query, [f"%{name_pattern}%"])
        except Exception as e:
            print(f"Error getting companies: {e}")
            return []
    
    def get_available_dates(self, limit: int = 10) -> List[str]:
        query = f"""
        SELECT DISTINCT date
        FROM krx_stockprice
        ORDER BY date DESC
        LIMIT {limit}
        """
        try:
            rows = self.execute_query(query)
            return [r["date"] for r in rows]
        except Exception as e:
            print(f"Error getting available dates: {e}")
            return []
    
    def validate_query(self, query: str) -> bool:
        """Validate SQL query syntax (SELECT-only)"""
        try:
            q = query.upper().strip()
            if not q.startswith("SELECT"):
                return False
            for kw in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE"]:
                if kw in q:
                    return False
            if self.connection:
                cursor = self.connection.cursor()
                try:
                    cursor.execute(f"EXPLAIN {query}")
                    cursor.fetchall()
                    return True
                except:
                    return False
                finally:
                    cursor.close()
            return True
        except:
            return False
    
    def close_connection(self):
        if self.connection:
            self.connection.close()
    
    def __del__(self):
        self.close_connection()