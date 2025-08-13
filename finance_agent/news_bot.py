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

    def _get_session_state(self, session_id: str):
        if session_id not in self.conversation_state:
            self.conversation_state[session_id] = {
                "schedules": [],
                "current_task": None
            }
        return self.conversation_state[session_id]

    def start_conversation(self, session_id):
        session_state = self._get_session_state(session_id)
        session_state["current_task"] = {"step": "awaiting_company_name"}
        return "알겠습니다. 어느 회사의 뉴스를 스케줄링할까요? 회사명을 입력해주세요."

    def start_cancellation(self, session_id: str):
        session_state = self._get_session_state(session_id)
        schedules = session_state.get("schedules", [])
        if not schedules:
            session_state["current_task"] = None
            return "현재 등록된 스케줄이 없습니다."

        if len(schedules) == 1:
            company_to_cancel = schedules[0]["company_name"]
            session_state["current_task"] = {
                "step": "awaiting_cancellation_confirmation",
                "company_to_cancel": company_to_cancel
            }
            return f"알겠습니다. '{company_to_cancel}' 뉴스의 정기 알림을 취소하시겠습니까? ('네' 또는 '아니오')"
        else:
            session_state["current_task"] = {"step": "awaiting_cancellation_choice"}
            options = "\n".join([f"{i+1}. {s['company_name']} ({s['schedule_time']})" for i, s in enumerate(schedules)])
            return f"어떤 스케줄을 취소하시겠습니까? 번호를 입력해주세요.\n{options}"

    def show_schedules(self, session_id: str) -> str:
        session_state = self._get_session_state(session_id)
        schedules_list = session_state.get("schedules", [])
        if not schedules_list:
            return "현재 등록된 스케줄이 없습니다."
        report_list = ["현재 등록된 알림 목록입니다:"]
        for sched in schedules_list:
            report_list.append(f" - 🗓️ 일일 뉴스: '{sched['company_name']}' (매일 {sched['schedule_time']})")
            report_list.append(f" - 📊 주간 보고서: '{sched['company_name']}' (매주 1회)")
        return "\n".join(report_list)
    
    # ✨ [수정된 함수] 여러 스케줄 중 테스트할 보고서를 선택하도록 변경
    def trigger_weekly_report(self, session_id: str):
        """테스트를 위해 주간 보고서를 즉시 실행합니다."""
        session_state = self._get_session_state(session_id)
        schedules = session_state.get("schedules", [])
        
        if not schedules:
            return "먼저 뉴스 스케줄링을 등록해야 테스트할 수 있습니다."
        
        if len(schedules) == 1:
            company_name = schedules[0]["company_name"]
            self._send_weekly_report(session_id, company_name=company_name)
            return f"'{company_name}'에 대한 주간 보고서 생성을 수동으로 실행했습니다. (콘솔 확인)"
        else:
            # ✨ 현재 진행 작업을 '보고서 테스트 선택'으로 설정
            session_state["current_task"] = {"step": "awaiting_report_test_choice"}
            options = "\n".join([f"{i+1}. {s['company_name']}" for i, s in enumerate(schedules)])
            return f"어떤 회사의 주간 보고서를 테스트하시겠습니까? 번호를 입력해주세요.\n{options}"

    def handle_message(self, session_id, user_input: str):
        session_state = self._get_session_state(session_id)
        task = session_state.get("current_task")
        if not task:
            return "진행 중인 작업이 없습니다. '뉴스 스케줄링' 등으로 시작해주세요."

        step = task.get("step")

        # ... (awaiting_company_name, awaiting_schedule_time 로직은 동일) ...
        if step == "awaiting_company_name":
            task["company_name"] = user_input.strip()
            summary, news_found = self._fetch_and_summarize_latest_news(task["company_name"])
            if not news_found:
                session_state["current_task"] = None
                return summary
            task["step"] = "awaiting_schedule_time"
            return (f"📰 {task['company_name']} 최신 뉴스 요약:\n{summary}\n\n"
                    f"매일 몇 시에 '{task['company_name']}'의 최신 뉴스를 요약해드릴까요? (예: '09:00', '14:30', 원하지 않으면 '아니' 또는 '취소')")
        elif step == "awaiting_schedule_time":
            if any(keyword in user_input for keyword in ['아니', '취소', '필요없어']):
                session_state["current_task"] = None
                return "알겠습니다. 스케줄링을 취소합니다."
            schedule_time_str = ''.join(filter(str.isdigit, user_input))
            if len(schedule_time_str) == 2: schedule_time_str += ":00"
            elif len(schedule_time_str) == 4: schedule_time_str = f"{schedule_time_str[:2]}:{schedule_time_str[2:]}"
            else: return "시간 형식이 올바르지 않습니다. '09:00', '14:30' 와 같이 입력해주세요."
            task["schedule_time"] = schedule_time_str
            session_state["schedules"].append({"company_name": task["company_name"], "schedule_time": task["schedule_time"]})
            self._schedule_jobs(session_id, task["company_name"], task["schedule_time"])
            session_state["current_task"] = None
            return f"알겠습니다. 매일 {task['schedule_time']}에 {task['company_name']} 뉴스를 보내드릴게요."

        # ... (awaiting_cancellation_choice, awaiting_cancellation_confirmation 로직은 동일) ...
        elif step == "awaiting_cancellation_choice":
            try:
                choice_idx = int(user_input) - 1
                schedules = session_state["schedules"]
                if 0 <= choice_idx < len(schedules):
                    company_to_cancel = schedules[choice_idx]["company_name"]
                    task["step"] = "awaiting_cancellation_confirmation"
                    task["company_to_cancel"] = company_to_cancel
                    return f"알겠습니다. '{company_to_cancel}' 뉴스의 정기 알림을 취소하시겠습니까? ('네' 또는 '아니오')"
                else: return "잘못된 번호입니다. 다시 입력해주세요."
            except ValueError: return "숫자로 입력해주세요."
        elif step == "awaiting_cancellation_confirmation":
            company_to_cancel = task.get("company_to_cancel")
            if user_input.lower() in ['네', '예', '응', '맞아']:
                self.scheduler.clear(company_to_cancel)
                session_state["schedules"] = [s for s in session_state["schedules"] if s["company_name"] != company_to_cancel]
                session_state["current_task"] = None
                return f"'{company_to_cancel}' 뉴스의 정기 알림이 취소되었습니다."
            else:
                session_state["current_task"] = None
                return "알겠습니다. 스케줄을 유지합니다."
        
        # ✨ [추가된 로직] 보고서 테스트 선택 처리
        elif step == "awaiting_report_test_choice":
            try:
                choice_idx = int(user_input) - 1
                schedules = session_state["schedules"]
                if 0 <= choice_idx < len(schedules):
                    company_to_test = schedules[choice_idx]["company_name"]
                    self._send_weekly_report(session_id, company_name=company_to_test)
                    session_state["current_task"] = None # 작업 완료
                    return f"'{company_to_test}'에 대한 주간 보고서 생성을 수동으로 실행했습니다. (콘솔 확인)"
                else:
                    return "잘못된 번호입니다. 다시 입력해주세요."
            except ValueError:
                return "숫자로 입력해주세요."
        
        return "알 수 없는 작업 단계입니다. 다시 시도해주세요."

    # ... 이하 _fetch_and_summarize_latest_news, _schedule_jobs, _send_daily_summary, 
    # _generate_and_print_daily_summary, _send_weekly_report, 
    # _generate_and_print_weekly_report, run_scheduler 함수들은 이전과 동일합니다 ...
    def _fetch_and_summarize_latest_news(self, company_name: str):
        today_str = datetime.now().strftime("%Y-%m-%d")
        news_list = self.news_db.search_news(keywords=[company_name], date=today_str, limit=1)
        if not news_list:
            return "관련 뉴스를 찾지 못했습니다.", False
        latest_news = news_list[0]
        title, url = latest_news.get("title", "제목 없음"), latest_news.get("link", "")
        content = latest_news.get("content") or self.news_db._fetch_news_content(url)
        if not content:
            return f"'{title}' 뉴스의 본문 내용을 가져올 수 없어 요약에 실패했습니다.", False
        prompt_text = news_summary_prompt.format(title=title, content=content, url=url)
        summary = self.llm.run(prompt_text)
        return f"{summary}\n출처: {url}", True

    def _schedule_jobs(self, session_id: str, company_name: str, schedule_time: str):
        self.scheduler.every().day.at(schedule_time).do(self._send_daily_summary, session_id=session_id, company_name=company_name).tag(session_id, company_name, 'daily')
        self.scheduler.every(7).days.do(self._send_weekly_report, session_id=session_id, company_name=company_name).tag(session_id, company_name, 'weekly')
        print(f"[{session_id}-{company_name}] 다음 작업 스케줄링됨: Daily @ {schedule_time}")
    
    def _send_daily_summary(self, session_id: str, company_name: str):
        threading.Thread(target=self._generate_and_print_daily_summary, args=(session_id, company_name)).start()

    def _generate_and_print_daily_summary(self, session_id: str, company_name: str):
        print(f"\n\n🤖 [자동 알림] {company_name}의 오늘의 뉴스 요약입니다.")
        summary, found = self._fetch_and_summarize_latest_news(company_name)
        print(summary if found else "현재 시간 기준으로 새로운 뉴스가 없습니다.")
        print("\n🧑: ", end="")

    def _send_weekly_report(self, session_id: str, company_name: str):
        threading.Thread(target=self._generate_and_print_weekly_report, args=(session_id, company_name)).start()

    def _generate_and_print_weekly_report(self, session_id: str, company_name: str):
        print(f"\n\n- - - - -\n🤖 [주간 보고서] 지난 7일간 {company_name}의 뉴스 동향입니다.")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")
        news_list = self.news_db.search_news(keywords=[company_name], start_date=start_date, end_date=end_date, limit=5)
        if not news_list:
            print("지난 7일간 요약할 뉴스가 없습니다.")
        else:
            news_for_report = [f"- 제목: {news['title']}\n- 내용: {news.get('content', '')[:200]}..." for news in news_list]
            prompt = weekly_report_prompt.format(company_name=company_name, news_articles="\n".join(news_for_report))
            report = self.llm.run(prompt)
            print(report)
        print("\n- - - - -\n\n🧑: ", end="")

    def run_scheduler(self):
        while True:
            self.scheduler.run_pending()
