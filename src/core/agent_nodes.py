from typing import Dict, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from src.data.data_fetcher import YahooFinanceDataFetcher
from src.utils.prompts import FinancePrompts
from src.utils.schemas import QueryClassification
from src.utils.parameter_extractor import LLMParameterExtractor
from src.data.technical_analyzer import TechnicalSignalDetector
from config.config import Config
import json
from datetime import datetime, timedelta

class FinanceAgentNodes:
    def __init__(self):
        self.config = Config()
        self.llm = ChatOpenAI(temperature=self.config.TEMPERATURE, model="gpt-4")
        self.data_fetcher = YahooFinanceDataFetcher()
        self.prompts = FinancePrompts()
        self.signal_detector = TechnicalSignalDetector()
        self.param_extractor = LLMParameterExtractor()
        
    
    
    def analyze_query_with_context(self, state: Dict) -> Dict:
        """쿼리와 컨텍스트를 분석하여 부족한 정보 식별"""
        user_query = state.get("user_query", "")
        context = state.get("session_context", {})
        
        prompt = ChatPromptTemplate.from_template("""
        사용자의 주식 질문과 기존 컨텍스트를 분석하여 질문을 분류하고 정보를 추출하세요.

        다음 중 하나의 쿼리 타입으로 분류하세요:
        - 단순조회: 특정 종목의 특정 날짜 데이터 조회
        - 순위조회: 특정 기준으로 정렬된 종목 리스트
        - 조건검색: 구체적인 수치 조건으로 종목 검색
        - 시장통계: 전체 시장 또는 KOSPI/KOSDAQ 통계

        반드시 다음 JSON 형식으로만 응답하세요:

        {{
            "query_type": "단순조회",
            "is_complete": true,
            "extracted_info": {{
                "종목명": "삼성전자",
                "날짜": "2024-01-01",
                "정보유형": "종가",
                "기준": null,
                "개수": null,
                "조건": null
            }},
            "missing_info": [],
            "confidence": 0.9
        }}

        날짜 변환 규칙을 적용하세요:
        - "어제" → {yesterday}
        - "오늘" → {today}
        - "지난주" → 지난주 금요일
                                                  
        ==========================                               
        사용자 질문: {query}
        기존 컨텍스트: {context}                                   
        """)
        
        from datetime import datetime, timedelta
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        try:
            response = self.llm.invoke(prompt.format(
                query=user_query,
                context=json.dumps(context, ensure_ascii=False, indent=2),
                today=today,
                yesterday=yesterday
            ))
            
            # JSON 추출 시도
            print(f"LLM 응답: {response.content[:300]}...")  # 디버깅용 출력
            content = response.content.strip()
            
            # JSON 블록 찾기
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                json_str = content[start:end].strip()
            elif content.startswith("{") and content.endswith("}"):
                json_str = content
            else:
                # JSON 부분 찾기
                start = content.find("{")
                end = content.rfind("}") + 1
                json_str = content[start:end] if start != -1 and end != 0 else content
            
            analysis = json.loads(json_str)
            
            # 날짜 정규화
            if analysis.get("extracted_info", {}).get("날짜"):
                analysis["extracted_info"]["날짜"] = self._normalize_date(analysis["extracted_info"]["날짜"])
            
            state["query_analysis"] = analysis
            return state
            
        except Exception as e:
            print(f"쿼리 분석 실패: {e}")
            print(f"LLM 응답: {response.content[:200]}...")
            
            # 기본 분석 로직 사용
            analysis = self._fallback_analysis(user_query, context)
            state["query_analysis"] = analysis
            return state
    
    def handle_incomplete_query(self, state: Dict) -> Dict:
        """불완전한 쿼리 처리 - 되묻기 로직"""
        analysis = state.get("query_analysis", {})
        context = state.get("session_context", {})
        interaction_count = state.get("interaction_count", 0)
        
        # 첫 번째 질문: 부족한 정보 한 번에 물어보기
        if interaction_count == 1:
            return self._ask_for_missing_info_batch(state, analysis, context)
        
        # 두 번째 이후: 후보군 제시
        else:
            return self._provide_candidates(state, analysis, context)
    
    def _ask_for_missing_info_batch(self, state: Dict, analysis: Dict, context: Dict) -> Dict:
        """부족한 정보를 한 번에 질문"""
        missing_info = analysis.get("missing_info", [])
        query_type = analysis.get("query_type", "unknown")
        
        # 질문 생성
        question = self._generate_batch_question(missing_info, query_type, context)
        
        state["response"] = question
        state["needs_user_input"] = True
        state["interaction_type"] = "batch_question"
        
        return state
    
    def _provide_candidates(self, state: Dict, analysis: Dict, context: Dict) -> Dict:
        """후보군 제시"""
        missing_info = analysis.get("missing_info", [])
        query_type = analysis.get("query_type", "unknown")
        
        # 각 부족한 정보에 대한 후보군 생성
        candidates = self._generate_candidates(missing_info, query_type, context)
        
        # 후보군 기반 질문 생성
        question = self._generate_candidate_question(candidates, context)
        
        state["response"] = question
        state["needs_user_input"] = True
        state["candidates"] = candidates
        state["interaction_type"] = "candidate_selection"
        
        return state
    
    def _generate_batch_question(self, missing_info: List[str], query_type: str, context: Dict) -> str:
        """일괄 질문 생성"""
        if query_type == "단순조회":
            parts = []
            if "종목명" in missing_info:
                parts.append("어떤 종목을")
            if "날짜" in missing_info:
                parts.append("언제")
            if "정보유형" in missing_info:
                parts.append("어떤 정보를")
            
            return f"{' '.join(parts)} 조회하시겠습니까?"
            
        elif query_type == "순위조회":
            parts = []
            if "날짜" in missing_info:
                parts.append("언제 기준으로")
            if "기준" in missing_info:
                parts.append("어떤 기준으로")
            if "개수" in missing_info:
                parts.append("몇 개를")
            
            return f"{' '.join(parts)} 조회하시겠습니까?"
        
        # 기본 질문
        return f"다음 정보를 알려주세요: {', '.join(missing_info)}"
    
    def _generate_candidates(self, missing_info: List[str], query_type: str, context: Dict) -> Dict:
        """후보군 생성"""
        candidates = {}
        
        for info in missing_info:
            if info == "날짜":
                candidates["날짜"] = [
                    {"label": "오늘", "value": datetime.now().strftime("%Y-%m-%d")},
                    {"label": "어제", "value": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")},
                    {"label": "지난주", "value": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")},
                    {"label": "직접 입력", "value": "custom"}
                ]
            
            elif info == "개수":
                candidates["개수"] = [
                    {"label": "5개", "value": "5"},
                    {"label": "10개", "value": "10"},
                    {"label": "20개", "value": "20"},
                    {"label": "직접 입력", "value": "custom"}
                ]
            
            elif info == "기준":
                candidates["기준"] = [
                    {"label": "상승률", "value": "상승률"},
                    {"label": "하락률", "value": "하락률"},
                    {"label": "거래량", "value": "거래량"},
                    {"label": "가격", "value": "가격"}
                ]
            
            elif info == "정보유형":
                candidates["정보유형"] = [
                    {"label": "종가", "value": "종가"},
                    {"label": "시가", "value": "시가"},
                    {"label": "거래량", "value": "거래량"},
                    {"label": "등락률", "value": "등락률"}
                ]
        
        return candidates
    
    def _generate_candidate_question(self, candidates: Dict, context: Dict) -> str:
        """후보군 기반 질문 생성"""
        if len(candidates) == 1:
            # 단일 후보군
            info_type = list(candidates.keys())[0]
            options = candidates[info_type]
            
            question = f"{info_type}을 선택해주세요:\n"
            for i, option in enumerate(options, 1):
                question += f"{i}. {option['label']}\n"
            
            return question
        
        else:
            # 복수 후보군
            question = "다음 중에서 선택해주세요:\n\n"
            
            for info_type, options in candidates.items():
                question += f"**{info_type}:**\n"
                for i, option in enumerate(options, 1):
                    question += f"  {i}. {option['label']}\n"
                question += "\n"
            
            question += "선택하시려면 '날짜 1, 개수 2' 형식으로 답해주세요."
            
            return question
    
    def _normalize_date(self, date_str: str) -> str:
        """날짜 정규화"""
        today = datetime.now()
        
        if "어제" in date_str.lower():
            return (today - timedelta(days=1)).strftime("%Y-%m-%d")
        elif "오늘" in date_str.lower():
            return today.strftime("%Y-%m-%d")
        elif "지난주" in date_str.lower():
            days_since_friday = (today.weekday() - 4) % 7
            last_friday = today - timedelta(days=days_since_friday + 7)
            return last_friday.strftime("%Y-%m-%d")
        else:
            return date_str
    
    def update_context_from_response(self, state: Dict) -> Dict:
        """사용자 응답으로부터 컨텍스트 업데이트"""
        user_response = state.get("user_query", "")
        candidates = state.get("candidates", {})
        context = state.get("session_context", {})
        
        # 후보군 선택 파싱
        if candidates:
            updated_context = self._parse_candidate_selection(user_response, candidates, context)
            state["session_context"] = updated_context
        
        return state
    
    def _parse_candidate_selection(self, user_response: str, candidates: Dict, context: Dict) -> Dict:
        """후보군 선택 파싱"""
        import re
        
        updated_context = context.copy()
        
        # 단순 숫자 응답 처리 (단일 후보군)
        if len(candidates) == 1:
            info_type = list(candidates.keys())[0]
            options = candidates[info_type]
            
            match = re.search(r'(\d+)', user_response)
            if match:
                index = int(match.group(1)) - 1
                if 0 <= index < len(options):
                    updated_context[info_type] = options[index]["value"]
        
        # 복수 후보군 처리
        else:
            for info_type in candidates.keys():
                pattern = f"{info_type}\s*(\d+)"
                match = re.search(pattern, user_response)
                if match:
                    index = int(match.group(1)) - 1
                    options = candidates[info_type]
                    if 0 <= index < len(options):
                        updated_context[info_type] = options[index]["value"]
        
        return updated_context
    
    def fetch_simple_data(self, state: Dict) -> Dict:
        """단순조회: 특정 종목의 특정 날짜 데이터 조회 - LLM 기반 정보 유형 추출"""
        # 새로운 분석 결과에서 정보 가져오기
        analysis = state.get("query_analysis", {})
        extracted_info = analysis.get("extracted_info", {})
        
        stock_name = extracted_info.get("종목명")
        date = extracted_info.get("날짜")
        user_query = state.get("user_query", "")
        
        # 세션 컨텍스트에서 추가 정보 가져오기
        session_context = state.get("session_context", {})
        if not stock_name and session_context.get("종목명"):
            stock_name = session_context["종목명"]
        if not date and session_context.get("날짜"):
            date = session_context["날짜"]
        
        if not stock_name or not date:
            state["response"] = "종목명과 날짜를 모두 제공해주세요."
            state["needs_user_input"] = False
            return state
        
        # LLM으로 정보 유형 추출
        info_type = self.param_extractor.extract_stock_info_type(user_query)
        
        # 실제 데이터 조회
        data = self.data_fetcher.get_stock_data(stock_name, date)
        
        if "error" in data:
            state["response"] = data["error"]
        else:
            response = self._format_simple_response_enhanced(user_query, data, info_type)
            state["response"] = response
        
        state["needs_user_input"] = False
        return state
    
    def fetch_market_statistics(self, state: Dict) -> Dict:
        """시장통계: 전체 시장 또는 KOSPI/KOSDAQ의 통계 정보"""
        # 새로운 분석 결과에서 정보 가져오기
        analysis = state.get("query_analysis", {})
        extracted_info = analysis.get("extracted_info", {})
        
        date = extracted_info.get("날짜")
        
        # 세션 컨텍스트에서 추가 정보 가져오기
        session_context = state.get("session_context", {})
        if not date and session_context.get("날짜"):
            date = session_context["날짜"]
        
        if not date:
            state["response"] = "날짜를 제공해주세요."
            state["needs_user_input"] = False
            return state
        
        # 실제 시장 통계 조회
        stats = self.data_fetcher.get_market_stats(date)
        
        if "error" in stats:
            state["response"] = stats["error"]
        else:
            user_query = state.get("user_query", "")
            response = self._format_market_stats_response(user_query, stats, date)
            state["response"] = response
        
        state["needs_user_input"] = False
        return state
    
    def fetch_rankings(self, state: Dict) -> Dict:
        """순위조회: 특정 기준으로 정렬된 종목 리스트 - LLM 기반 파라미터 추출"""
        # 새로운 분석 결과에서 정보 가져오기
        analysis = state.get("query_analysis", {})
        extracted_info = analysis.get("extracted_info", {})
        
        date = extracted_info.get("날짜")
        user_query = state.get("user_query", "")
        
        # 세션 컨텍스트에서 정보 가져오기
        session_context = state.get("session_context", {})
        if not date and session_context.get("날짜"):
            date = session_context["날짜"]
        
        if not date:
            state["response"] = "날짜를 제공해주세요."
            state["needs_user_input"] = False
            return state
        
        # LLM으로 순위 조회 파라미터 추출
        params = self.param_extractor.extract_ranking_parameters(user_query)
        
        # 세션 컨텍스트에서 추가 파라미터 가져오기
        if session_context.get("기준"):
            params["criteria"] = session_context["기준"]
        if session_context.get("개수"):
            params["limit"] = int(session_context["개수"])
        
        # 실제 순위 조회
        rankings = self.data_fetcher.get_rankings(date, params["criteria"], market, params["limit"])
        
        if "error" in rankings:
            state["response"] = rankings["error"]
        else:
            response = self._format_rankings_response_enhanced(user_query, rankings, params, date)
            state["response"] = response
        
        state["needs_user_input"] = False
        return state
    
    def perform_conditional_search(self, state: Dict) -> Dict:
        """조건검색: 구체적인 수치 조건으로 종목 검색 - LLM 기반 파라미터 추출"""
        # 새로운 분석 결과에서 정보 가져오기
        analysis = state.get("query_analysis", {})
        extracted_info = analysis.get("extracted_info", {})
        
        date = extracted_info.get("날짜")
        user_query = state.get("user_query", "")
        
        # 세션 컨텍스트에서 정보 가져오기
        session_context = state.get("session_context", {})
        if not date and session_context.get("날짜"):
            date = session_context["날짜"]
        
        if not date:
            state["response"] = "날짜를 제공해주세요."
            state["needs_user_input"] = False
            return state
        
        # LLM으로 검색 조건 추출
        conditions = self.param_extractor.extract_search_parameters(user_query)
        
        # 세션 컨텍스트에서 추가 조건 가져오기
        if session_context.get("조건"):
            # 세션 컨텍스트의 조건을 파싱하여 병합
            context_conditions = self._parse_condition(session_context["조건"])
            conditions.update(context_conditions)
        
        if not conditions:
            state["response"] = "검색 조건을 명확히 해주세요."
            state["needs_user_input"] = True
            return state
        
        # 실제 조건 검색
        results = self.data_fetcher.search_by_conditions(date, conditions)
        
        if "error" in results:
            state["response"] = results["error"]
        else:
            response = self._format_search_results_response_enhanced(user_query, results, conditions, date)
            state["response"] = response
        
        state["needs_user_input"] = False
        return state
    
    def generate_response(self, state: Dict) -> Dict:
        """Generate final response using LLM"""
        user_query = state.get("user_query", "")
        
        # 사용 가능한 모든 데이터 수집
        all_data = {
            "query_classification": state.get("query_classification", {}),
            "price_data": state.get("price_data", {}),
            "market_statistics": state.get("market_statistics", {}),
            "market_rankings": state.get("market_rankings", {}),
            "search_results": state.get("search_results", {}),
            "technical_signals": state.get("technical_signals", {})
        }
        
        prompt = self.prompts.get_response_prompt()
        response = self.llm.invoke(prompt.format(
            query=user_query,
            data=str(all_data)
        ))
        
        state["response"] = response.content
        state["needs_user_input"] = False
        
        return state
    
    def route_query(self, state: Dict) -> str:
        """Route the query to appropriate next node"""
        # 세션 컨텍스트 기반 라우팅 확인
        if state.get("session_context"):
            analysis = state.get("query_analysis", {})
            if analysis and not analysis.get("is_complete", True):
                return "handle_incomplete_query"
            elif analysis and analysis.get("is_complete", False):
                return self._route_complete_query(analysis)
        
        # 기존 분류 기반 라우팅
        classification = state.get("query_classification", {})
        
        if classification.get("needs_clarification", False):
            return "ask_clarification"
        
        category = classification.get("category", "")
        
        if category == "단순조회":
            return "fetch_simple_data"
        elif category == "시장통계":
            return "fetch_market_statistics"
        elif category == "순위조회":
            return "fetch_rankings"
        elif category == "조건검색":
            return "perform_conditional_search"
        else:
            return "generate_response"
    
    def _route_complete_query(self, analysis: Dict) -> str:
        """완성된 쿼리 라우팅"""
        query_type = analysis.get("query_type", "")
        
        if query_type == "단순조회":
            return "fetch_simple_data"
        elif query_type == "시장통계":
            return "fetch_market_statistics"
        elif query_type == "순위조회":
            return "fetch_rankings"
        elif query_type == "조건검색":
            return "perform_conditional_search"
        else:
            return "generate_response"
    
    
    def _format_simple_response_enhanced(self, query: str, data: Dict, info_type: str) -> str:
        """개선된 단순조회 응답 포맷팅 (LLM 기반)"""
        stock_name = data.get('stock_name', '')
        date = data.get('date', '')
        
        if info_type == "open":
            return f"{stock_name}의 {date} 시가는 {data['open']:,.0f}원입니다."
        elif info_type == "high":
            return f"{stock_name}의 {date} 고가는 {data['high']:,.0f}원입니다."
        elif info_type == "low":
            return f"{stock_name}의 {date} 저가는 {data['low']:,.0f}원입니다."
        elif info_type == "close":
            return f"{stock_name}의 {date} 종가는 {data['close']:,.0f}원입니다."
        elif info_type == "volume":
            return f"{stock_name}의 {date} 거래량은 {data['volume']:,}주입니다."
        elif info_type == "change_rate":
            return f"{stock_name}의 {date} 등락률은 {data['change_rate']:+.2f}%입니다."
        else:
            return f"{stock_name}의 {date} 종가는 {data['close']:,.0f}원입니다."
    
    def _format_market_stats_response(self, query: str, stats: Dict, date: str) -> str:
        """시장통계 응답 포맷팅"""
        if "KOSPI 지수" in query:
            return f"{date} KOSPI 지수는 {stats['kospi_index']:.2f}입니다."
        elif "KOSDAQ 지수" in query:
            return f"{date} KOSDAQ 지수는 {stats['kosdaq_index']:.2f}입니다."
        elif "거래대금" in query:
            return f"{date} 전체 시장 거래대금은 {stats['total_trading_value']:,}원입니다."
        elif "상승한 종목" in query:
            return f"{date}에 상승한 종목은 {stats['rising_stocks']}개입니다."
        elif "하락한 종목" in query:
            return f"{date}에 하락한 종목은 {stats['falling_stocks']}개입니다."
        else:
            return f"{date} 시장 통계를 조회했습니다."
    
    
    def _format_rankings_response_enhanced(self, query: str, rankings: Dict, params: Dict, date: str) -> str:
        """개선된 순위조회 응답 포맷팅 (LLM 기반)"""
        stocks = rankings.get("rankings", [])
        if not stocks:
            return f"{date}에 조건에 맞는 종목이 없습니다."
        
        criteria = params.get("criteria", "상승률")
        limit = params.get("limit", 10)
        
        stock_names = [stock['korean_name'] for stock in stocks[:limit]]
        return f"{date}에서 {criteria} 기준 상위 {limit}개 종목: {', '.join(stock_names)}"
    
    
    def _format_search_results_response_enhanced(self, query: str, results: Dict, conditions: Dict, date: str) -> str:
        """개선된 조건검색 응답 포맷팅 (LLM 기반)"""
        stocks = results.get("results", [])
        if not stocks:
            return f"{date}에 조건에 맞는 종목이 없습니다."
        
        # 조건 설명 생성
        condition_desc = []
        if conditions.get("min_change_rate"):
            condition_desc.append(f"등락률 {conditions['min_change_rate']}% 이상")
        if conditions.get("max_change_rate"):
            condition_desc.append(f"등락률 {conditions['max_change_rate']}% 이하")
        if conditions.get("min_volume"):
            condition_desc.append(f"거래량 {conditions['min_volume']:,}주 이상")
        
        condition_text = ", ".join(condition_desc) if condition_desc else "지정된 조건"
        
        stock_names = [stock['korean_name'] for stock in stocks[:10]]
        return f"{date}에 {condition_text}에 맞는 종목 ({len(stocks)}개): {', '.join(stock_names)}"
    
    
    def _parse_condition(self, condition_text: str) -> Dict:
        """조건 파싱"""
        import re
        
        conditions = {}
        
        # 등락률 조건
        if "등락률" in condition_text:
            if "이상" in condition_text:
                match = re.search(r'([+-]?\d+(?:\.\d+)?)\s*%\s*이상', condition_text)
                if match:
                    conditions["min_change_rate"] = float(match.group(1))
            if "이하" in condition_text:
                match = re.search(r'([+-]?\d+(?:\.\d+)?)\s*%\s*이하', condition_text)
                if match:
                    conditions["max_change_rate"] = float(match.group(1))
        
        # 거래량 조건
        if "거래량" in condition_text:
            if "이상" in condition_text:
                match = re.search(r'거래량이?\s*(\d+)만주\s*이상', condition_text)
                if match:
                    conditions["min_volume"] = int(match.group(1)) * 10000
            if "이하" in condition_text:
                match = re.search(r'거래량이?\s*(\d+)만주\s*이하', condition_text)
                if match:
                    conditions["max_volume"] = int(match.group(1)) * 10000
        
        return conditions
    
    def check_query_completeness(self, state: Dict) -> str:
        """쿼리 완성도 확인 후 라우팅"""
        analysis = state.get("query_analysis", {})
        
        if analysis.get("is_complete", False):
            # 완성된 쿼리는 바로 해당 노드로 라우팅
            query_type = analysis.get("query_type", "")
            if query_type == "단순조회":
                return "fetch_simple_data"
            elif query_type == "시장통계":
                return "fetch_market_statistics"
            elif query_type == "순위조회":
                return "fetch_rankings"
            elif query_type == "조건검색":
                return "perform_conditional_search"
            else:
                return "generate_response"
        else:
            return "handle_incomplete_query"