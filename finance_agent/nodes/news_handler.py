# finance_agent/nodes/news_handler.py
from typing import Dict
from datetime import datetime
import uuid, requests
from config.config import Config
from finance_agent.prompts import news_summary_prompt
from finance_agent.news_db_manager import NewsDatabaseManager
from finance_agent.llm import LLM

class NewsHandler:
    def __init__(self):
        self.news_db = NewsDatabaseManager()
        self.llm = LLM()  # ← model_name, temperature 설정은 llm.py에서

    def process(self, state: Dict) -> Dict:
        parsed = state.get("parsed_query", {})
        intent = parsed.get("intent", "")
        date = parsed.get("date", "")
        keywords = parsed.get("keywords", [])

        if intent == "today_news_request":
            news = self.news_db._crawl_naver_news(
                company=keywords[0] if keywords else "",
                extra_keywords=keywords[1:],
                date=datetime.now().strftime("%Y-%m-%d"),
                limit=3
            )
        else:
            news = self.news_db.search_news(keywords=keywords, date=date, limit=3)
            if not news:
                news = self.news_db._crawl_naver_news(
                    company=keywords[0] if keywords else "",
                    extra_keywords=keywords[1:],
                    date=date,
                    limit=3
                )

        if news:
            summaries = []
            for n in news:
                title, url, content = n["title"], n["link"], n.get("content", "")
                if not content:
                    content = self.news_db._fetch_news_content(url)

                prompt_text = news_summary_prompt.format(title=title, content=content, url=url)
                summary = self.llm.run(prompt_text)  # ← LLM 호출

                summaries.append(f"- {title}\n{summary}\n출처: {url}")

            state["final_output"] = "📰 뉴스 요약\n" + "\n\n".join(summaries)
        else:
            state["final_output"] = "❗ 관련 뉴스를 찾을 수 없습니다."

        state["is_complete"] = True
        return state