clarification_prompt = """
당신은 사용자들의 금융 관련 질문을 돕기 위해 설계된 AI 어시스턴트입니다.
사용자의 질문이 모호하거나 필요한 세부 정보가 부족한 경우, 명확한 답변을 위해 추가 정보를 요청해야 합니다.

1. 사용자의 질문이 모호한지 판단합니다.
2. 질문이 모호하다고 판단되는 경우, clarification_needed를 true로 설정하고 부족한 정보를 요청하는 질문을 생성합니다.
3. 질문이 명확하다고 판단되는 경우, clarification_needed는 false로 설정하고 clarification_question은 빈 문자열("")로 둡니다.

[규칙]
- 날짜 혹은 기간이 명시되어야 하는 경우, "최근" 등의 표현은 모호하므로 명확한 날짜나 기간을 요청해야 합니다. "어제", "한달" 등의 표현은 구체적인 날짜로 변환할 수 있지만, "최근"은 모호합니다.
- 맥락 상 전체 시장에 대한 내용이 아니라 특정 종목이나 시장에 대한 정보가 반드시 필요한 경우, "특정 종목" 또는 "특정 시장"이라고만 언급하는 것은 모호하므로 구체적인 종목명이나 시장명을 요청해야 합니다.

[예시]
사용자 질문: 최근 많이 오른 주식 알려줘.
output: 
```json
{{
    "clarification_needed": true,
    "clarification_question": "최근이라는 표현은 모호합니다. 혹시 어떤 날짜 범위를 말씀하시는 걸까요?"
}}
```
사용자 질문: 고점 대비 많이 떨어진 주식을 알려줘.
output: 
```json
{{
    "clarification_needed": true,
    "clarification_question": "어떤 기간의 고점을 기준으로 말씀하시는 건가요?"
}}
```
사용자 질문: 특정 주식의 최근 동향을 알고 싶어요.
output:
```json
{{
    "clarification_needed": true,
    "clarification_question": "해당 표현은 모호합니다. 종목, 기간, 원하는 정보(예: 주가, 거래량 등)를 구체적으로 말씀해 주세요."
}}
```
사용자 질문: 2024-12-12에 거래량이 전날대비 500% 이상 증가한 종목을 모두 보여줘
output:
```json
{{
    "clarification_needed": false,
    "clarification_question": ""
}}
```
사용자 질문: 2025-02-15 KOSPI 시장에서 가장 비싼 종목은?
output:
```json
{{
    "clarification_needed": false,
    "clarification_question": ""
}}
```
그럼 아래 사용자 질문에 대해 json 형식(```json ```)으로 답변해주세요
==============
사용자 질문: {user_query}
output:
"""

query_parser_prompt = """
금융 관련 질문이 주어졌을 때, 아래 정보를 추출하여 JSON 형식으로 출력해주세요.
1. 날짜: 특정 날짜가 아닌 범위가 주어진 경우, "" 반환
2. 회사명: 해당 회사를 잘 몰라도 질문의 맥락 상 회사명이라고 판단되는 경우 추출 
3. 시장: KOSPI, KOSDAQ, KONEX 중 하나

[예시]
사용자 질문: 2024-10-29에서 KOSPI에서 거래량 많은 종목 10개는?
output:
```json
{{
    "date": "2024-10-29",
    "company_name": "",
    "market": "KOSPI"
}}
```
사용자 질문: 제우스의 2025-07-07 종가는? 
output:
```json
{{
    "date": "2025-07-07",
    "company_name": "제우스",
    "market": ""
}}
```
사용자 질문: 2025-04-24에 볼린저 밴드 상단에 터치한 종목을 알려줘
output:
```json
{{
    "date": "2025-04-24",
    "company_name": "",
    "market": ""
}}
```
```
사용자 질문: 현대사료에서 2024-06-01부터 2025-06-30까지 골든크로스가 몇번 발생했어?
output:
```json
{{
    "date": "",
    "company_name": "현대사료",
    "market": ""
}}
```

이제 다름 사용자 질문에 대해 JSON 형식(```json ```)으로 답변해주세요.
==============
사용자 질문: {user_query}
output:
"""


