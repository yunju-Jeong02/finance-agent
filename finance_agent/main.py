# finance_agent/main.py
from fastapi import FastAPI, Request, Header
from typing import Optional
from finance_agent.agent import FinanceAgent

app = FastAPI()
agent = FinanceAgent()

@app.get("/agent")
def handle_agent_request(
    question: str,
    authorization: Optional[str] = Header(None),
    x_ncp_clovastudio_request_id: Optional[str] = Header(None)
):
    result = agent.process_query(user_query=question)
    
    # 평가 시스템에 맞는 응답 포맷으로 변환
    return {
        "answer": result.get("response", "오류가 발생했습니다.")
    }