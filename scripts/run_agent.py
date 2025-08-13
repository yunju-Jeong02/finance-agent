<<<<<<< HEAD
# scripts/run_agent.py (이 코드로 파일 전체를 교체하세요)

import sys
import os
import uuid
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from finance_agent.agent import FinanceAgent
from finance_agent.news_bot import NewsBot
from langchain_core.messages import HumanMessage, AIMessage

class AgentController:
    def __init__(self):
        self.finance_agent = FinanceAgent()
        self.news_bot = NewsBot()
        self.active_mode = 'finance'
        self.session_id = str(uuid.uuid4())
        self.chat_history = []

    def run(self):
        print("=== KU-gent v2.6 (Stable) ===")
        print("'뉴스 스케줄링', '스케줄 취소', '스케줄 확인'이라고 말씀해보세요. '종료' 입력 시 종료됩니다.\n")

        scheduler_thread = threading.Thread(target=self.news_bot.run_scheduler, daemon=True)
        scheduler_thread.start()

        while True:
            try:
                user_input = input("🧑: ").strip()

                if not user_input: continue
                if user_input.lower() in ['종료', 'quit']:
                    print("🤖: Agent를 종료합니다.")
                    break

                # --- 라우팅 로직 ---
                response = None
                
                # NewsBot 키워드가 우선순위를 가짐
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
                
                # 현재 NewsBot 모드에서 대화가 진행 중일 경우
                elif self.active_mode == 'news_bot':
                    response = self.news_bot.handle_message(self.session_id, user_input)
                
                # 위 모든 경우에 해당하지 않으면 FinanceAgent가 처리
                else:
                    self.active_mode = 'finance' # 확실하게 finance 모드임을 명시
                    result = self.finance_agent.process_query(
                        user_query=user_input, 
                        session_id=self.session_id,
                        chat_history=self.chat_history 
                    )
                    response = result.get('response') or result.get("clarification_question")
                    if response:
                        self.chat_history.append(HumanMessage(content=user_input))
                        self.chat_history.append(AIMessage(content=response))

                # ✨ [수정된 부분] NewsBot과의 대화가 끝났는지 확인하고 모드 전환
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
    controller = AgentController()
    controller.run()
    return 0

if __name__ == "__main__":
=======
# scripts/run_agent.py (이 코드로 파일 전체를 교체하세요)

import sys
import os
import uuid
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from finance_agent.agent import FinanceAgent
from finance_agent.news_bot import NewsBot

class AgentController:
    def __init__(self):
        self.finance_agent = FinanceAgent()
        self.news_bot = NewsBot()
        self.active_mode = 'finance'
        self.session_id = str(uuid.uuid4())

    def run(self):
        print("=== KU-gent v2.3 (Cancellable) ===")
        print("'뉴스 스케줄링' 또는 '스케줄 취소'라고 말씀해보세요. '종료' 입력 시 종료됩니다.\n")

        scheduler_thread = threading.Thread(target=self.news_bot.run_scheduler, daemon=True)
        scheduler_thread.start()

        while True:
            try:
                user_input = input("🧑: ").strip()

                if not user_input: continue
                if user_input.lower() in ['종료', 'quit']:
                    print("🤖: Agent를 종료합니다.")
                    break

                # --- 최종 라우팅 로직 (취소 기능 추가) ---

                # 1. "스케줄 취소" 키워드가 있으면 news_bot 모드로 전환하고 취소 시작
                if "스케줄 취소" in user_input:
                    self.active_mode = 'news_bot'
                    response = self.news_bot.start_cancellation(self.session_id)
                
                # 2. "뉴스 스케줄링" 키워드가 있으면 news_bot 모드로 전환하고 스케줄링 시작
                elif "뉴스 스케줄링" in user_input:
                    self.active_mode = 'news_bot'
                    response = self.news_bot.start_conversation(self.session_id)

                # 3. 이미 news_bot 모드일 경우, 대화 계속
                elif self.active_mode == 'news_bot':
                    response = self.news_bot.handle_message(self.session_id, user_input)
                
                # 4. 위 모든 경우에 해당하지 않으면 finance_agent가 처리
                else:
                    result = self.finance_agent.process_query(user_input, self.session_id)
                    response = result.get('response') or result.get("clarification_question")

                # NewsBot과의 대화가 완전히 끝나면 다시 finance 모드로 복귀
                if not self.news_bot.conversation_state.get(self.session_id) and self.active_mode == 'news_bot':
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
    controller = AgentController()
    controller.run()
    return 0

if __name__ == "__main__":
>>>>>>> b66b5c0396370d7c4b1a27fe7ca2c19e6e6aa253
    sys.exit(main())