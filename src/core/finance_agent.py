from typing import Dict, List, Optional, TypedDict
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from src.core.agent_nodes import FinanceAgentNodes
import uuid

class AgentState(TypedDict):
    user_query: str
    query_classification: Dict
    query_analysis: Dict
    session_context: Dict
    interaction_count: int
    candidates: Dict
    interaction_type: str
    session_id: str
    price_data: Dict
    market_statistics: Dict
    market_rankings: Dict
    search_results: Dict
    technical_signals: Dict
    response: str
    needs_user_input: bool
    conversation_history: List[BaseMessage]

class FinanceAgent:
    def __init__(self):
        self.nodes = FinanceAgentNodes()
        self.graph = self._build_graph()
        self.session_contexts = {}
        self.interaction_counts = {}
        
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(AgentState)
        
        # Add nodes - 중복 제거 및 단순화
        workflow.add_node("analyze_query", self.nodes.analyze_query_with_context)
        workflow.add_node("handle_incomplete_query", self.nodes.handle_incomplete_query)
        workflow.add_node("fetch_simple_data", self.nodes.fetch_simple_data)
        workflow.add_node("fetch_market_statistics", self.nodes.fetch_market_statistics)
        workflow.add_node("fetch_rankings", self.nodes.fetch_rankings)
        workflow.add_node("perform_conditional_search", self.nodes.perform_conditional_search)
        workflow.add_node("generate_response", self.nodes.generate_response)
        
        # Set entry point - 세션 컨텍스트 기반으로 시작
        workflow.set_entry_point("analyze_query")
        
        # Add conditional edges - 단순화된 워크플로우
        workflow.add_conditional_edges(
            "analyze_query",
            self.nodes.check_query_completeness,
            {
                "handle_incomplete_query": "handle_incomplete_query",
                "fetch_simple_data": "fetch_simple_data",
                "fetch_market_statistics": "fetch_market_statistics", 
                "fetch_rankings": "fetch_rankings",
                "perform_conditional_search": "perform_conditional_search",
                "generate_response": "generate_response"
            }
        )
        
        # End conditions
        workflow.add_edge("handle_incomplete_query", END)
        workflow.add_edge("fetch_simple_data", END)
        workflow.add_edge("fetch_market_statistics", END)
        workflow.add_edge("fetch_rankings", END)
        workflow.add_edge("perform_conditional_search", END)
        workflow.add_edge("generate_response", END)
        
        return workflow.compile()
    
    def process_query(self, user_query: str, session_id: str = None) -> Dict:
        """Process a user query and return response"""
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        # 세션 컨텍스트 업데이트
        self.interaction_counts[session_id] = self.interaction_counts.get(session_id, 0) + 1
        
        initial_state = {
            "user_query": user_query,
            "query_classification": {},
            "query_analysis": {},
            "session_context": self.session_contexts.get(session_id, {}),
            "interaction_count": self.interaction_counts[session_id],
            "candidates": {},
            "interaction_type": "",
            "session_id": session_id,
            "price_data": {},
            "market_statistics": {},
            "market_rankings": {},
            "search_results": {},
            "technical_signals": {},
            "response": "",
            "needs_user_input": False,
            "conversation_history": []
        }
        
        try:
            result = self.graph.invoke(initial_state)
            
            # 세션 컨텍스트 업데이트
            if result.get("session_context"):
                self.session_contexts[session_id] = result["session_context"]
            
            result["session_id"] = session_id
            return result
        except Exception as e:
            return {
                "response": f"I apologize, but I encountered an error processing your query: {str(e)}",
                "needs_user_input": False,
                "session_id": session_id
            }
    
    def handle_clarification_response(self, original_query: str, clarification: str, session_id: str = None) -> Dict:
        """Handle user's response to clarification question"""
        combined_query = f"{original_query} {clarification}"
        return self.process_query(combined_query, session_id)
    
    def get_capabilities(self) -> Dict:
        """Return agent capabilities for extensibility"""
        return {
            "supported_queries": [
                "단순조회 - 특정 종목의 특정 날짜 데이터 조회",
                "시장통계 - KOSPI/KOSDAQ 지수, 거래대금, 상승/하락 종목 수",
                "순위조회 - 상승률, 하락률, 거래량, 가격 순위",
                "조건검색 - 구체적인 수치 조건으로 종목 검색",
                "기술적 분석 - RSI, 이동평균, 볼린저밴드 등 기술적 신호"
            ],
            "data_sources": [
                "Yahoo Finance API (한국 주식)",
                "MySQL database (과거 데이터)"
            ],
            "response_types": [
                "직접 답변",
                "재질문 (모호한 질문)",
                "데이터 분석",
                "조건 검색 결과",
                "단계적 정보 수집",
                "후보군 제시"
            ]
        }
    
    def clear_session(self, session_id: str):
        """Clear session context"""
        self.session_contexts.pop(session_id, None)
        self.interaction_counts.pop(session_id, None)
    
    def get_session_status(self, session_id: str) -> Dict:
        """Get session status"""
        context = self.session_contexts.get(session_id, {})
        interaction_count = self.interaction_counts.get(session_id, 0)
        
        return {
            "session_id": session_id,
            "interaction_count": interaction_count,
            "context": context,
            "has_context": bool(context)
        }

