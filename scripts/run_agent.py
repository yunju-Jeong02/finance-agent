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