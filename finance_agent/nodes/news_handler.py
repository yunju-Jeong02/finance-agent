from typing import Dict, List
from datetime import datetime
import re
import requests
from bs4 import BeautifulSoup
from finance_agent.prompts import news_summary_prompt
from finance_agent.news_db_manager import NewsDatabaseManager
from finance_agent.llm import LLM
import traceback

class NewsHandler:
    def __init__(self):
        self.news_db = NewsDatabaseManager()
        self.llm = LLM()

    def _summarize(self, title: str, content: str, url: str) -> str:
        prompt_text = news_summary_prompt.format(title=title or "", content=content or "", url=url or "")
        return self.llm.run(prompt_text)

    def _url_to_item(self, url: str) -> Dict | None:
        if not (url and url.startswith("http")):
            return None
        try:
            res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=7)
            if res.status_code != 200:
                return None
            soup = BeautifulSoup(res.text, 'html.parser')
            title = (soup.title.string or "").strip() if soup.title else ""
            content = self.news_db.fetch_content_from_url(url)
            if not (title and content):
                return None
            return {"title": title, "link": url, "date": None, "content": content}
        except requests.exceptions.RequestException:
            return None

    def _search_or_crawl(self, keywords: List[str], date: str | None, limit: int = 3) -> List[Dict]:
        news = self.news_db.search_news(keywords=keywords, date=date, limit=limit)
        if not news:
            news = self.news_db._crawl_naver_news(
                company=keywords[0] if keywords else "",
                extra_keywords=keywords[1:],
                date=date,
                limit=limit
            )
        return news or []

    def process(self, state: Dict) -> Dict:
        parsed = state.get("parsed_query", {})
        intent = parsed.get("intent", "")
        
        if intent == "hot_news_request":
            try:
                df = self.news_db.get_recent_news_titles(limit=100)
                if df.empty:
                    state["final_output"] = "❌ 최근 뉴스가 없습니다."
                    state["is_complete"] = True
                    return state

                top_keywords = self.news_db.extract_top_keywords(df['title'])
                if not top_keywords:
                    state["final_output"] = "❌ 주요 키워드를 찾지 못했습니다."
                    state["is_complete"] = True
                    return state
                
                top_5_keywords = top_keywords[:5]
                
                # 1. 상위 5개 키워드 중 2개 이상이 포함된 뉴스 찾기
                # (키워드 일치 개수와 상위 키워드 인덱스에 따라 우선순위 정렬)
                candidate_news = []
                for _, row in df.iterrows():
                    matched_keywords = [kw for kw in top_5_keywords if kw in row['title']]
                    if len(matched_keywords) >= 2:
                        # 일치하는 키워드 수와 가장 상위의 키워드 인덱스로 우선순위 점수 부여
                        score = len(matched_keywords) * 100 - min([top_5_keywords.index(kw) for kw in matched_keywords])
                        candidate_news.append({"score": score, "item": row.to_dict()})
                
                # 점수 순으로 정렬
                candidate_news.sort(key=lambda x: x['score'], reverse=True)
                selected_news = [item['item'] for item in candidate_news]

                final_news_list = []
                if len(selected_news) >= 3:
                    # 3개 이상이면 우선순위 높은 3개만 선택
                    final_news_list = selected_news[:3]
                else:
                    # 3개 미만이면 남은 개수만큼 상위 키워드(1,2,3위)에서 추가
                    final_news_list.extend(selected_news)
                    
                    missing_count = 3 - len(final_news_list)
                    if missing_count > 0:
                        used_links = {n.get('link') for n in final_news_list}
                        for i in range(missing_count):
                            # 이미 사용된 키워드 제외하고 상위 키워드 순서대로 뉴스 검색
                            keyword_index = len(selected_news) + i
                            if keyword_index < len(top_keywords):
                                kw_to_add = top_keywords[keyword_index]
                                additional_news = self.news_db.search_news(keywords=[kw_to_add], limit=1)
                                if additional_news and additional_news[0].get('link') not in used_links:
                                    final_news_list.append(additional_news[0])
                                    used_links.add(additional_news[0].get('link'))
                
                # 요약 생성
                if final_news_list:
                    outputs = []
                    for n in final_news_list:
                        title = n.get("title", "제목 없음")
                        url = n.get("link", "")
                        content = n.get("content") or self.news_db.fetch_content_from_url(url)
                        summary = self._summarize(title, content or title, url)
                        outputs.append(f"- {title}\n{summary}\n출처: {url}")
                    
                    state["final_output"] = "📰 핫한 뉴스 요약\n\n" + "\n\n".join(outputs)
                else:
                    state["final_output"] = "❗ 관련 뉴스를 찾을 수 없습니다."
                    
            except Exception as e:
                state["final_output"] = f"핫 뉴스 처리 중 오류가 발생했습니다: {e}"
            
            state["is_complete"] = True
            state["needs_user_input"] = False
            return state

        keywords = parsed.get("keywords", []) or []
        date = parsed.get("date", "")
        
        news = []
        if intent == "today_news_request":
            news = self._search_or_crawl(
                keywords=keywords,
                date=datetime.now().strftime("%Y-%m-%d"),
                limit=3
            )
        elif intent == "url_summary_request" and keywords:
            item = self._url_to_item(keywords[0])
            if item:
                news = [item]
        else:
            news = self._search_or_crawl(keywords=keywords, date=date, limit=3)

        if news:
            outputs = []
            for n in news:
                title = n.get("title", "")
                url = n.get("link", "") or n.get("url", "")
                content = n.get("content") or (self.news_db.fetch_content_from_url(url) if url else title)
                summary = self._summarize(title, content or title, url)
                outputs.append(f"- {title}\n{summary}\n출처: {url}")
            state["final_output"] = "📰 뉴스 요약\n\n" + "\n\n".join(outputs)
        else:
            state["final_output"] = "❗ 관련 뉴스를 찾을 수 없습니다."

        state["is_complete"] = True
        state["needs_user_input"] = False
        return state