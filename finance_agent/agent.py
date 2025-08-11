"""
 Graph Framework for Financial Data Queries
Uses separated nodes for better maintainability
"""

import uuid
from typing import Dict, List, TypedDict
from langgraph.graph import StateGraph, END

from finance_agent.nodes.input_node import InputNode
from finance_agent.nodes.query_parser_node import QueryParserNode
from finance_agent.nodes.sql_generator_node import SqlGeneratorNode
from finance_agent.nodes.sql_refiner_node import SqlRefinerNode
from finance_agent.nodes.output_formatter_node import OutputFormatterNode


class GraphState(TypedDict):
    """State for  graph framework"""
    user_query: str
    session_id: str
    clarification_needed: bool
    clarification_question: str
    needs_user_input: bool
    parsed_query: str
    sql_query: str
    sql_attempts: int
    sql_error: str
    query_results: List[Dict]
    final_output: str
    is_complete: bool


class FinanceAgent:
    """ graph framework using separated nodes"""
    def __init__(self):
        # Initialize nodes
        self.input_node = InputNode()
        self.query_parser_node = QueryParserNode()
        self.sql_generator_node = SqlGeneratorNode()
        self.sql_refiner_node = SqlRefinerNode()
        self.output_formatter_node = OutputFormatterNode()
        
        # Build graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build  graph framework"""
        workflow = StateGraph(GraphState)
        
        # Add nodes
        workflow.add_node("input_handler", self.input_handler)
        workflow.add_node("query_parser", self.query_parser)
        workflow.add_node("sql_generator", self.sql_generator)
        workflow.add_node("sql_refiner", self.sql_refiner)
        workflow.add_node("output_formatter", self.output_formatter)
        
        # Set entry point
        workflow.set_entry_point("input_handler")
        
        workflow.add_conditional_edges(
            "input_handler",
            self.route_after_input,
            {
                "end": END,  # clarification_needed일 때 바로 END
                "query_parser": "query_parser"
            }
        )

        workflow.add_conditional_edges(
            "query_parser",
            self.route_after_query_parser,
            {
                "end": END,
                "sql_generator": "sql_generator"
            }
        )
                
        workflow.add_conditional_edges(
            "sql_generator",
            self.route_after_sql_generation,
            {
                "refine": "sql_refiner",
                "format": "output_formatter"
            }
        )
        
        workflow.add_conditional_edges(
            "sql_refiner",
            self.route_after_refine,
            {
                "retry": "sql_refiner",
                "format": "output_formatter"
            }
        )
        
        workflow.add_edge("output_formatter", END)
        
        return workflow.compile()
    
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
    
    def route_after_input(self, state: GraphState) -> str:
        if state["clarification_needed"]:
            return "end"
        return "query_parser"
        
    def route_after_query_parser(self, state: GraphState) -> str:
        if state.get("is_complete", False):
            return "end"
        return "sql_generator"
    
    def route_after_sql_generation(self, state: GraphState) -> str:
        """Route after SQL generation"""
        if state["sql_error"]:
            return "refine"
        else:
            return "format"
    
    def route_after_refine(self, state: GraphState) -> str:
        """Route after SQL refinement"""
        if state["sql_error"] and state["sql_attempts"] < 3:
            return "retry"
        else:
            return "format"
    
    def process_query(self, user_query: str, session_id: str = None, clarification_count: int = 0) -> Dict:
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        
        initial_state = {
            "user_query": user_query,
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
            # print('[FinanceAgent] Initial_state:', initial_state)  # 디버깅용
            
            # Process the initial state through the graph
            result = self.graph.invoke(initial_state)

            # print(f"[FinanceAgent] Processed state: {result}")  # 디버깅용
            
            return {
                "clarification_question": result["clarification_question"],
                "response": result["final_output"],
                "needs_user_input": result.get("needs_user_input", False),
                "is_complete": result["is_complete"],
                "session_id": session_id,
                "sql_query": result.get("sql_query", ""),
                "sql_attempts": result.get("sql_attempts", 0),
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
        """Start conversation with the framework"""
        print("=== KU-gent ===")
        print("한국 주식 데이터에 대해 질문해보세요. 'quit'를 입력하면 종료됩니다.\n")
        
        clarification_count = 0  # 인터페이스에서 관리

        while True:
            try:
                user_input = input("🧑: ").strip()
                
                if user_input.lower() == 'quit':
                    print("Agent를 종료합니다.")
                    break
                
                if not user_input:
                    continue
                
                # Process query
                result = self.framework.process_query(
                    user_input,
                    self.current_session_id,
                )
                self.current_session_id = result["session_id"]
                
                # 출력할 응답
                response = result['response'] if result['response'] else result.get("clarification_question")
                print(f"🤖: {response}")

                # Clarification 필요 시
                if result.get("needs_user_input", False):
                    if clarification_count < 2:
                        clarification = input("추가 정보를 입력해주세요: ").strip()
                        if clarification:
                            clarification_count += 1  # 카운트 증가
                            clarification_question = result.get("clarification_question", "")
                            # print(clarification_count)
                            result = self.framework.process_query(
                                user_query=f"사용자 요청: {user_input} \n 추가 질문: {clarification_question} \n 추가 질문에 대한 사용자 응답: {clarification}",
                                session_id=self.current_session_id,
                            )
                            response = result['response'] if result['response'] else result.get("clarification_question")
                            print(f"🤖: {response}")
                        else:
                            print("🤖: 추가 정보가 없어 대화를 종료합니다.")
                            break
                    else:
                        # 이미 2회 요청했으면 종료
                        print("🤖: 정보가 부족하여 질문을 이해하지 못했습니다. 다시 질문해 주세요.")
                        break
                else:
                    clarification_count = 0  # 성공적으로 처리되면 카운트 초기화

                # Debug info
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