#!/usr/bin/env python3
"""
Finance Agent 테스트 스크립트
"""
import sys
import os

# 프로젝트 루트 디렉터리를 Python path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.finance_agent import FinanceAgent

def test_agent():
    """Finance Agent 테스트"""
    agent = FinanceAgent()
    
    # 예시 질문들
    test_queries = [
        "삼성전자의 2024-01-01 종가는?",
        "2024-07-15 KOSPI 지수는?",
        "2024-08-16에 상승한 종목은 몇 개?",
        "최근 상승한 종목",  # 모호한 질문
        "등락률이 +5% 이상인 종목을 알려줘",
        "상승률 높은 종목 5개"
    ]
    
    print("Finance Agent 테스트 시작\n")
    
    for i, query in enumerate(test_queries, 1):
        print(f"[테스트 {i}] {query}")
        try:
            result = agent.process_query(query)
            print(f"응답: {result['response']}")
            if result.get('needs_user_input'):
                print("(재질문 필요)")
        except Exception as e:
            print(f"에러 발생: {e}")
        print("-" * 50)

if __name__ == "__main__":
    test_agent()