
'''
import uuid
import logging
import os
import traceback
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
    pending_action: Dict


class FinanceAgent:
    def __init__(self):
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        logging.basicConfig(
            level=logging.DEBUG,
            filename=os.path.join(log_dir, 'finance_agent.log'),
            filemode='a',
            format='%(asctime)s %(levelname)s:%(message)s'
        )

        self.input_node = InputNode()
        self.query_parser_node = QueryParserNode()
        self.sql_generator_node = SqlGeneratorNode()
        self.sql_refiner_node = SqlRefinerNode()
        self.output_formatter_node = OutputFormatterNode()
        self.graph = self._build_graph()
        self.last_state: GraphState = {}

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(GraphState)
        workflow.add_node("input_handler", self.input_handler)
        workflow.add_node("query_parser", self.query_parser)
        workflow.add_node("sql_generator", self.sql_generator)
        workflow.add_node("sql_refiner", self.sql_refiner)
        workflow.add_node("output_formatter", self.output_formatter)

        workflow.set_entry_point("input_handler")

        # 1) 입력 처리 후 분기
        workflow.add_conditional_edges(
            "input_handler",
            self.route_after_input,
            {"end": END, "query_parser": "query_parser"}
        )
        # 2) 파싱 후에도 clarification_needed 체크
        workflow.add_conditional_edges(
            "query_parser",
            self.route_after_query_parser,
            {"end": END, "sql_generator": "sql_generator"}
        )
        # 3) SQL 생성 분기
        workflow.add_conditional_edges(
            "sql_generator",
            self.route_after_sql_generation,
            {"refine": "sql_refiner", "format": "output_formatter"}
        )
        # 4) 리파인 분기
        workflow.add_conditional_edges(
            "sql_refiner",
            self.route_after_refine,
            {"retry": "sql_refiner", "format": "output_formatter"}
        )
        # 5) 최종 포맷터 → END
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
        # 🔥 핫뉴스 키워드 선택 단계 처리: 숫자 입력 시 SQL 건너뛰고 바로 output_formatter로 이동
        if state.get("pending_action", {}).get("type") == "hot_news_select":
            try:
                choice_idx = int(state["user_query"].strip()) - 1
                options = state["pending_action"]["options"]
                if 0 <= choice_idx < len(options):
                    selected = options[choice_idx]
                    state["parsed_query"] = selected["query"]
                    state["clarification_needed"] = False
                    state["clarification_question"] = ""
                    state["needs_user_input"] = False
                    return "output_formatter"
                else:
                    state["final_output"] = "1~5 사이의 숫자를 입력해 주세요."
                    state["needs_user_input"] = True
                    return "end"
            except ValueError:
                state["final_output"] = "숫자를 정확히 입력해 주세요."
                state["needs_user_input"] = True
                return "end"

        # 🔍 일반 Clarification 처리
        if state["clarification_needed"]:
            if state.get("clarification_count", 0) < 2:
                state["final_output"] = state["clarification_question"]
                state["needs_user_input"] = True
                state["clarification_count"] += 1
                return "end"
            else:
                state["final_output"] = "정보가 부족하여 질문을 이해하지 못했습니다. 더 구체적으로 질문해 주세요."
                state["is_complete"] = True
                state["needs_user_input"] = False
                return "end"

        return "query_parser"

    def route_after_query_parser(self, state: GraphState) -> str:
        # 파싱 직후에도 모호함 요청 처리
        if state["clarification_needed"]:
            state["final_output"] = state["clarification_question"]
            state["needs_user_input"] = True
            return "end"
        if state.get("is_complete", False):
            return "end"
        return "sql_generator"

    def route_after_sql_generation(self, state: GraphState) -> str:
        intent = state.get("parsed_query", {}).get("intent", "")
        if intent.endswith("_news_request") or intent.endswith("_summary_request") or intent == "hot_news_request":
            return "format"
        return "refine" if state.get("sql_error") else "format"

    def route_after_refine(self, state: GraphState) -> str:
        if state["sql_error"] and state["sql_attempts"] < 3:
            return "retry"
        return "format"

    def process_query(self, user_query: str, session_id: str = None, clarification_count: int = 0) -> Dict:
        if session_id is None:
            session_id = str(uuid.uuid4())

        pending = self.last_state or {}
        initial_state: GraphState = {
            "user_query": user_query,
            "session_id": session_id,
            "clarification_needed": False,
            "clarification_question": "",
            "clarification_count": clarification_count,
            "needs_user_input": False,
            "parsed_query": {},
            "sql_query": "",
            "sql_attempts": 0,
            "sql_error": "",
            "query_results": [],
            "final_output": "",
            "is_complete": False,
            "pending_action": pending.get("pending_action", {}) if isinstance(pending, dict) else {},
        }

        self.last_state = initial_state
        try:
            result = self.graph.invoke(initial_state)
            self.last_state = result
            return {
                "clarification_question": result.get("clarification_question", ""),
                "response": result.get("final_output", ""),
                "needs_user_input": result.get("needs_user_input", False),
                "is_complete": result.get("is_complete", True),
                "session_id": session_id,
                "sql_query": result.get("sql_query", ""),
                "sql_attempts": result.get("sql_attempts", 0),
                "clarification_count": result.get("clarification_count", clarification_count),
            }
        except Exception as e:
            logging.error("process_query error:\n%s", traceback.format_exc())
            return {
                "response": f"처리 중 오류가 발생했습니다: {e}",
                "needs_user_input": False,
                "is_complete": True,
                "session_id": session_id,
                "sql_query": "",
                "sql_attempts": 0,
                "clarification_count": clarification_count,
            }

    def handle_clarification_response(
        self,
        original_query: str,
        clarification: str,
        session_id: str,
        clarification_count: int = 0
    ) -> Dict:
        # 마지막 상태를 복사해서 clarification 주입
        state = self.last_state.copy()  # type: ignore
        state["user_query"] = f"{original_query}, 추가 정보: {clarification}"
        state["clarification_needed"] = False
        state["clarification_question"] = ""
        state["needs_user_input"] = False
        state["clarification_count"] = clarification_count

        logging.debug("▶ handle_clarification_response in state: %r", state)
        try:
            new_state = self.graph.invoke(state)
            self.last_state = new_state
            return {
                "clarification_question": new_state.get("clarification_question", ""),
                "response": new_state.get("final_output", ""),
                "needs_user_input": new_state.get("needs_user_input", False),
                "is_complete": new_state.get("is_complete", True),
                "session_id": session_id,
                "sql_query": new_state.get("sql_query", ""),
                "sql_attempts": new_state.get("sql_attempts", 0),
                "clarification_count": new_state.get("clarification_count", 0),
            }
        except Exception as e:
            logging.error("handle_clarification_response error:\n%s", traceback.format_exc())
            return {
                "response": f"처리 중 오류가 발생했습니다: {e}",
                "needs_user_input": False,
                "is_complete": True,
                "session_id": session_id,
                "sql_query": "",
                "sql_attempts": 0,
                "clarification_count": clarification_count,
            }

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
                response = result['response'] if result['response'] else result.get("clarification_question")
                self.current_session_id = result["session_id"]
                # clarification 질문이거나 최종 답변이거나, response 에 담긴 텍스트를 항상 출력
                print(f"🤖: {response}")

                if result.get("needs_user_input", False):
                    # 실제 모델이 생성한 clarification_question 사용
                    cq = result.get("clarification_question", "").strip()
                    clarification = input(f"🤖: {cq}\n🧑: ").strip()
                    if clarification:
                        clarified = self.framework.handle_clarification_response(
                            user_input,
                            clarification,
                            self.current_session_id,
                            clarification_count=result.get("clarification_count", 0)
                        )
                        self.current_session_id = clarified["session_id"]
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
'''

