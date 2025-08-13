import uuid
import copy
from typing import Dict, List, TypedDict, Sequence
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage
from datetime import datetime

# Assuming all your nodes are imported correctly
from finance_agent.nodes.input_node import InputNode
from finance_agent.nodes.query_parser_node import QueryParserNode
from finance_agent.nodes.sql_generator_node import SqlGeneratorNode
from finance_agent.nodes.sql_refiner_node import SqlRefinerNode
from finance_agent.nodes.output_formatter_node import OutputFormatterNode
from finance_agent.nodes.news_handler import NewsHandler


class GraphState(TypedDict):
    """State for graph framework"""
    user_query: str
    chat_history: Sequence[BaseMessage]
    session_id: str
    clarification_needed: bool
    clarification_question: str
    needs_user_input: bool
    parsed_query: Dict
    sql_query: str
    sql_attempts: int
    sql_error: str
    query_results: List[Dict]
    final_output: str
    is_complete: bool
    # pending_action은 더 이상 사용하지 않음


class FinanceAgent:
    """ graph framework using separated nodes"""
    def __init__(self):
        # Initialize nodes
        self.input_node = InputNode()
        self.query_parser_node = QueryParserNode()
        self.sql_generator_node = SqlGeneratorNode()
        self.sql_refiner_node = SqlRefinerNode()
        self.output_formatter_node = OutputFormatterNode()
        self.news_node = NewsHandler()
        
        # Build graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build graph framework"""
        workflow = StateGraph(GraphState)
        
        # Add nodes
        workflow.add_node("input_handler", self.input_handler)
        workflow.add_node("query_parser", self.query_parser)
        workflow.add_node("sql_generator", self.sql_generator)
        workflow.add_node("sql_refiner", self.sql_refiner)
        workflow.add_node("output_formatter", self.output_formatter)
        workflow.add_node("news_handler", self.news_handler)
        
        # Set entry point
        workflow.set_entry_point("input_handler")
        
        # input -> query_parser (직접 연결)
        workflow.add_edge("input_handler", "query_parser")

        # query_parser -> (router)
        workflow.add_conditional_edges(
            "query_parser",
            self.route_after_query_parser,
            {
                "end": END,
                "sql_generator": "sql_generator",
                "news_handler": "news_handler",
            }
        )
            
        # sql_generator -> refine/format
        workflow.add_conditional_edges(
            "sql_generator",
            self.route_after_sql_generation,
            {
                "refine": "sql_refiner",
                "format": "output_formatter"
            }
        )
        
        # sql_refiner -> retry/format
        workflow.add_conditional_edges(
            "sql_refiner",
            self.route_after_refine,
            {
                "retry": "sql_refiner",
                "format": "output_formatter"
            }
        )
        
        # terminal edges
        workflow.add_edge("output_formatter", END)
        workflow.add_edge("news_handler", END)
        
        return workflow.compile()
    
    # ---- Node wrappers ----
    def input_handler(self, state: GraphState) -> GraphState:
        return self.input_node.process(state)

    def query_parser(self, state: GraphState) -> GraphState:
        return self.query_parser_node.process(state)
    
    def sql_generator(self, state: GraphState) -> GraphState:
        return self.sql_generator_node.process(state)
    
    def sql_refiner(self, state: GraphState) -> GraphState:
        return self.sql_refiner_node.process(state)
    
    def output_formatter(self, state: GraphState) -> GraphState:
        return self.output_formatter_node.process(state)
    
    def news_handler(self, state: GraphState) -> GraphState:
        return self.news_node.process(state)
    
    # ---- Routers ----
    def route_after_query_parser(self, state: GraphState) -> str:
        if state.get("is_complete", False):
            return "end"
        intent = state.get("parsed_query", {}).get("intent", "")
        if intent.endswith("_news_request") or intent.endswith("_summary_request"):
            return "news_handler"
        return "sql_generator"
    
    def route_after_sql_generation(self, state: GraphState) -> str:
        """Route after SQL generation"""
        if state.get("sql_error"):
            return "refine"
        else:
            return "format"
    
    def route_after_refine(self, state: GraphState) -> str:
        """Route after SQL refinement"""
        if state.get("sql_error") and state.get("sql_attempts", 0) < 3:
            return "retry"
        else:
            return "format"
    
    # ---- Public API ----
    def process_query(self, user_query: str, session_id: str = None, chat_history: list = None, initial_state: Dict = None) -> Dict:
        if session_id is None:
            session_id = str(uuid.uuid4())

        if chat_history is None:
            chat_history = []

        if initial_state is None:
            initial_state = {
                "user_query": user_query,
                "chat_history": chat_history,
                "session_id": session_id,
                "clarification_needed": False,
                "clarification_question": "",
                "needs_user_input": False,
                "parsed_query": {},
                "sql_query": "",
                "sql_attempts": 0,
                "sql_error": "",
                "query_results": [],
                "final_output": "",
                "is_complete": False
            }
        else:
            initial_state["user_query"] = user_query

        try:
            result_state = self.graph.invoke(initial_state)
            return {
                "clarification_question": result_state.get("clarification_question"),
                "response": result_state.get("final_output"),
                "needs_user_input": result_state.get("needs_user_input", False),
                "is_complete": result_state.get("is_complete", False),
                "session_id": session_id,
                "sql_query": result_state.get("sql_query", ""),
                "sql_attempts": result_state.get("sql_attempts", 0),
                "state": result_state,
            }
        except Exception as e:
            return {
                "response": f"처리 중 오류가 발생했습니다: {str(e)}",
                "needs_user_input": False,
                "is_complete": True,
                "session_id": session_id,
                "sql_query": "",
                "sql_attempts": 0,
            }


class FinanceAgentInterface:
    """Interface for graph framework"""
    def __init__(self):
        self.framework = FinanceAgent()
        self.current_session_id = None
    
    def start_conversation(self):
        print("=== KU-gent v2.6 (Stable) ===")
        print("'뉴스 스케줄링', '스케줄 취소', '스케줄 확인'이라고 말씀해보세요. '종료' 입력 시 종료됩니다.\n")

        while True:
            try:
                user_input = input("🧑: ").strip()
                if user_input.lower() in ('quit', '종료', 'exit'):
                    print("Agent를 종료합니다.")
                    break
                if not user_input:
                    continue

                result = self.framework.process_query(
                    user_input,
                    self.current_session_id,
                )
                self.current_session_id = result["session_id"]
                
                response = result.get('response') or result.get("clarification_question") or ""
                print(f"🤖: {response}")

                if result.get("sql_query"):
                    print(f"[SQL] {result['sql_query']}")
                if result.get("sql_attempts", 0) > 1:
                    print(f"[재시도] {result['sql_attempts']}번")
                print()

            except KeyboardInterrupt:
                print("\n\n대화를 중단합니다.")
                break
            except Exception as e:
                print(f"오류: {e}")
                continue


if __name__ == "__main__":
    interface = FinanceAgentInterface()
    interface.start_conversation()