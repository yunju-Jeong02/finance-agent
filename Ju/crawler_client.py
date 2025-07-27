import requests
from datetime import datetime
from email.utils import parsedate_to_datetime

NAVER_CLIENT_ID = "ijcAFNdsQCZ2H2fGxpyd"
NAVER_CLIENT_SECRET = "wshoGn_9Rk"

class NewsCrawler:
    def __init__(self):
        self.client_id = NAVER_CLIENT_ID
        self.client_secret = NAVER_CLIENT_SECRET
        self.base_url = "https://openapi.naver.com/v1/search/news.json"
        self.headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
        }

    def search_naver_news(self, query, display=10, start=1, sort="sim"):
        params = {
            "query": query,
            "display": display,
            "start": start,
            "sort": sort,
        }
        try:
            res = requests.get(self.base_url, headers=self.headers, params=params)
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"[ERROR] API 호출 실패: {e}")
            return None

    def get_all_news_by_date(self, query, target_date=None, max_total=1000):
        if target_date is None:
            target_date = datetime.now().strftime("%Y%m%d")
        all_news = []
        start = 1
        display = 100  # 최대 100건씩 조회

        while start <= 1000 and len(all_news) < max_total:
            response = self.search_naver_news(query=query, display=display, start=start, sort="date")
            if not response or "items" not in response:
                break

            page_news = []
            for item in response["items"]:
                pub_date = item.get("pubDate", "")
                try:
                    dt = parsedate_to_datetime(pub_date)
                    if dt.strftime("%Y%m%d") == target_date:
                        link = item.get("originallink", "") or item.get("link", "")
                        if "n.news.naver.com" in link:
                            page_news.append({
                                "title": item.get("title", ""),
                                "link": link,
                                "pubDate": pub_date
                            })
                except Exception:
                    continue

            if not page_news:
                # 해당 날짜 기사 없으면 종료
                break

            all_news.extend(page_news)
            start += display

        return all_news[:max_total]


"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime

class NewsCrawler:
    def __init__(self):
        self.base_url = "https://news.naver.com/main/list.naver"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        }

    def get_news_list(self, keyword=None, date=None, max_pages=3):
        if date is None:
            date = datetime.now().strftime('%Y%m%d')

        results = []

        for page in range(1, max_pages + 1):
            params = {
                'mode': 'LSD',
                'mid': 'sec',
                'sid1': '101',
                'listType': 'title',
                'date': date,
                'page': page
            }
            res = requests.get(self.base_url, headers=self.headers, params=params)
            if res.status_code != 200:
                print(f"[ERROR] Failed to fetch page {page}")
                break

            soup = BeautifulSoup(res.text, 'html.parser')
            items = soup.select(".list_body.newsflash_body li")
            if not items:
                break

            for item in items:
                link_tag = item.select_one("a")
                title = link_tag.text.strip() if link_tag else ""
                link = link_tag['href'] if link_tag else ""
                if keyword:
                    if keyword.lower() in title.lower():
                        results.append({'title': title, 'link': link})
                else:
                    results.append({'title': title, 'link': link})

            if len(results) >= 20:
                break

        return results[:20]

    def get_news_content(self, url):
        res = requests.get(url, headers=self.headers)
        if res.status_code != 200:
            print(f"[ERROR] Failed to fetch news content")
            return None

        soup = BeautifulSoup(res.text, 'html.parser')
        content_div = soup.select_one("#dic_area")
        if content_div:
            return content_div.get_text(strip=True)
        else:
            print(f"[WARNING] News content not found")
            return None
"""