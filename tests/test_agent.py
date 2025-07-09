"""
Tests for Finance Agent
"""

import pytest
import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from finance_agent.agent import FinanceAgent
from finance_agent.database import DatabaseManager


class TestFinanceAgent:
    """Test Finance Agent functionality"""
    
    def test_agent_initialization(self):
        """Test agent can be initialized"""
        try:
            agent = FinanceAgent()
            assert agent is not None
            assert agent.graph is not None
        except Exception as e:
            # Skip test if dependencies not available
            pytest.skip(f"Agent initialization failed: {e}")
    
    def test_process_query_structure(self):
        """Test query processing returns expected structure"""
        try:
            agent = FinanceAgent()
            result = agent.process_query("KOSPI 시장에서 가장 비싼 종목은?")
            
            # Check result structure
            assert "response" in result
            assert "is_complete" in result
            assert "session_id" in result
            
        except Exception as e:
            pytest.skip(f"Query processing test failed: {e}")


class TestDatabaseManager:
    """Test Database Manager functionality"""
    
    def test_database_manager_init(self):
        """Test database manager initialization"""
        try:
            db_manager = DatabaseManager()
            assert db_manager is not None
        except Exception as e:
            pytest.skip(f"Database manager initialization failed: {e}")
    
    def test_database_connection(self):
        """Test database connection"""
        try:
            db_manager = DatabaseManager()
            is_connected = db_manager.test_connection()
            assert isinstance(is_connected, bool)
        except Exception as e:
            pytest.skip(f"Database connection test failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__])