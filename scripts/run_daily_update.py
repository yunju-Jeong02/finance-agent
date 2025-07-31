"""
Daily Stock Update Runner
매일 주가 데이터 업데이트를 실행하는 스크립트
"""

import sys
import os
import argparse
from datetime import datetime

# 프로젝트 루트 디렉터리를 Python path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from finance_agent.updater import DailyStockUpdater


def run_daily_update():
    """매일 업데이트 실행"""
    print("=== 매일 주가 데이터 업데이트 시작 ===")
    print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    updater = DailyStockUpdater()
    
    try:
        updater.update_daily_data()  # 내부에서 start_date, end_date 정상 처리
        print("✓ 업데이트 완료!")
        return 0
        
    except Exception as e:
        print(f"✗ 업데이트 실패: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        updater.close_connection()


def run_force_update(days: int = 30):
    """전체 데이터 강제 업데이트"""
    print(f"=== 전체 데이터 강제 업데이트 시작 ({days}일) ===")
    print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    updater = DailyStockUpdater()
    
    try:
        updater.force_update_all_data(days)
        print("✓ 강제 업데이트 완료!")
        return 0
        
    except Exception as e:
        print(f"✗ 강제 업데이트 실패: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        updater.close_connection()


def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(description='주가 데이터 업데이트 스크립트')
    parser.add_argument('--mode', choices=['daily', 'force'], default='daily',
                       help='업데이트 모드 (daily: 매일 업데이트, force: 강제 전체 업데이트)')
    parser.add_argument('--days', type=int, default=30,
                       help='강제 업데이트 시 가져올 일수 (기본: 30일)')
    
    args = parser.parse_args()
    
    if args.mode == 'daily':
        return run_daily_update()
    elif args.mode == 'force':
        return run_force_update(args.days)


if __name__ == "__main__":
    sys.exit(main())
