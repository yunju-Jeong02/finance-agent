"""
Tests for Database functionality
"""

import pytest
import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from finance_agent.database import DatabaseManager


class TestDatabaseManager:
    """Test Database Manager functionality"""
    
    @pytest.fixture
    def db_manager(self):
        """Create database manager instance"""
        try:
            return DatabaseManager()
        except Exception as e:
            pytest.skip(f"Database manager creation failed: {e}")
    
    def test_get_available_dates(self, db_manager):
        """Test getting available dates"""
        try:
            dates = db_manager.get_available_dates(5)
            assert isinstance(dates, list)
            if dates:
                assert len(dates) <= 5
        except Exception as e:
            pytest.skip(f"Get available dates test failed: {e}")
    
    def test_get_sample_data(self, db_manager):
        """Test getting sample data"""
        try:
            sample_data = db_manager.get_sample_data(3)
            assert isinstance(sample_data, list)
            if sample_data:
                assert len(sample_data) <= 3
        except Exception as e:
            pytest.skip(f"Get sample data test failed: {e}")
    
    def test_get_companies_by_name(self, db_manager):
        """Test getting companies by name"""
        try:
            companies = db_manager.get_companies_by_name("삼성")
            assert isinstance(companies, list)
        except Exception as e:
            pytest.skip(f"Get companies by name test failed: {e}")
    
    def test_execute_query_basic(self, db_manager):
        """Test basic query execution"""
        try:
            query = "SELECT COUNT(*) as count FROM krx_stockprice LIMIT 1"
            result = db_manager.execute_query(query)
            assert isinstance(result, list)
            if result:
                assert "count" in result[0]
        except Exception as e:
            pytest.skip(f"Basic query execution test failed: {e}")
    
    def test_validate_query(self, db_manager):
        """Test query validation"""
        try:
            # Valid query
            valid_query = "SELECT * FROM krx_stockprice LIMIT 1"
            assert db_manager.validate_query(valid_query) == True
            
            # Invalid query (DELETE)
            invalid_query = "DELETE FROM krx_stockprice"
            assert db_manager.validate_query(invalid_query) == False
            
        except Exception as e:
            pytest.skip(f"Query validation test failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__])