class FinanceAgentInterface:
    """Enhanced interface for interacting with the finance agent"""
    
    def __init__(self):
        self.agent = FinanceAgent()
        self.conversation_active = True
        self.current_session_id = None
        
    def start_conversation(self):
        """Start interactive conversation with the agent"""
        print("한국 주식 시장 Finance Agent에게 주식과 금융 시장에 대해 무엇이든 물어보세요.\n")
        print(" - 'quit': 종료\n")
        print(" - 'help': 도움말\n")
        print(" - 'reset': 현재 세션 초기화\n")
        print("🤖: 무엇을 도와드릴까요?")
        
        while self.conversation_active:
            try:
                user_input = input("🧑🏻: ").strip()
                
                if user_input.lower() == 'quit':
                    if self.current_session_id:
                        self.agent.clear_session(self.current_session_id)
                    print("Finance Agent를 이용해 주셔서 감사합니다!")
                    break
                elif user_input.lower() == 'help':
                    self._show_help()
                    continue
                elif user_input.lower() == 'capabilities':
                    self._show_capabilities()
                    continue
                elif user_input.lower() == 'reset':
                    self._reset_session()
                    continue
                elif user_input.lower() == 'status':
                    self._show_session_status()
                    continue
                elif not user_input:
                    continue
                
                # Process the query
                result = self.agent.process_query(user_input, self.current_session_id)
                self.current_session_id = result.get('session_id')
                
                print(f"🤖: {result['response']}")
                
                # Handle clarification if needed
                if result.get('needs_user_input', False):
                    interaction_type = result.get('interaction_type', '')
                    
                    if interaction_type == 'candidate_selection':
                        clarification = input("🤖: 선택해 주세요 (숫자 또는 '날짜 1, 개수 2' 형식): ").strip()
                    else:
                        clarification = input("🤖: 더 자세한 정보를 제공해 주세요: ").strip()
                    
                    if clarification:
                        clarified_result = self.agent.handle_clarification_response(user_input, clarification, self.current_session_id)
                        self.current_session_id = clarified_result.get('session_id')
                        print(f"Agent: {clarified_result['response']}")
                
                print()  # Add spacing between conversations
                
            except KeyboardInterrupt:
                print("\n\n대화를 중단합니다. 'quit'를 입력하여 종료하거나 계속 대화하세요.")
                continue
            except Exception as e:
                print(f"오류가 발생했습니다: {e}")
                continue
    
    def _show_help(self):
        """Show available commands"""
        print("\n사용 가능한 명령어:")
        print("- help: 이 도움말 메시지 표시")
        print("- capabilities: 에이전트 기능 표시")
        print("- quit: 에이전트 종료")
        print("\n예시 질문:")
        print("- 삼성전자의 2024-01-01 종가는?")
        print("- 2024-07-15 KOSPI 지수는?")
        print("- 2024-08-16에 상승한 종목은 몇 개?")
        print("- 등락률이 +5% 이상인 종목을 알려줘")
        print("- RSI가 70 이상인 과매수 종목은?")
        print()
    
    def _show_capabilities(self):
        """Show agent capabilities"""
        capabilities = self.agent.get_capabilities()
        print("\nFinance Agent 기능:")
        
        print("\n지원되는 질문 유형:")
        for query_type in capabilities['supported_queries']:
            print(f"- {query_type}")
        
        print("\n데이터 소스:")
        for source in capabilities['data_sources']:
            print(f"- {source}")
        
        print("\n응답 유형:")
        for response_type in capabilities['response_types']:
            print(f"- {response_type}")
        print()
    
    def _reset_session(self):
        """Reset current session"""
        if self.current_session_id:
            self.agent.clear_session(self.current_session_id)
            self.current_session_id = None
            print("세션이 초기화되었습니다.")
        else:
            print("초기화할 세션이 없습니다.")
    
    def _show_session_status(self):
        """Show current session status"""
        if self.current_session_id:
            status = self.agent.get_session_status(self.current_session_id)
            print(f"\\n현재 세션 상태:")
            print(f"- 세션 ID: {status['session_id'][:8]}...")
            print(f"- 상호작용 횟수: {status['interaction_count']}")
            print(f"- 컨텍스트 보유: {status['has_context']}")
            if status['context']:
                print(f"- 수집된 정보: {status['context']}")
            print()
        else:
            print("활성 세션이 없습니다.")

if __name__ == "__main__":
    interface = FinanceAgentInterface()
    interface.start_conversation()