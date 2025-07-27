import requests
from bs4 import BeautifulSoup

class URLSummaryClient:
    def __init__(self, clova_client):
        self.clova = clova_client

    def summarize_url(self, url):
        try:
            res = requests.get(url, timeout=5)
            soup = BeautifulSoup(res.text, 'html.parser')
            article = soup.select_one("#newsct_article")
            if not article:
                return "❗ 뉴스 본문을 찾을 수 없습니다."
            content = article.get_text(" ", strip=True)
            return self.clova.summarize(content)
        except Exception as e:
            return f"❗ URL 접속/요약 실패: {e}"
