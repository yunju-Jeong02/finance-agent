from sqlalchemy import create_engine
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

def get_engine():
    return create_engine(
        f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )

def get_economy_news_by_date(date_str, max_page=250):
    """
    네이버 경제 섹션에서 특정 날짜 뉴스 수집 (Selenium + BeautifulSoup)
    """
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
            # 동영상 기사 alt 태그 처리
            img_tag = li.select_one("dt.photo img")
            if img_tag and img_tag.has_attr("alt"):
                title = img_tag["alt"].strip()
                a_tag = li.select_one("dt.photo a")
                if a_tag and a_tag.has_attr("href"):
                    href = a_tag["href"]

            # 일반 기사 텍스트 추출
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