sql_generation_prompt = """
질문에 대한 힌트를 **반드시** 반영하여 질문을 krx_stockprice 테이블에 대한 MYSQL 쿼리로 변환해주세요.

<주어질 정보>
- 사용자 질문
- 종목 검색 힌트: ticker = '종목 코드' 형태로 주어지며, 종목 검색 힌트가 없으면 빈 문자열("")로 주어집니다. 
- 시장 검색 힌트: ticker LIKE '%.KS' 또는 ticker LIKE '%.KQ' 형태로 주어지며, 시장 검색 힌트가 없으면 빈 문자열("")로 주어집니다.

<SQL 쿼리 작성 규칙>
1. 날짜는 항상 YYYY-MM-DD 포맷. 날짜가 없으면 최신 날짜 {latest_date} 사용
2. 종목 검색 힌트가 주어졌을 경우, **반드시** 이 힌트를 그대로 사용해야 하며, 절대 ticker 검색에 한글 회사명을 사용해서는 안 됩니다. 
3. 가장 비싼: ORDER BY adj_close DESC
4. 상승: price_change_pct > 0
5. 하락: price_change_pct < 0
6. SELECT * 사용하지 말 것. 관련 있는 칼럼만을 선택
7. 모든 컬럼/테이블명은 아래 설명된 이름만 사용
8. market 이 KOSPI인 경우 ticker LIKE '%.KS', KOSDAQ인 경우 ticker LIKE '%.KQ'로 필터링

<krx_stockprice 칼럼>
- date: 거래 일자 (YYYY-MM-DD)
- adj_close: 당일 수정 종가
- close: 당일 종가
- high: 당일 최고가
- low: 당일 최저가
- open: 당일 시가
- volume: 당일 거래량 (주식 수)
- ticker: 종목 코드 (예: 005930.KS, 016790.KQ)
- price_change_pct: 전일 대비 등락률 (%)
- volume_change_pct: 전일 대비 거래량 변화율 (%)
- ma_5, ma_20, ma_60: 5일, 20일, 60일 단순 이동평균선
- ma_vol_20: 20일 거래량 평균
- volume_ratio_20: 현재 거래량 / 20일 평균 거래량
- rsi_14: 14일 기준 RSI
- signal_bollinger_upper: 종가가 상단 밴드 초과시 True
- signal_bollinger_lower: 종가가 하단 밴드 이하시 True
- golden_cross: 골든크로스 발생시 True
- dead_cross: 데드크로스 발생시 True

<예시>
사용자 질문: 2024-10-29에서 KOSPI에서 거래량 많은 종목 10개는? 
종목 검색 힌트: ""
시장 검색 힌트: ticker LIKE '%.KS'
출력:
```sql
SELECT ticker
FROM krx_stockprice, volume -- 거래량도 같이 출력
WHERE date = '2024-10-29' AND ticker LIKE '%.KS'
ORDER BY volume DESC
LIMIT 10
```
사용자 질문: 현대사료의 2025-05-13 시가는?
종목 검색 힌트: ticker = '016790.KS'
시장 검색 힌트: ""
출력:
```sql
SELECT ticker, open 
FROM krx_stockprice
WHERE ticker = '016790.KS' and date = '2025-05-13';
```
사용자 질문: 2025-01-13에 RSI가 70 이상인 과매수 종목을 알려줘
종목 검색 힌트: ""
시장 검색 힌트: ""
출력:
```sql
SELECT ticker, rsi_14 -- RSI 값도 같이 출력
FROM krx_stockprice
WHERE date = '2025-01-13' AND rsi_14 >= 70
ORDER BY rsi_14 DESC;
```

이제 다음 사용자 질문을 SQL 쿼리로 변환해주세요.
================
사용자 질문: {user_query}
종목 검색 힌트: {ticker_hint}
시장 검색 힌트: {market_hint}
출력:
"""

sql_refinement_prompt = """
다음 SQL 쿼리에서 오류가 발생했습니다. 오류를 수정하여 올바른 SQL 쿼리를 작성해주세요. 
SQL 쿼리만을 출력해야합니다. 또한 SQL 쿼리 출력은 ```sql로 시작하고, 마지막에 ```로 끝나야 합니다.

원래 질문: {user_query}
오류 쿼리: {original_query}
오류 메시지: {error}

<SQL 쿼리 작성 규칙>
1. 날짜는 항상 YYYY-MM-DD 포맷. 날짜가 없으면 최신 날짜 {latest_date} 사용
2. 특정 주식 시장에 대한 정보가 없으면 전체 시장에서 검색
3. 특정 종목에 대한 정보를 요청할 경우: ticker = '주어진 티커'를 where 조건으로 사용하여 해당 종목에 대한 정보만 검색 (예: WHERE ticker = '005930.KS')
4. 가장 비싼: ORDER BY adj_close DESC
5. 상승: price_change_pct > 0
6. 하락: price_change_pct < 0
7. SELECT * 사용하지 말 것. 관련 있는 칼럼만을 선택
8. 모든 컬럼/테이블명은 위에 설명된 이름만 사용
9. market 이 KOSPI인 경우 ticker LIKE '%.KS', KOSDAQ인 경우 ticker LIKE '%.KQ'로 필터링

<krx_stockprice 칼럼 설명>
- date: 거래 일자 (YYYY-MM-DD)
- adj_close: 당일 수정 종가
- close: 당일 종가
- high: 당일 최고가
- low: 당일 최저가
- open: 당일 시가
- volume: 당일 거래량 (주식 수)
- ticker: 종목 코드 (예: 005930.KS)
- price_change_pct: 전일 대비 등락률 (%)
- volume_change_pct: 전일 대비 거래량 변화율 (%)
- ma_5, ma_20, ma_60: 5일, 20일, 60일 단순 이동평균선
- ma_vol_20: 20일 거래량 평균
- volume_ratio_20: 현재 거래량 / 20일 평균 거래량
- rsi_14: 14일 기준 RSI
- signal_bollinger_upper: 종가가 상단 밴드 초과시 True
- signal_bollinger_lower: 종가가 하단 밴드 이하시 True
- golden_cross: 골든크로스 발생시 True
- dead_cross: 데드크로스 발생시 True

수정된 SQL:
"""
