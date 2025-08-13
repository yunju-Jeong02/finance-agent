# scripts/test_agent.py

import sys
import os
import uuid
import threading

# 프로젝트 루트 디렉터리를 Python path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from finance_agent.agent import FinanceAgent
# ✨ 1. 원본 NewsBot을 가져옵니다.
from finance_agent.news_bot import NewsBot
from langchain_core.messages import HumanMessage, AIMessage

# ✨ 2. 테스트용으로 스케줄만 변경한 '데모 봇'을 새로 정의합니다.
class DemoNewsBot(NewsBot):
    """
    원본 NewsBot의 모든 기능을 상속받고,
    주간 보고서 스케줄링 메소드만 테스트용으로 변경(오버라이딩)합니다.
    """
    def _schedule_jobs(self, session_id: str, company_name: str, schedule_time: str):
        # 일일 요약 스케줄은 원본과 동일하게 설정
        self.scheduler.every().day.at(schedule_time).do(
            self._send_daily_summary, 
            session_id=session_id, 
            company_name=company_name
        ).tag(session_id, company_name, 'daily')
        
        # ✨ 주간 보고서 스케줄만 '1분'으로 변경하여 테스트
        self.scheduler.every(1).minute.do(
            self._send_weekly_report, 
            session_id=session_id, 
            company_name=company_name
        ).tag(session_id, company_name, 'weekly')
        
        print(f"--- [DEMO MODE] ---")
        print(f"[{session_id}-{company_name}] 다음 작업 스케줄링됨: Daily @ {schedule_time}, Weekly in 1 minute.")
        print(f"-------------------")


class AgentTestController:
    def __init__(self):
        self.finance_agent = FinanceAgent()
        # ✨ 3. 컨트롤러가 '데모 봇'을 사용하도록 설정합니다.
        self.news_bot = DemoNewsBot() 
        self.active_mode = 'finance'
        self.session_id = str(uuid.uuid4())
        self.chat_history = []

    def run(self):
        print("=== Finance Agent TEST Script (Weekly Report: 1 minute) ===")
        print("'뉴스 스케줄링'으로 테스트를 시작하세요. '종료' 입력 시 종료됩니다.\n")

        # 이하 로직은 run_agent.py와 완전히 동일합니다.
        scheduler_thread = threading.Thread(target=self.news_bot.run_scheduler, daemon=True)
        scheduler_thread.start()

        while True:
            try:
                user_input = input("🧑: ").strip()

                if not user_input: continue
                if user_input.lower() in ['종료', 'quit']:
                    print("🤖: Agent를 종료합니다.")
                    break

                response = None
                
                if any(kw in user_input for kw in ["스케줄 확인", "스케줄 취소", "뉴스 스케줄링", "주간 보고서 테스트"]):
                    self.active_mode = 'news_bot'
                    if "스케줄 확인" in user_input:
                        response = self.news_bot.show_schedules(self.session_id)
                    elif "스케줄 취소" in user_input:
                        response = self.news_bot.start_cancellation(self.session_id)
                    elif "뉴스 스케줄링" in user_input:
                        response = self.news_bot.start_conversation(self.session_id)
                    elif "주간 보고서 테스트" in user_input:
                        response = self.news_bot.trigger_weekly_report(self.session_id)
                
                elif self.active_mode == 'news_bot':
                    response = self.news_bot.handle_message(self.session_id, user_input)
                
                else:
                    self.active_mode = 'finance'
                    result = self.finance_agent.process_query(
                        user_query=user_input, 
                        session_id=self.session_id,
                        chat_history=self.chat_history 
                    )
                    response = result.get('response') or result.get("clarification_question")
                    if response:
                        self.chat_history.append(HumanMessage(content=user_input))
                        self.chat_history.append(AIMessage(content=response))

                session_state = self.news_bot.conversation_state.get(self.session_id, {})
                if self.active_mode == 'news_bot' and session_state.get("current_task") is None:
                    self.active_mode = 'finance'

                print(f"🤖: {response}")
                if response: print()

            except (KeyboardInterrupt, EOFError):
                print("\n\n🤖: 대화를 중단합니다.")
                break
            except Exception as e:
                print(f"오류가 발생했습니다: {e}")
                import traceback
                traceback.print_exc()

def main():
    controller = AgentTestController()
    controller.run()
    return 0

if __name__ == "__main__":
    sys.exit(main())