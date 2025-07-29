from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import pandas as pd
import time

# DB 설정
DB_CONFIG = {
    'user': 'admin',
    'password': 'miraeasset25!',
    'host': 'miraeasset-database-1.c5w8cg8kau54.ap-northeast-2.rds.amazonaws.com',
    'port': 3306,
    'database': 'news_DB'
}

# 시간대별 수집 개수
COUNT_MAP = {
    '09': 1500,
    '12': 1250,
    '15': 1250,
    '18': 1000
}

def get_engine():
    return create_engine(
        f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )

def get_economy_news_by_date(date_str, max_page=250):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=options)

    articles = []
    for page in range(1, max_page + 1):
        url = f"https://news.naver.com/main/list.naver?mode=LS2D&mid=shm&sid1=101&date={date_str}&page={page}"
        driver.get(url)
        time.sleep(1.5)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        news_list = soup.select("ul.type06_headline li") + soup.select("ul.type06 li")
        if not news_list:
            break

        for li in news_list:
            title, href = None, None
            img_tag = li.select_one("dt.photo img")
            if img_tag and img_tag.has_attr("alt"):
                title = img_tag["alt"].strip()
                a_tag = li.select_one("dt.photo a")
                if a_tag and a_tag.has_attr("href"):
                    href = a_tag["href"]

            if not title or not href:
                for a in li.select("dt a"):
                    t = a.get_text(strip=True)
                    h = a.get("href", "")
                    if t and "n.news.naver.com" in h:
                        title = t
                        href = h
                        break
            if title and href:
                articles.append({"date": date_str, "title": title, "link": href})

    driver.quit()
    return pd.DataFrame(articles)

def update_news(**kwargs):
    execution_hour = kwargs['logical_date'].strftime('%H')
    today = kwargs['logical_date'].strftime('%Y%m%d')
    count = COUNT_MAP.get(execution_hour, 0)
    if count == 0:
        print(f"[INFO] No crawl scheduled for hour {execution_hour}")
        return

    engine = get_engine()

    df = get_economy_news_by_date(today, max_page=250).head(count)
    if df.empty:
        print("[WARN] No articles found")
        return

    df.to_sql('News', con=engine, if_exists='append', index=False)
    print(f"[INFO] {len(df)}개 {today} 뉴스 DB 삽입 완료")

    with engine.begin() as conn:
        today_count = conn.execute(text("SELECT COUNT(*) FROM News WHERE date = :today"), {"today": today}).scalar()
        oldest_date = conn.execute(text("SELECT date FROM News WHERE date != :today ORDER BY date ASC LIMIT 1"), {"today": today}).scalar()

        if oldest_date:
            oldest_count = conn.execute(text("SELECT COUNT(*) FROM News WHERE date = :d"), {"d": oldest_date}).scalar()
            if today_count + oldest_count > 5000:
                conn.execute(text("DELETE FROM News WHERE date = :d"), {"d": oldest_date})
                print(f"[INFO] 오래된 날짜 {oldest_date} 삭제 (5000개 초과 방지)")

        if execution_hour == "18":
            conn.execute(text("""
                DELETE FROM News
                WHERE date < DATE_FORMAT(DATE_SUB(NOW(), INTERVAL 30 DAY), '%Y%m%d')
            """))
            print("[INFO] 30일 초과 데이터 정리 완료")

# DAG 정의
with DAG(
    dag_id="naver_economy_news_dag",
    start_date=datetime(2025, 7, 30),
    schedule_interval="0 9,12,15,18 * * *",
    catchup=False,
    default_args={'owner': 'airflow', 'retries': 1, 'retry_delay': timedelta(minutes=5)},
    tags=['naver', 'news']
) as dag:

    update_task = PythonOperator(
        task_id="crawl_and_update_news",
        python_callable=update_news,
        provide_context=True
    )
