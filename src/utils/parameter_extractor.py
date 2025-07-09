"""
LLM 기반 파라미터 추출기
정규표현식 대신 LLM을 사용해서 자연어에서 파라미터 추출
"""
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from config.config import Config

class RankingParameters(BaseModel):
    """순위 조회 파라미터"""
    criteria: str = Field(description="정렬 기준 (상승률, 하락률, 거래량, 가격, 시가총액)")
    limit: int = Field(description="조회할 종목 수", default=10)
    order: str = Field(description="정렬 순서 (desc, asc)", default="desc")

class SearchParameters(BaseModel):
    """조건 검색 파라미터"""
    min_change_rate: Optional[float] = Field(description="최소 등락률 (%)", default=None)
    max_change_rate: Optional[float] = Field(description="최대 등락률 (%)", default=None)
    min_volume: Optional[int] = Field(description="최소 거래량", default=None)
    max_volume: Optional[int] = Field(description="최대 거래량", default=None)
    min_price: Optional[float] = Field(description="최소 가격", default=None)
    max_price: Optional[float] = Field(description="최대 가격", default=None)
    min_market_cap: Optional[float] = Field(description="최소 시가총액", default=None)
    max_market_cap: Optional[float] = Field(description="최대 시가총액", default=None)

class LLMParameterExtractor:
    """LLM 기반 파라미터 추출기"""
    
    def __init__(self):
        self.config = Config()
        self.llm = ChatOpenAI(
            temperature=0.1,
            model="gpt-4",
            api_key=self.config.OPENAI_API_KEY
        )
    
    def extract_ranking_parameters(self, query: str) -> Dict[str, Any]:
        """순위 조회 파라미터 추출"""
        parser = PydanticOutputParser(pydantic_object=RankingParameters)
        
        prompt = ChatPromptTemplate.from_template("""
        다음 사용자 질문에서 주식 순위 조회에 필요한 파라미터를 추출하세요.

        사용자 질문: {query}

        가능한 정렬 기준:
        - 상승률: 등락률이 높은 순서
        - 하락률: 등락률이 낮은 순서 (음수)
        - 거래량: 거래량이 많은 순서
        - 가격: 주가가 높은 순서
        - 시가총액: 시가총액이 큰 순서

        예시:
        - "상승률 높은 종목 5개" → criteria: "상승률", limit: 5
        - "제일 잘나가는 주식 10개" → criteria: "상승률", limit: 10
        - "많이 떨어진 종목 3개" → criteria: "하락률", limit: 3
        - "거래량 많은 종목" → criteria: "거래량", limit: 10
        - "비싼 주식 순서대로" → criteria: "가격", limit: 10

        {format_instructions}
        """)
        
        try:
            response = self.llm.invoke(prompt.format(
                query=query,
                format_instructions=parser.get_format_instructions()
            ))
            
            return parser.parse(response.content).dict()
            
        except Exception as e:
            print(f"순위 파라미터 추출 실패: {e}")
            # 기본값 반환
            return {
                "criteria": "상승률",
                "limit": 10,
                "order": "desc"
            }
    
    def extract_search_parameters(self, query: str) -> Dict[str, Any]:
        """조건 검색 파라미터 추출"""
        parser = PydanticOutputParser(pydantic_object=SearchParameters)
        
        prompt = ChatPromptTemplate.from_template("""
        다음 사용자 질문에서 주식 조건 검색에 필요한 파라미터를 추출하세요.

        사용자 질문: {query}

        추출할 조건들:
        - 등락률: "5% 이상 상승", "3% 이하 하락" 등
        - 거래량: "1000만주 이상", "백만주 이하" 등
        - 가격: "1만원 이상", "5만원 이하" 등
        - 시가총액: "1조원 이상" 등

        예시:
        - "등락률이 5% 이상인 종목" → min_change_rate: 5.0
        - "3% 이하로 떨어진 종목" → max_change_rate: -3.0
        - "거래량이 1000만주 이상" → min_volume: 10000000
        - "가격이 1만원에서 5만원 사이" → min_price: 10000, max_price: 50000

        숫자 변환 규칙:
        - 만: 10,000배
        - 억: 100,000,000배
        - 조: 1,000,000,000,000배

        {format_instructions}
        """)
        
        try:
            response = self.llm.invoke(prompt.format(
                query=query,
                format_instructions=parser.get_format_instructions()
            ))
            
            result = parser.parse(response.content).dict()
            
            # None 값 제거
            return {k: v for k, v in result.items() if v is not None}
            
        except Exception as e:
            print(f"검색 파라미터 추출 실패: {e}")
            # 빈 조건 반환
            return {}
    
    def extract_stock_info_type(self, query: str) -> str:
        """주식 정보 유형 추출"""
        prompt = ChatPromptTemplate.from_template("""
        다음 질문에서 사용자가 원하는 주식 정보 유형을 추출하세요.

        사용자 질문: {query}

        가능한 정보 유형:
        - open: 시가
        - high: 고가, 최고가
        - low: 저가, 최저가
        - close: 종가, 마감가
        - volume: 거래량
        - change_rate: 등락률, 수익률, 변동률

        예시:
        - "삼성전자 종가는?" → close
        - "시가가 얼마야?" → open
        - "거래량 알려줘" → volume
        - "등락률은?" → change_rate

        단 하나의 단어로만 답하세요.
        """)
        
        try:
            response = self.llm.invoke(prompt.format(query=query))
            result = response.content.strip().lower()
            
            # 유효한 값인지 확인
            valid_types = ["open", "high", "low", "close", "volume", "change_rate"]
            if result in valid_types:
                return result
            else:
                return "close"  # 기본값
                
        except Exception as e:
            print(f"주식 정보 유형 추출 실패: {e}")
            return "close"  # 기본값