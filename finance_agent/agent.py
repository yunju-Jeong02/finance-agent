# finance_agent/agent.py (이 코드로 파일 전체를 교체하세요)

import uuid
from typing import Dict, List, TypedDict, Sequence
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage

from finance_agent.nodes.input_node import InputNode
from finance_agent.nodes.query_parser_node import QueryParserNode
from finance_agent.nodes.sql_generator_node import SqlGeneratorNode
from finance_agent.nodes.sql_refiner_node import SqlRefinerNode
from finance_agent.nodes.output_formatter_node import OutputFormatterNode
from finance_agent.nodes.news_handler import NewsHandler

class GraphState(TypedDict):
    """State for graph framework"""
    user_query: str
    # ✨ 1. 대화 기록을 저장할 공간 추가
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


class FinanceAgent:
    """ graph framework using separated nodes"""
    def __init__(self):
        self.input_node = InputNode()
        self.query_parser_node = QueryParserNode()
        self.sql_generator_node = SqlGeneratorNode()
        self.sql_refiner_node = SqlRefinerNode()
        self.output_formatter_node = OutputFormatterNode()
        self.news_node = NewsHandler()
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(GraphState)
        
        workflow.add_node("input_handler", self.input_handler)
        workflow.add_node("query_parser", self.query_parser)
        workflow.add_node("sql_generator", self.sql_generator)
        workflow.add_node("sql_refiner", self.sql_refiner)
        workflow.add_node("output_formatter", self.output_formatter)
        workflow.add_node("news_handler", self.news_handler)
        
        workflow.set_entry_point("input_handler")
        
        workflow.add_conditional_edges("input_handler", self.route_after_input, {"end": END, "query_parser": "query_parser"})
        workflow.add_conditional_edges("query_parser", self.route_after_query_parser, {"end": END, "sql_generator": "sql_generator", "news_handler": "news_handler"})
        workflow.add_conditional_edges("sql_generator", self.route_after_sql_generation, {"refine": "sql_refiner", "format": "output_formatter"})
        workflow.add_conditional_edges("sql_refiner", self.route_after_refine, {"retry": "sql_refiner", "format": "output_formatter", "end": END})
        
        workflow.add_edge("output_formatter", END)
        workflow.add_edge("news_handler", END)
        
        return workflow.compile()
    
    def input_handler(self, state: GraphState) -> GraphState: return self.input_node.process(state)
    def query_parser(self, state: GraphState) -> GraphState: return self.query_parser_node.process(state)
    def sql_generator(self, state: GraphState) -> GraphState: return self.sql_generator_node.process(state)
    def sql_refiner(self, state: GraphState) -> GraphState: return self.sql_refiner_node.process(state)
    def output_formatter(self, state: GraphState) -> GraphState: return self.output_formatter_node.process(state)
    def news_handler(self, state: GraphState) -> GraphState: return self.news_node.process(state)

    def route_after_input(self, state: GraphState) -> str: return "end" if state["clarification_needed"] else "query_parser"
    def route_after_query_parser(self, state: GraphState) -> str:
        if state.get("is_complete", False): return "end"
        
        parsed = state.get("parsed_query", {})
        # 사용자의 프롬프트 출력 형식에 맞게 intent 추출
        intent = parsed.get("intent")
        if not intent and "entities" in parsed: # entities 형식일 경우
             if any(kw in parsed["entities"].get("keywords", []) for kw in ["뉴스", "요약"]):
                 intent = "news_request"

        return "news_handler" if intent and "news" in intent else "sql_generator"
        
    def route_after_sql_generation(self, state: GraphState) -> str: return "refine" if state["sql_error"] else "format"
    def route_after_refine(self, state: GraphState) -> str:
        if state["sql_error"] and state["sql_attempts"] < 3: return "retry"
        elif not state["sql_error"]: return "format"
        else: return "end"

    # ✨ 2. process_query가 chat_history를 받도록 수정
    def process_query(self, user_query: str, session_id: str = None, chat_history: list = []) -> Dict:
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        initial_state = {
            "user_query": user_query,
            # ✨ 3. 초기 상태에 대화 기록 추가
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
        
        try:
            result = self.graph.invoke(initial_state)
            return {
                "clarification_question": result.get("clarification_question", ""),
                "response": result.get("final_output", ""),
                "needs_user_input": result.get("needs_user_input", False),
                "is_complete": result.get("is_complete", False),
                "session_id": session_id,
                "sql_query": result.get("sql_query", ""),
                "sql_attempts": result.get("sql_attempts", 0),
            }
        except Exception as e:
            return {"response": f"처리 중 오류가 발생했습니다: {e}", "is_complete": True, "session_id": session_id}