import uuid
from typing import Dict, List, TypedDict
from langgraph.graph import StateGraph, END
from finance_agent.nodes.input_node import InputNode
from finance_agent.nodes.query_parser_node import QueryParserNode
from finance_agent.nodes.sql_generator_node import SqlGeneratorNode
from finance_agent.nodes.sql_refiner_node import SqlRefinerNode
from finance_agent.nodes.output_formatter_node import OutputFormatterNode

class GraphState(TypedDict):
    user_query: str
    session_id: str
    clarification_needed: bool
    clarification_question: str
    clarification_count: int
    needs_user_input: bool

    parsed_query: Dict
    sql_query: str
    sql_attempts: int
    sql_error: str

    query_results: List[Dict]
    final_output: str

    is_complete: bool


class FinanceAgent:
    """Graph-based agent for stock and news queries."""

    def __init__(self):
        self.input_node = InputNode()
        self.query_parser_node = QueryParserNode()
        self.sql_generator_node = SqlGeneratorNode()
        self.sql_refiner_node = SqlRefinerNode()
        self.output_formatter_node = OutputFormatterNode()
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(GraphState)

        workflow.add_node("input_handler", self.input_handler)
        workflow.add_node("query_parser", self.query_parser)
        workflow.add_node("sql_generator", self.sql_generator)
        workflow.add_node("sql_refiner", self.sql_refiner)
        workflow.add_node("output_formatter", self.output_formatter)

        workflow.set_entry_point("input_handler")

        workflow.add_conditional_edges(
            "input_handler",
            self.route_after_input,
            {"end": END, "query_parser": "query_parser"}
        )

        workflow.add_conditional_edges(
            "query_parser",
            self.route_after_query_parser,
            {"end": END, "sql_generator": "sql_generator"}
        )

        workflow.add_conditional_edges(
            "sql_generator",
            self.route_after_sql_generation,
            {"refine": "sql_refiner", "format": "output_formatter"}
        )

        workflow.add_conditional_edges(
            "sql_refiner",
            self.route_after_refine,
            {"retry": "sql_refiner", "format": "output_formatter"}
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
            if state.get("clarification_count", 0) < 2:
                state["is_complete"] = False
                state["needs_user_input"] = True
                state["clarification_count"] += 1
                return "input_handler"
            else:
                state["final_output"] = "정보가 부족하여 질문을 이해하지 못했습니다. 더 구체적으로 질문해 주세요."
                state["is_complete"] = True
                return "end"
        return "query_parser"

    def route_after_query_parser(self, state: GraphState) -> str:
        if state.get("is_complete", False):
            return "end"
        return "sql_generator"

    def route_after_sql_generation(self, state: GraphState) -> str:
        # 뉴스 요약인 경우 SQL 에러 여부와 관계없이 output으로 바로
        if state.get("parsed_query", {}).get("intent", "").endswith("_request"):
            return "format"
        return "refine" if state["sql_error"] else "format"

    def route_after_refine(self, state: GraphState) -> str:
        if state["sql_error"] and state["sql_attempts"] < 3:
            return "retry"
        return "format"

    def process_query(self, user_query: str, session_id: str = None) -> Dict:
        if session_id is None:
            session_id = str(uuid.uuid4())
        initial_state = {
            "user_query": user_query,
            "session_id": session_id,
            "clarification_needed": False,
            "clarification_count": 0,
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
                "is_complete": result.get("is_complete", True),
                "session_id": session_id,
                "sql_query": result.get("sql_query", ""),
                "sql_attempts": result.get("sql_attempts", 0),
            }
        except Exception as e:
            return {
                "response": f"처리 중 오류가 발생했습니다: {e}",
                "needs_user_input": False,
                "is_complete": True,
                "session_id": session_id,
                "sql_query": "",
                "sql_attempts": 0,
            }

    def handle_clarification_response(self, original_query, clarification, session_id, clarification_count=0):
        combined_query = f"사용자 질문: {original_query}, 추가 정보: {clarification}"
        return self.process_query(combined_query, session_id=session_id)

class FinanceAgentInterface:
    def __init__(self):
        self.framework = FinanceAgent()
        self.current_session_id = None

    def start_conversation(self):
        print("=== KU-gent ===")
        while True:
            try:
                user_input = input("🧑: ").strip()
                if user_input.lower() == 'quit':
                    print("Agent를 종료합니다.")
                    break
                if not user_input:
                    continue

                result = self.framework.process_query(user_input, self.current_session_id)
                self.current_session_id = result["session_id"]
                print(f"🤖: {result['response']}")

                if result.get("needs_user_input", False):
                    clarification = input("🤖: 추가 정보를 입력해주세요: ").strip()
                    if clarification:
                        clarified = self.framework.handle_clarification_response(
                            user_input, clarification, self.current_session_id,
                            clarification_count=result.get("clarification_count", 0)
                        )
                        print(f"🤖: {clarified['response']}")

                if result.get("sql_query"):
                    print(f"[SQL] {result['sql_query']}")
                if result.get("sql_attempts", 0) > 1:
                    print(f"[재시도] {result['sql_attempts']}번")
            except KeyboardInterrupt:
                print("\nAgent 중단")
                break
            except Exception as e:
                print(f"오류: {e}")



if __name__ == "__main__":
    interface = FinanceAgentInterface()
    interface.start_conversation()

'''

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
    clarification_count: int
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
        """Handle input using input node"""
        return self.input_node.process(state)
    
    def query_parser(self, state: GraphState) -> GraphState:
        """Parse query using query parser node"""
        return self.query_parser_node.process(state)
    
    def sql_generator(self, state: GraphState) -> GraphState:
        """Generate SQL using sql generator node"""
        return self.sql_generator_node.process(state)
    
    def sql_refiner(self, state: GraphState) -> GraphState:
        """Refine SQL using sql refiner node"""
        return self.sql_refiner_node.process(state)
    
    def output_formatter(self, state: GraphState) -> GraphState:
        """Format output using output formatter node"""
        return self.output_formatter_node.process(state)
    
    def route_after_input(self, state: GraphState) -> str:
        if state["clarification_needed"]:
            # clarification 시도 횟수 2회 미만만 되묻기
            if state.get("clarification_count", 0) < 2:
                state["is_complete"] = False
                state["needs_user_input"] = True
                state["clarification_count"] = state.get("clarification_count", 0) + 1
                return "input_handler" # 로 보내기..
            else:
                # 2회 이상이면 중단/안내 메시지
                state["final_output"] = "정보가 부족하여 질문을 이해하지 못했습니다. 더 구체적으로 질문해 주세요."
                state["is_complete"] = True
                state["needs_user_input"] = False
                return "end"
        else:
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
    
    def process_query(self, user_query: str, session_id: str = None) -> Dict:
        """Process user query through  framework"""
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        initial_state = {
            "user_query": user_query,
            "session_id": session_id,
            "clarification_needed": False,
            "clarification_count": 0, 
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
    
    def handle_clarification_response(self, original_query, clarification, session_id, clarification_count=0):
        combined_query = f"사용자 질문: {original_query}, 추가 정보: {clarification}"
        return self.process_query(
            combined_query, 
            session_id=session_id,
            clarification_count=clarification_count
        )


class FinanceAgentInterface:
    """Interface for graph framework"""
    def __init__(self):
        self.framework = FinanceAgent()
        self.current_session_id = None
    
    def start_conversation(self):
        """Start conversation with  framework"""
        print("=== KU-gent ===")
        print("한국 주식 데이터에 대해 질문해보세요.'quit'를 입력하면 종료됩니다.\n")
        
        while True:
            try:
                user_input = input("🧑: ").strip()
                
                if user_input.lower() == 'quit':
                    print("Agent를 종료합니다.")
                    break
                
                if not user_input:
                    continue
                
                # Process query
                result = self.framework.process_query(user_input, self.current_session_id)
                self.current_session_id = result["session_id"]
                
                response = result['response'] if result['response'] else result.get("clarification_question")
                print(f"🤖: {response}")

                # Handle clarification if needed
                if result.get("needs_user_input", False):
                    clarification = input("🤖: 추가 정보를 입력해주세요: ").strip()
                    if clarification:
                        clarified_result = self.framework.handle_clarification_response(
                            user_input, clarification, self.current_session_id, clarification_count=result.get("clarification_count", 0)
                        )
                        print(f"🤖: {clarified_result['response']}")
                
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

'''