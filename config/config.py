import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    CLOVA_HOST = os.getenv("CLOVA_HOST", "clovastudio.apigw.ntruss.com")
    CLOVA_API_KEY = os.getenv("CLOVA_API_KEY", "your-api-key")

    MYSQL_HOST = os.getenv("MYSQL_HOST")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT"))
    MYSQL_USER = os.getenv("MYSQL_USER")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "finance_db")
    MYSQL_DATABASE2 = os.getenv("MYSQL_DATABASE2", "news_DB")

    
    # Yahoo Finance settings
    YFINANCE_MAX_RETRIES = 3
    YFINANCE_TIMEOUT = 10
    
    # LangGraph settings
    MAX_ITERATIONS = 10
    TEMPERATURE = 0.1