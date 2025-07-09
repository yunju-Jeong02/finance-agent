from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import date

class QueryClassification(BaseModel):
    """쿼리 분류 결과"""
    category: Literal["단순조회", "시장통계", "순위조회", "조건검색", "ambiguous"] = Field(
        description="질문 카테고리"
    )
    stock_names: List[str] = Field(
        default_factory=list,
        description="추출된 종목명 리스트"
    )
    market: Literal["KOSPI", "KOSDAQ", "ALL"] = Field(
        default="ALL",
        description="시장 구분"
    )
    date: Optional[str] = Field(
        default=None,
        description="날짜 (YYYY-MM-DD 형식)"
    )
    needs_clarification: bool = Field(
        default=False,
        description="재질문 필요 여부"
    )
    clarification_question: Optional[str] = Field(
        default=None,
        description="재질문 내용"
    )

class StockData(BaseModel):
    """개별 종목 데이터"""
    symbol: str = Field(description="종목 코드")
    korean_name: str = Field(description="한국어 종목명")
    date: str = Field(description="날짜")
    open_price: Optional[float] = Field(default=None, description="시가")
    high_price: Optional[float] = Field(default=None, description="고가")
    low_price: Optional[float] = Field(default=None, description="저가")
    close_price: Optional[float] = Field(default=None, description="종가")
    volume: Optional[int] = Field(default=None, description="거래량")
    change_rate: Optional[float] = Field(default=None, description="등락률")
    market: str = Field(default="KOSPI", description="시장 구분")

class MarketStatistics(BaseModel):
    """시장 통계 데이터"""
    date: str = Field(description="날짜")
    kospi_index: Optional[float] = Field(default=None, description="KOSPI 지수")
    kosdaq_index: Optional[float] = Field(default=None, description="KOSDAQ 지수")
    total_trading_value: Optional[int] = Field(default=None, description="전체 거래대금")
    rising_stocks: Optional[int] = Field(default=None, description="상승 종목 수")
    falling_stocks: Optional[int] = Field(default=None, description="하락 종목 수")
    kospi_rising_stocks: Optional[int] = Field(default=None, description="KOSPI 상승 종목 수")
    kosdaq_rising_stocks: Optional[int] = Field(default=None, description="KOSDAQ 상승 종목 수")
    kospi_market_count: Optional[int] = Field(default=None, description="KOSPI 거래 종목 수")
    kosdaq_market_count: Optional[int] = Field(default=None, description="KOSDAQ 거래 종목 수")

class SearchConditions(BaseModel):
    """조건검색 파라미터"""
    min_change_rate: Optional[float] = Field(default=None, description="최소 등락률")
    max_change_rate: Optional[float] = Field(default=None, description="최대 등락률")
    min_volume: Optional[int] = Field(default=None, description="최소 거래량")
    max_volume: Optional[int] = Field(default=None, description="최대 거래량")
    min_price: Optional[float] = Field(default=None, description="최소 가격")
    max_price: Optional[float] = Field(default=None, description="최대 가격")
    min_rsi: Optional[float] = Field(default=None, description="최소 RSI")
    max_rsi: Optional[float] = Field(default=None, description="최대 RSI")
    market: str = Field(default="ALL", description="시장 구분")

class RankingCriteria(BaseModel):
    """순위 조회 기준"""
    type: Literal["상승률", "하락률", "거래량", "가격"] = Field(description="순위 기준")
    order: Literal["ASC", "DESC"] = Field(description="정렬 순서")
    limit: int = Field(default=10, description="조회 개수")
    market: str = Field(default="ALL", description="시장 구분")

class TechnicalSignal(BaseModel):
    """기술적 신호"""
    symbol: str = Field(description="종목 코드")
    korean_name: str = Field(description="한국어 종목명")
    close_price: float = Field(description="종가")
    rsi_14: Optional[float] = Field(default=None, description="RSI(14)")
    ma_20: Optional[float] = Field(default=None, description="20일 이동평균")
    ma_60: Optional[float] = Field(default=None, description="60일 이동평균")
    volume_ratio: Optional[float] = Field(default=None, description="거래량 비율")
    
class AgentResponse(BaseModel):
    """에이전트 응답"""
    response: str = Field(description="응답 내용")
    needs_user_input: bool = Field(default=False, description="사용자 입력 필요 여부")
    data_source: Optional[str] = Field(default=None, description="데이터 소스")
    query_type: Optional[str] = Field(default=None, description="쿼리 타입")