"""
Finance Agent 실행 스크립트
"""
import sys
import os

# 프로젝트 루트 디렉터리를 Python path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from finance_agent.agent import FinanceAgentInterface


def main():
    """Graph Framework 실행"""
    try:
        print("=== KU-gent Finance Agent 시작 ===")
        print("SQL 기반 직접 데이터베이스 쿼리를 통해 빠르고 정확한 결과를 제공합니다.\n")
        
        interface = FinanceAgentInterface()
        interface.start_conversation()
        
    except KeyboardInterrupt:
        print("\n\n Agent를 종료합니다.")
    except Exception as e:
        print(f"에러 발생: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())