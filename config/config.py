import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    HYPERCLOVA_API_KEY = os.getenv("HYPERCLOVA_API_KEY")
    HYPERCLOVA_REQUEST_KEY = os.getenv("HYPERCLOVA_REQUEST_KEY")

    MYSQL_HOST = os.getenv("MYSQL_HOST")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT"))
    MYSQL_USER = os.getenv("MYSQL_USER")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "finance_db")
    
    # Yahoo Finance settings
    YFINANCE_MAX_RETRIES = 3
    YFINANCE_TIMEOUT = 10
    
    # LangGraph settings
    MAX_ITERATIONS = 10
    TEMPERATURE = 0.1