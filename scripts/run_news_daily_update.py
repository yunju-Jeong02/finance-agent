from sqlalchemy import create_engine, text
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime, timedelta

# DB 설정
DB_CONFIG = {
    'user': 'admin',
    'password': 'miraeasset25!',
    'host': 'miraeasset-database-1.c5w8cg8kau54.ap-northeast-2.rds.amazonaws.com',
    'port': 3306,
    'database': 'news_DB'
}

def get_engine():
    return create_engine(
        f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )

def get_latest_date_from_db():
    engine = get_engine()
    query = "SELECT MAX(date) FROM News"
    with engine.connect() as conn:
        result = conn.execute(text(query)).scalar()
        return result if result else None

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

def insert_news_to_db(df):
    engine = get_engine()
    df.to_sql(name='News', con=engine, if_exists='append', index=False)

def delete_old_news(days=30):
    engine = get_engine()
    cutoff_date = (datetime.today() - timedelta(days=days)).strftime('%Y-%m-%d')
    with engine.connect() as conn:
        with conn.begin():
            conn.execute(text("DELETE FROM News WHERE date < :cutoff"), {"cutoff": cutoff_date})

def main():
    latest_db_date = get_latest_date_from_db()
    if latest_db_date:
        start_date = datetime.strptime(latest_db_date, '%Y%m%d') + timedelta(days=1)
    else:
        # DB에 데이터가 없다면 기본 시작일 설정
        start_date = datetime.today() - timedelta(days=7)

    end_date = datetime.today()
    
    print(f"📆 수집 기간: {start_date.strftime('%Y%m%d')} ~ {end_date.strftime('%Y%m%d')}")

    for single_date in pd.date_range(start=start_date, end=end_date):
        date_str = single_date.strftime('%Y%m%d')
        print(f"크롤링 중: {date_str}")
        df = get_economy_news_by_date(date_str)
        if not df.empty:
            insert_news_to_db(df)
            print(f"→ {len(df)}건 저장 완료")
        else:
            print("→ 데이터 없음")

    print("🧹 오래된 뉴스 삭제 중...")
    delete_old_news()
    print("✅ 완료")

if __name__ == "__main__":
    main()