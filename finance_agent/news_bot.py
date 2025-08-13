# finance_agent/news_bot.py (이 코드로 파일 전체를 교체하세요)

import schedule
import time
import threading
from datetime import datetime, timedelta

from finance_agent.llm import LLM
from finance_agent.news_db_manager import NewsDatabaseManager
from finance_agent.prompts import news_summary_prompt, weekly_report_prompt

class NewsBot:
    def __init__(self):
        self.llm = LLM()
        self.news_db = NewsDatabaseManager()
        self.scheduler = schedule.Scheduler()
        self.conversation_state = {}

    # --- 대화 시작 로직 ---
    def start_conversation(self, session_id):
        """뉴스 스케줄링 대화를 시작합니다."""
        self.conversation_state[session_id] = {
            "step": "awaiting_company_name",
            "company_name": None,
        }
        return "알겠습니다. 어느 회사의 뉴스를 스케줄링할까요? 회사명을 입력해주세요."

    def start_cancellation(self, session_id):
        """뉴스 스케줄 취소 대화를 시작합니다."""
        state = self.conversation_state.get(session_id)
        if state and state.get("schedule_time"):
            company_name = state["company_name"]
            state["step"] = "awaiting_cancellation_confirmation"
            return f"알겠습니다. '{company_name}' 뉴스의 정기 알림을 취소하시겠습니까? ('네' 또는 '아니오')"
        else:
            # 대화 상태에 스케줄 정보가 없으면, 모든 스케줄을 뒤져본다 (재시작 대비)
            jobs = [job for job in self.scheduler.jobs if session_id in job.tags]
            if not jobs:
                self.conversation_state.pop(session_id, None) # 상태 초기화
                return "현재 설정된 뉴스 스케줄이 없습니다."
            else:
                 # 스케줄은 있지만 상태가 날아간 경우 (예: 프로그램 재시작)
                 self.conversation_state[session_id] = {"step": "awaiting_cancellation_confirmation"}
                 return f"설정된 정기 알림을 취소하시겠습니까? ('네' 또는 '아니오')"


    # --- 메인 대화 처리 로직 ---
    def handle_message(self, session_id, user_input: str):
        """사용자 메시지를 상태에 따라 처리합니다."""
        state = self.conversation_state.get(session_id)
        if not state:
            return "죄송합니다. 대화 상태를 찾을 수 없습니다. 다시 시작해주세요."

        step = state.get("step")

        # 1. 취소 확인 단계
        if step == "awaiting_cancellation_confirmation":
            if user_input.lower() in ['네', '예', '응', '맞아']:
                self.scheduler.clear(session_id) # 해당 세션의 모든 스케줄 삭제
                company_name = state.get("company_name", "기존")
                self.conversation_state.pop(session_id, None) # 대화 상태 종료
                return f"'{company_name}' 뉴스의 정기 알림이 취소되었습니다."
            else:
                self.conversation_state.pop(session_id, None) # 대화 상태 종료
                return "알겠습니다. 스케줄을 유지합니다."

        # 2. 회사명 입력 단계
        elif step == "awaiting_company_name":
            state["company_name"] = user_input.strip()
            summary, news_found = self._fetch_and_summarize_latest_news(state["company_name"])
            if not news_found:
                self.conversation_state.pop(session_id, None)
                return f"{state['company_name']}의 최신 뉴스를 찾을 수 없습니다."
            
            state["step"] = "awaiting_schedule_time"
            return (
                f"📰 {state['company_name']} 최신 뉴스 요약:\n{summary}\n\n"
                f"매일 몇 시에 '{state['company_name']}'의 최신 뉴스를 요약해드릴까요? (예: '09:00', '14:30', 원하지 않으면 '아니' 또는 '취소')"
            )

        # 3. 시간 입력 단계
        elif step == "awaiting_schedule_time":
            if any(keyword in user_input for keyword in ['아니', '취소', '필요없어']):
                self.conversation_state.pop(session_id, None)
                return "알겠습니다. 스케줄링을 취소합니다."

            schedule_time_str = ''.join(filter(str.isdigit, user_input))
            if len(schedule_time_str) == 2: schedule_time_str += ":00"
            elif len(schedule_time_str) == 4: schedule_time_str = f"{schedule_time_str[:2]}:{schedule_time_str[2:]}"
            else: return "시간 형식이 올바르지 않습니다. '오전 9시', '14:30' 와 같이 입력해주세요."
            
            state["schedule_time"] = schedule_time_str
            self._schedule_jobs(session_id)
            state["step"] = "scheduled"
            return f"알겠습니다. 매일 {state['schedule_time']}에 {state['company_name']} 뉴스를 보내드릴게요."
        
        else:
             self.conversation_state.pop(session_id, None)
             return "대화가 완료되었습니다. 다른 질문이 있으신가요?"


    # --- 내부 기능 ---
    def _fetch_and_summarize_latest_news(self, company_name: str):
        today_str = datetime.now().strftime("%Y-%m-%d")
        news_list = self.news_db.search_news(keywords=[company_name], date=today_str, limit=1)
        if not news_list:
            news_list = self.news_db._crawl_naver_news(company=company_name, limit=1)
        if not news_list:
            return "관련 뉴스를 찾지 못했습니다.", False

        latest_news = news_list[0]
        title, url = latest_news["title"], latest_news["link"]
        content = latest_news.get("content") or self.news_db._fetch_news_content(url)

        prompt_text = news_summary_prompt.format(title=title, content=content, url=url)
        summary = self.llm.run(prompt_text)
        return f"{summary}\n출처: {url}", True

    def _schedule_jobs(self, session_id: str):
        state = self.conversation_state[session_id]
        self.scheduler.every().day.at(state['schedule_time']).do(self._send_daily_summary, session_id=session_id).tag(session_id, 'daily')
        self.scheduler.every(7).days.do(self._send_weekly_report, session_id=session_id).tag(session_id, 'weekly')
        print(f"[{session_id}] 다음 작업 스케줄링됨: Daily @ {state['schedule_time']}, Weekly in 7 days.")

    def _send_daily_summary(self, session_id: str):
        state = self.conversation_state.get(session_id)
        if not state: return schedule.CancelJob
        
        print(f"\n\n🤖 [자동 알림] {state['company_name']}의 오늘의 뉴스 요약입니다.")
        summary, found = self._fetch_and_summarize_latest_news(state['company_name'])
        print(summary if found else "현재 시간 기준으로 새로운 뉴스가 없습니다.")
        print("\n🧑: ", end="")

    def _send_weekly_report(self, session_id: str):
        state = self.conversation_state.get(session_id)
        if not state: return schedule.CancelJob

        print(f"\n\n- - - - -\n🤖 [주간 보고서] 지난 7일간 {state['company_name']}의 뉴스 동향입니다.")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")
        news_list = self.news_db.search_news(keywords=[state['company_name']], start_date=start_date, end_date=end_date, limit=5)

        if not news_list:
            print("지난 7일간 요약할 뉴스가 없습니다.")
        else:
            news_for_report = [f"- 제목: {news['title']}\n- 내용: {news.get('content', '')[:200]}..." for news in news_list]
            prompt = weekly_report_prompt.format(company_name=state['company_name'], news_articles="\n".join(news_for_report))
            report = self.llm.run(prompt)
            print(report)
        print("\n- - - - -\n\n🧑: ", end="")


    def run_scheduler(self):
        while True:
            self.scheduler.run_pending()
            time.sleep(1)