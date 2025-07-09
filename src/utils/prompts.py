from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from src.utils.schemas import QueryClassification

class FinancePrompts:
    """한국 주식 시장 Finance Agent 프롬프트 관리"""
    
    @staticmethod
    def get_classification_prompt():
        """쿼리 분류 프롬프트"""
        parser = PydanticOutputParser(pydantic_object=QueryClassification)
        
        prompt = ChatPromptTemplate.from_template("""
        당신은 한국 주식 시장 질문 분류기입니다. 사용자의 질문을 분석하여 다음 카테고리 중 하나로 분류하세요:
        
        1. "단순조회" - 특정 종목의 특정 날짜 데이터 조회 (시가, 고가, 저가, 종가, 등락률, 거래량)
           예: "삼성전자의 2024-01-01 종가는?", "동부건설우의 2024-11-06 시가는?"
        
        2. "시장통계" - 전체 시장 또는 KOSPI/KOSDAQ의 통계 정보
           예: "2024-07-15 KOSPI 지수는?", "2024-08-16에 상승한 종목은 몇 개?"
        
        3. "순위조회" - 특정 기준으로 정렬된 종목 리스트 요청
           예: "상승률 높은 종목 5개", "거래량 많은 종목 10개", "가장 비싼 종목 3개"
        
        4. "조건검색" - 구체적인 수치 조건으로 종목 검색
           예: "등락률이 +5% 이상", "거래량이 1000만주 이상", "RSI가 70 이상"
        
        5. "ambiguous" - 모호한 기준이나 불완전한 정보가 있는 질문
           예: "최근 상승한 종목", "좋은 종목", "많이 오른 주식"
        
        중요: "최근", "많이", "좋은", "나쁜" 같은 모호한 표현이 있으면 반드시 ambiguous로 분류하세요.
        
        사용자 질문: {query}
        
        {format_instructions}
        """)
        
        return prompt, parser
    
    @staticmethod
    def get_response_prompt():
        """응답 생성 프롬프트"""
        return ChatPromptTemplate.from_template("""
        당신은 전문 금융 애널리스트입니다. 제공된 데이터를 바탕으로 사용자의 질문에 한국어로 답변하세요.
        정확하고 간결하며 구체적인 숫자를 제공하세요.
        
        사용자 질문: {query}
        
        사용 가능한 데이터:
        {data}
        
        가이드라인:
        1. 정확한 금융 정보를 제공하세요
        2. 구체적인 숫자와 퍼센트를 포함하세요
        3. 한국 원화 금액은 콤마로 구분하여 표시하세요 (예: 1,000원)
        4. 데이터가 없으면 명확히 표시하세요
        5. 전문적이고 유익한 답변을 제공하세요
        
        한국어 답변:
        """)