from sqlalchemy import create_engine
from datetime import datetime
import pandas as pd
from main_news_crawler import get_economy_news_by_date, DB_CONFIG  # DAG와 같은 경로에 모듈로 저장했다고 가정

def get_engine():
    return create_engine(
        f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )

if __name__ == "__main__":
    engine = get_engine()
    test_date = "20250730"
    # 30개만 수집해서 삽입 (삭제 로직 없음)
    df = get_economy_news_by_date(test_date, max_page=5).head(30)
    if not df.empty:
        df.to_sql('News', con=engine, if_exists='append', index=False)
        print(f"[TEST] {len(df)}개 {test_date} 뉴스 DB 삽입 완료")
    else:
        print("[TEST] 수집된 뉴스 없음")