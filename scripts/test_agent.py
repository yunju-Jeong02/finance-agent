#!/usr/bin/env python3
"""
Finance Agent 테스트 스크립트
"""
import sys
import os

# 프로젝트 루트 디렉터리를 Python path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from finance_agent.agent import FinanceAgent

def test_agent():
    """Finance Agent 테스트"""
    agent = FinanceAgent()
    
    # 예시 질문들
    test_queries = [
        '2025-05-14에 거래량이 전날대비 300% 이상 증가한 종목을 모두 보여줘'
    ]
    
    print("Finance Agent 테스트 시작\n")
    
    for i, query in enumerate(test_queries, 1):
        print(f"[테스트 {i}] {query}")
        result = agent.process_query(query)
        print(result)

if __name__ == "__main__":
    test_agent()