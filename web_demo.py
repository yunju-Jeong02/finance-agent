# web_demo.py

import streamlit as st
import time
import threading
from langchain_core.messages import HumanMessage, AIMessage

# 기존의 에이전트와 봇 코드를 그대로 가져옵니다.
from finance_agent.agent import FinanceAgent
from finance_agent.news_bot import NewsBot

# ----------------------------------------------------
# ✨ 1. 페이지 설정 및 세션 상태 초기화
# ----------------------------------------------------
st.set_page_config(page_title="KUGENT DEMO", page_icon="🤖")

# 제목 변경
st.title("KUGENT DEMO") 

# 설명 변경
st.caption("KUGENT DEMO는 금융 분석과 뉴스 스케줄링을 도와주는 AI 에이전트입니다. 사용자의 질문에 대한 답변, 최신 뉴스 요약, 주간 보고서 생성 등의 기능이 있습니다.")


# Streamlit의 세션 상태(st.session_state)를 사용해 각 사용자별 대화 상태를 저장합니다.
# 이렇게 하면 웹 페이지가 새로고침 되어도 정보가 유지됩니다.
if "session_id" not in st.session_state:
    # 각 에이전트와 봇을 세션 상태에 한 번만 초기화
    st.session_state.finance_agent = FinanceAgent()
    st.session_state.news_bot = NewsBot()
    st.session_state.session_id = str(id(st.session_state.news_bot)) # 고유 ID 생성
    
    # 백그라운드 스케줄러 실행 (웹 앱이 시작될 때 한 번만)
    scheduler_thread = threading.Thread(
        target=st.session_state.news_bot.run_scheduler, 
        daemon=True
    )
    scheduler_thread.start()
    
    # 대화 기록, 모드 등을 초기화
    st.session_state.messages = []
    st.session_state.active_mode = 'finance'
    st.session_state.chat_history = []

# ----------------------------------------------------
# ✨ 2. 이전 대화 내용 표시
# ----------------------------------------------------
# 세션에 저장된 메시지를 순회하며 화면에 채팅 풍선을 그립니다.
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ----------------------------------------------------
# ✨ 3. 사용자 입력 처리
# ----------------------------------------------------
# st.chat_input은 화면 하단에 채팅 입력창을 만들어줍니다.
if prompt := st.chat_input("질문을 입력하세요..."):
    # 사용자가 입력한 내용을 화면에 표시
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 봇의 답변을 표시할 영역을 미리 준비
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""

        # --- 기존 AgentController의 라우팅 로직을 여기에 구현 ---
        response = None
        user_input = prompt
        
        # NewsBot 키워드 우선 처리
        if any(kw in user_input for kw in ["스케줄 확인", "스케줄 취소", "뉴스 스케줄링", "주간 보고서 테스트"]):
            st.session_state.active_mode = 'news_bot'
            if "스케줄 확인" in user_input:
                response = st.session_state.news_bot.show_schedules(st.session_state.session_id)
            elif "스케줄 취소" in user_input:
                response = st.session_state.news_bot.start_cancellation(st.session_state.session_id)
            elif "뉴스 스케줄링" in user_input:
                response = st.session_state.news_bot.start_conversation(st.session_state.session_id)
            elif "주간 보고서 테스트" in user_input:
                response = st.session_state.news_bot.trigger_weekly_report(st.session_state.session_id)
        
        # NewsBot 대화 진행
        elif st.session_state.active_mode == 'news_bot':
            response = st.session_state.news_bot.handle_message(st.session_state.session_id, user_input)
        
        # 기본 FinanceAgent 처리
        else:
            st.session_state.active_mode = 'finance'
            with st.spinner("생각 중..."): # 처리 중임을 시각적으로 표시
                result = st.session_state.finance_agent.process_query(
                    user_query=user_input, 
                    session_id=st.session_state.session_id,
                    chat_history=st.session_state.chat_history 
                )
            response = result.get('response') or result.get("clarification_question")
            if response:
                st.session_state.chat_history.append(HumanMessage(content=user_input))
                st.session_state.chat_history.append(AIMessage(content=response))

        # NewsBot 대화가 끝나면 finance 모드로 복귀
        session_state = st.session_state.news_bot.conversation_state.get(st.session_state.session_id, {})
        if st.session_state.active_mode == 'news_bot' and session_state.get("current_task") is None:
            st.session_state.active_mode = 'finance'
        
        # 타이핑 효과처럼 보이도록 응답을 한 글자씩 표시
        for chunk in response.split():
            full_response += chunk + " "
            time.sleep(0.05)
            message_placeholder.markdown(full_response + "▌")
        message_placeholder.markdown(full_response)
    
    # 봇의 최종 응답을 대화 기록에 저장
    st.session_state.messages.append({"role": "assistant", "content": full_response})