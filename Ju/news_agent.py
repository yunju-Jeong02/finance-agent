from utils import extract_date, is_url
from collections import Counter
import pandas as pd
import re

class NewsAgent:
    def __init__(self, clova_client, db_client, crawler, url_summarizer):
        self.clova = clova_client
        self.db = db_client
        self.crawler = crawler
        self.url_summarizer = url_summarizer

    def process_query(self, user_query):
    # URL은 DB 검색 건너뛰고 바로 요약
        if is_url(user_query):
            return f"[질문 분석 결과]\n- 의도: url_summary_request\n- 날짜: 없음\n- 키워드: URL\n\n" + \
                self.url_summarizer.summarize_url(user_query)

        intent = self.clova.classify_intent(user_query)
        date = extract_date(user_query)
        keywords = self._extract_keyword(user_query)
        analysis_header = (
            f"[질문 분석 결과]\n"
            f"- 의도(intent): {intent}\n"
            f"- 날짜: {date if date else '없음'}\n"
            f"- 키워드: {', '.join(keywords) if keywords else '없음'}\n\n"
        )

        # URL은 DB 패스하고 바로 요약
        if intent == "url_summary_request":
            return analysis_header + self.url_summarizer.summarize_url(user_query)

        if intent == "clarification_needed":
            return analysis_header + "⚠️ 요청이 모호합니다. 하나씩 물어봐 주세요."

        if intent == "today_news_request":
            return analysis_header + self._summarize_today_news(keywords)

        if intent == "news_summary_request":
            return analysis_header + self._summarize_keyword_news(keywords, date)

        if intent == "hot_news_request":
            return analysis_header + self._summarize_hot_news()

        return analysis_header + "❓ 요청을 이해하지 못했습니다. 다시 말씀해 주세요."

    """
    def _summarize_today_news(self, keywords):
        query = " ".join(keywords)
        print(f"[INFO] Searching 경제 뉴스 for keywords: {query}")

        live_news = self.crawler.get_news_list(keyword=query)

        print(f"[INFO] Crawling result count: {len(live_news)}")
        if live_news:
            url = live_news[0]['link']
            print(f"[INFO] First news URL: {url}")
            return self.url_summarizer.summarize_url(url)

        return "❗ 오늘 관련 뉴스를 찾을 수 없습니다."
    """

    def _summarize_today_news(self, keywords):
        query = " ".join(keywords)
        print(f"[INFO] Searching news for keywords: {query}")

        live_news = self.crawler.get_all_news_by_date(query=query)

        print(f"[INFO] Crawling result count: {len(live_news)}")
        if live_news:
            url = live_news[0]['link']
            print(f"[INFO] First news URL: {url}")
            return self.url_summarizer.summarize_url(url)

        return "❗ 오늘 관련 뉴스를 찾을 수 없습니다."


    def _summarize_keyword_news(self, keywords, date):
        results = self.db.search_news(keywords=keywords, date=date, limit=1)
        if not results:
            live = self.crawler.search_news(" ".join(keywords))
            if live:
                return self.url_summarizer.summarize_url(live[0]['link'])
            return "❗ 관련 뉴스를 찾을 수 없습니다."

        news = results[0]
        return f"\n📌 {news['title']}\n🗓 {news['date']}\n🔗 {news['link']}\n\n📝 요약:\n{self.clova.summarize(news.get('content') or news['title'])}"

    def _summarize_hot_news(self, limit=100):
        query = f"SELECT title, content FROM News ORDER BY date DESC LIMIT {limit}"
        try:
            df = pd.read_sql(query, con=self.db.engine)
        except Exception as e:
            return f"❌ DB 접근 오류: {e}"

        if df.empty:
            return "❌ 최근 뉴스가 없습니다."

        text = ' '.join(df['title'])
        words = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', text).split()
        stopwords = {'그리고','하지만','그래서','때문에','있다','하다','되다','않다','수','것','들','등'}
        counter = Counter([w for w in words if w not in stopwords and len(w) > 1])
        top_keywords = [w for w, _ in counter.most_common(5)]

        print("\n🔥 최근 자주 언급된 키워드:")
        for i, kw in enumerate(top_keywords, 1):
            print(f"{i}. {kw}")
        choice = input("\n🧑 요약할 키워드 번호(1~5): ").strip()
        if not choice.isdigit() or not (1 <= int(choice) <= 5):
            return "❗ 잘못된 입력입니다."

        selected = top_keywords[int(choice)-1]
        match = df[df['title'].str.contains(selected, na=False)]
        if match.empty:
            return f"❌ {selected} 관련 뉴스가 없습니다."

        latest = match.iloc[0]
        summary = self.clova.summarize(latest.get('content') or latest['title'])
        return f"📰 기사 제목: {latest['title']}\n\n📌 요약:\n{summary}"

    def _extract_keyword(self, query):
        # 조사/명령어 등 불필요한 단어들 제거
        stopwords = {"요약", "뉴스", "알려줘", "해줘", "핫한", "실시간", "오늘", "요약해줘"}
        # 특수문자 제거 후 단어 분리
        words = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', query).split()
        # 불용어 제거
        keywords = [w for w in words if w not in stopwords]

        # 키워드가 없으면 기본값 '뉴스'
        return keywords
