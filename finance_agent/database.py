"""
Database manager for krx_stockprice table
"""

import mysql.connector
from mysql.connector import Error
from typing import List, Dict, Optional, Any
import pandas as pd
from config.config import Config


class Databasemanager:
    """Database manager for executing SQL queries against krx_stockprice table"""
    
    def __init__(self):
        self.config = Config()
        self.connection = None
        self.connect()
    
    def connect(self):
        """Establish connection to MySQL database"""
        try:
            self.connection = mysql.connector.connect(
                host=self.config.MYSQL_HOST,
                port=self.config.MYSQL_PORT,
                user=self.config.MYSQL_USER,
                password=self.config.MYSQL_PASSWORD,
                database=self.config.MYSQL_DATABASE
            )
            if self.connection.is_connected():
                print("Connected to MySQL database")
        except Error as e:
            print(f"Error connecting to MySQL: {e}")
            raise e
    
    def execute_query(self, query: str, params: Optional[List] = None) -> List[Dict]:
        """Execute SQL query and return results as list of dictionaries"""
        if not self.connection or not self.connection.is_connected():
            self.connect()
        
        cursor = self.connection.cursor(dictionary=True)
        
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            results = cursor.fetchall()
            
            # Convert any Decimal or datetime objects to appropriate types
            formatted_results = []
            for row in results:
                formatted_row = {}
                for key, value in row.items():
                    if hasattr(value, 'strftime'):  # datetime objects
                        formatted_row[key] = value.strftime('%Y-%m-%d')
                    elif hasattr(value, '__float__'):  # Decimal objects
                        formatted_row[key] = float(value)
                    else:
                        formatted_row[key] = value
                formatted_results.append(formatted_row)
            
            return formatted_results
            
        except Error as e:
            print(f"Error executing query: {e}")
            raise e
        finally:
            cursor.close()
    
    def execute_query_single(self, query: str, params: Optional[List] = None) -> Optional[Dict]:
        """Execute query and return single result"""
        results = self.execute_query(query, params)
        return results[0] if results else None
    
    def get_table_schema(self) -> str:
        """Get krx_stockprice table schema information"""
        query = """
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_COMMENT
        FROM INFORmaTION_SCHEma.COLUMNS
        WHERE TABLE_SCHEma = %s AND TABLE_NAME = 'krx_stockprice'
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
        - ma_5, ma_20, ma_60: 5일, 20일, 60일 단순 이동평균선
        - ma_VOL_20: 20일 거래량 평균
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
        """Test database connection"""
        try:
            test_query = "SELECT 1"
            result = self.execute_query(test_query)
            return len(result) > 0
        except:
            return False
    
    def get_sample_data(self, limit: int = 5) -> List[Dict]:
        """Get sample data from krx_stockprice table"""
        query = f"""
        SELECT *
        FROM krx_stockprice
        ORDER BY Date DESC
        LIMIT {limit}
        """
        
        try:
            return self.execute_query(query)
        except Exception as e:
            print(f"Error getting sample data: {e}")
            return []
    
    def get_companies_by_name(self, name_pattern: str) -> List[Dict]:
        """Get companies matching name pattern"""
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
        """Get available dates in the database"""
        query = f"""
        SELECT DISTINCT Date
        FROM krx_stockprice
        ORDER BY Date DESC
        LIMIT {limit}
        """
        
        try:
            results = self.execute_query(query)
            return [row['Date'] for row in results]
        except Exception as e:
            print(f"Error getting available dates: {e}")
            return []
    
    def validate_query(self, query: str) -> bool:
        """Validate SQL query syntax"""
        try:
            # Basic validation: check if it's a SELECT statement
            query_upper = query.upper().strip()
            
            # Only allow SELECT statements
            if not query_upper.startswith('SELECT'):
                return False
            
            # Check for potentially dangerous keywords
            dangerous_keywords = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE', 'TRUNCATE']
            for keyword in dangerous_keywords:
                if keyword in query_upper:
                    return False
            
            # Try to prepare the statement
            if self.connection and self.connection.is_connected():
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
            
        except Exception as e:
            print(f"Error validating query: {e}")
            return False
    
    def close_connection(self):
        """Close database connection"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            print("Database connection closed")
    
    def __del__(self):
        """Cleanup on object destruction"""
        self.close_connection()