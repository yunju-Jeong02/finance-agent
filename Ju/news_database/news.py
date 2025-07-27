from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import pandas as pd
import pymysql
from sqlalchemy import create_engine

DB_CONFIG = {
    'host': 'miraeasset-database-1.c5w8cg8kau54.ap-northeast-2.rds.amazonaws.com',
    'user': 'admin',
    'password': 'miraeasset25!',
    'port': 3306,
    'database': 'news_DB',
    'charset': 'utf8mb4'
}

COUNT_MAP = {
    '09': 1500,
    '12': 1250,
    '15': 1250,
    '18': 1000
}

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2025, 7, 18),
}

def crawl_naver_news(max_count):
    collected = []
    page = 1
    base_url = "https://search.naver.com/search.naver?where=news&query=경제&sort=1&sm=tab_pge&start="
    while len(collected) < max_count:
        start = 1 + (page - 1) * 10
        url = f"{base_url}{start}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        news_items = soup.select("div.news_wrap.api_ani_send")

        if not news_items:
            break

        for item in news_items:
            title_tag = item.select_one("a.news_tit")
            if not title_tag:
                continue
            title = title_tag.get('title')
            link = title_tag.get('href')
            date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            collected.append([date, title, link])
            if len(collected) >= max_count:
                break
        page += 1

    df = pd.DataFrame(collected, columns=["date", "title", "link"])
    return df

def update_database(**context):
    execution_hour = context['execution_date'].strftime('%H')
    max_count = COUNT_MAP.get(execution_hour, 0)
    if max_count == 0:
        print(f"No crawling scheduled at hour {execution_hour}")
        return

    print(f"Starting crawl for {max_count} articles at hour {execution_hour}")
    df = crawl_naver_news(max_count)
    if df.empty:
        print("No articles found")
        return

    # DB 연결 및 테이블 생성
    conn = pymysql.connect(**DB_CONFIG)
    with conn.cursor() as cursor:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS News (
            id INT AUTO_INCREMENT PRIMARY KEY,
            date VARCHAR(20),
            title TEXT,
            link TEXT,
            UNIQUE KEY unique_link (link(255))
        ) CHARACTER SET utf8mb4;
        """)
    conn.commit()

    # SQLAlchemy 엔진 생성
    engine = create_engine(
        f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )

    # 중복 삽입 무시하고 데이터 삽입
    df.to_sql('News', con=engine, if_exists='append', index=False, method='multi')

    # 최신 5000개 초과 삭제 (오래된 뉴스 삭제)
    with conn.cursor() as cursor:
        delete_sql = """
        DELETE FROM News
        WHERE id NOT IN (
            SELECT id FROM (
                SELECT id FROM News ORDER BY date DESC LIMIT 5000
            ) AS latest
        );
        """
        cursor.execute(delete_sql)
    conn.commit()
    conn.close()
    print(f"DB update completed at hour {execution_hour}")

with DAG(
    dag_id='naver_news_scraping',
    default_args=default_args,
    schedule_interval='0 9,12,15,18 * * *',
    catchup=False,
    tags=['naver', 'news', 'scraping']
) as dag:

    update_db_task = PythonOperator(
        task_id='crawl_and_update_db',
        python_callable=update_database,
        provide_context=True
    )

