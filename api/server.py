# app.py
from fastapi import FastAPI
from pydantic import BaseModel
from finance_agent.agent import FinanceAgent

app = FastAPI()
agent = FinanceAgent()

# 대화 상태 저장 (간단히 메모리 기준)
# 실제 서비스에선 Redis나 DB를 추천
sessions = {}

class UserMessage(BaseModel):
    session_id: str
    user_input: str
    clarification_count: int = 0

@app.post("/chat")
def chat(msg: UserMessage):
    if msg.session_id not in sessions:
        sessions[msg.session_id] = {}

    # 최신 세션 불러오기
    agent.last_state = sessions[msg.session_id]

    # 🔍 Clarification count는 따로 넘김
    result = agent.process_query(
        user_query=msg.user_input,
        session_id=msg.session_id,
        clarification_count=msg.clarification_count
    )

    # 세션 상태 업데이트
    sessions[msg.session_id] = agent.last_state

    return result


class ClarifyMessage(BaseModel):
    session_id: str
    original_query: str
    clarification: str
    clarification_count: int = 1

@app.post("/clarify")
def clarify(msg: ClarifyMessage):
    agent.last_state = sessions.get(msg.session_id, {})

    result = agent.handle_clarification_response(
        original_query=msg.original_query,
        clarification=msg.clarification,
        session_id=msg.session_id,
        clarification_count=msg.clarification_count
    )

    sessions[msg.session_id] = agent.last_state
    return result