import uuid
import logging
import os
import traceback
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
    pending_action: Dict


class FinanceAgent:
    def __init__(self):
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        logging.basicConfig(
            level=logging.DEBUG,
            filename=os.path.join(log_dir, 'finance_agent.log'),
            filemode='a',
            format='%(asctime)s %(levelname)s:%(message)s'
        )

        self.input_node = InputNode()
        self.query_parser_node = QueryParserNode()
        self.sql_generator_node = SqlGeneratorNode()
        self.sql_refiner_node = SqlRefinerNode()
        self.output_formatter_node = OutputFormatterNode()
        self.graph = self._build_graph()
        self.last_state: GraphState = {}

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(GraphState)
        workflow.add_node("input_handler", self.input_handler)
        workflow.add_node("query_parser", self.query_parser)
        workflow.add_node("sql_generator", self.sql_generator)
        workflow.add_node("sql_refiner", self.sql_refiner)
        workflow.add_node("output_formatter", self.output_formatter)

        workflow.set_entry_point("input_handler")

        # 1) 입력 처리 후 분기
        workflow.add_conditional_edges(
            "input_handler",
            self.route_after_input,
            {"end": END, "query_parser": "query_parser"}
        )
        # 2) 파싱 후에도 clarification_needed 체크
        workflow.add_conditional_edges(
            "query_parser",
            self.route_after_query_parser,
            {"end": END, "sql_generator": "sql_generator"}
        )
        # 3) SQL 생성 분기
        workflow.add_conditional_edges(
            "sql_generator",
            self.route_after_sql_generation,
            {"refine": "sql_refiner", "format": "output_formatter"}
        )
        # 4) 리파인 분기
        workflow.add_conditional_edges(
            "sql_refiner",
            self.route_after_refine,
            {"retry": "sql_refiner", "format": "output_formatter"}
        )
        # 5) 최종 포맷터 → END
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
        # 🔥 핫뉴스 키워드 선택 단계 처리: 숫자 입력 시 SQL 건너뛰고 바로 output_formatter로 이동
        if state.get("pending_action", {}).get("type") == "hot_news_select":
            try:
                choice_idx = int(state["user_query"].strip()) - 1
                options = state["pending_action"]["options"]
                if 0 <= choice_idx < len(options):
                    selected = options[choice_idx]
                    state["parsed_query"] = selected["query"]
                    state["clarification_needed"] = False
                    state["clarification_question"] = ""
                    state["needs_user_input"] = False
                    return "output_formatter"
                else:
                    state["final_output"] = "1~5 사이의 숫자를 입력해 주세요."
                    state["needs_user_input"] = True
                    return "end"
            except ValueError:
                state["final_output"] = "숫자를 정확히 입력해 주세요."
                state["needs_user_input"] = True
                return "end"

        # 🔍 일반 Clarification 처리
        if state["clarification_needed"]:
            if state.get("clarification_count", 0) < 2:
                state["final_output"] = state["clarification_question"]
                state["needs_user_input"] = True
                state["clarification_count"] += 1
                return "end"
            else:
                state["final_output"] = "정보가 부족하여 질문을 이해하지 못했습니다. 더 구체적으로 질문해 주세요."
                state["is_complete"] = True
                state["needs_user_input"] = False
                return "end"

        return "query_parser"

    def route_after_query_parser(self, state: GraphState) -> str:
        # 파싱 직후에도 모호함 요청 처리
        if state["clarification_needed"]:
            state["final_output"] = state["clarification_question"]
            state["needs_user_input"] = True
            return "end"
        if state.get("is_complete", False):
            return "end"
        return "sql_generator"

    def route_after_sql_generation(self, state: GraphState) -> str:
        intent = state.get("parsed_query", {}).get("intent", "")
        if intent.endswith("_news_request") or intent.endswith("_summary_request") or intent == "hot_news_request":
            return "format"
        return "refine" if state.get("sql_error") else "format"

    def route_after_refine(self, state: GraphState) -> str:
        if state["sql_error"] and state["sql_attempts"] < 3:
            return "retry"
        return "format"

    def process_query(self, user_query: str, session_id: str = None, clarification_count: int = 0) -> Dict:
        if session_id is None:
            session_id = str(uuid.uuid4())

        pending = self.last_state or {}
        initial_state: GraphState = {
            "user_query": user_query,
            "session_id": session_id,
            "clarification_needed": False,
            "clarification_question": "",
            "clarification_count": clarification_count,
            "needs_user_input": False,
            "parsed_query": {},
            "sql_query": "",
            "sql_attempts": 0,
            "sql_error": "",
            "query_results": [],
            "final_output": "",
            "is_complete": False,
            "pending_action": pending.get("pending_action", {}) if isinstance(pending, dict) else {},
        }

        self.last_state = initial_state
        try:
            result = self.graph.invoke(initial_state)
            self.last_state = result
            return {
                "clarification_question": result.get("clarification_question", ""),
                "response": result.get("final_output", ""),
                "needs_user_input": result.get("needs_user_input", False),
                "is_complete": result.get("is_complete", True),
                "session_id": session_id,
                "sql_query": result.get("sql_query", ""),
                "sql_attempts": result.get("sql_attempts", 0),
                "clarification_count": result.get("clarification_count", clarification_count),
            }
        except Exception as e:
            logging.error("process_query error:\n%s", traceback.format_exc())
            return {
                "response": f"처리 중 오류가 발생했습니다: {e}",
                "needs_user_input": False,
                "is_complete": True,
                "session_id": session_id,
                "sql_query": "",
                "sql_attempts": 0,
                "clarification_count": clarification_count,
            }

    def handle_clarification_response(
        self,
        original_query: str,
        clarification: str,
        session_id: str,
        clarification_count: int = 0
    ) -> Dict:
        # 마지막 상태를 복사해서 clarification 주입
        state = self.last_state.copy()  # type: ignore
        state["user_query"] = f"{original_query}, 추가 정보: {clarification}"
        state["clarification_needed"] = False
        state["clarification_question"] = ""
        state["needs_user_input"] = False
        state["clarification_count"] = clarification_count

        logging.debug("▶ handle_clarification_response in state: %r", state)
        try:
            new_state = self.graph.invoke(state)
            self.last_state = new_state
            return {
                "clarification_question": new_state.get("clarification_question", ""),
                "response": new_state.get("final_output", ""),
                "needs_user_input": new_state.get("needs_user_input", False),
                "is_complete": new_state.get("is_complete", True),
                "session_id": session_id,
                "sql_query": new_state.get("sql_query", ""),
                "sql_attempts": new_state.get("sql_attempts", 0),
                "clarification_count": new_state.get("clarification_count", 0),
            }
        except Exception as e:
            logging.error("handle_clarification_response error:\n%s", traceback.format_exc())
            return {
                "response": f"처리 중 오류가 발생했습니다: {e}",
                "needs_user_input": False,
                "is_complete": True,
                "session_id": session_id,
                "sql_query": "",
                "sql_attempts": 0,
                "clarification_count": clarification_count,
            }

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
                response = result['response'] if result['response'] else result.get("clarification_question")
                self.current_session_id = result["session_id"]
                # clarification 질문이거나 최종 답변이거나, response 에 담긴 텍스트를 항상 출력
                print(f"🤖: {response}")

                if result.get("needs_user_input", False):
                    # 실제 모델이 생성한 clarification_question 사용
                    cq = result.get("clarification_question", "").strip()
                    clarification = input(f"🤖: {cq}\n🧑: ").strip()
                    if clarification:
                        clarified = self.framework.handle_clarification_response(
                            user_input,
                            clarification,
                            self.current_session_id,
                            clarification_count=result.get("clarification_count", 0)
                        )
                        self.current_session_id = clarified["session_id"]
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
