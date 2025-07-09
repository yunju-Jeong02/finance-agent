"""
Finance Agent Package
한국 주식 시장 데이터 분석 에이전트
"""

from .agent import FinanceAgent, FinanceAgentInterface
from .database import DatabaseManager
from .updater import DailyStockUpdater

__version__ = "2.0.0"
__author__ = "Finance Agent Team"

__all__ = [
    "FinanceAgent",
    "FinanceAgentInterface", 
    "DatabaseManager",
    "DailyStockUpdater"
]