clarification_prompt = """
당신은 사용자들의 금융 관련 질문을 돕기 위해 설계된 AI 어시스턴트입니다.
사용자의 질문이 모호하거나 필요한 세부 정보가 부족한 경우, 명확한 답변을 위해 추가 정보를 요청해야 합니다.

[규칙]
1. 사용자의 질문이 모호한지 판단합니다.
2. 질문이 모호하다고 판단되는 경우, clarification_needed를 true로 설정하고 부족한 정보를 요청하는 질문을 생성합니다.
3. 질문이 명확하다고 판단되는 경우, clarification_needed는 false로 설정하고 clarification_question은 빈 문자열("")로 둡니다.

[예시]
사용자 질문: 최근 많이 오른 주식 알려줘.
output: 
```json
{{
    "clarification_needed": true,
    "clarification_question": '최근'이라는 표현은 모호합니다. 혹시 어떤 날짜 범위를 말씀하시는 걸까요?
}}
```
사용자 질문: 고점 대비 많이 떨어진 주식을 알려줘.
output: 
```json
{{
    "clarification_needed": true,
    "clarification_question": '고점 대비'라는 표현은 모호합니다. 어떤 기간의 고점을 기준으로 말씀하시는 건가요?
}}
```
사용자 질문: 특정 주식의 최근 동향을 알고 싶어요.
output:
```json
{{
    "clarification_needed": true,
    "clarification_question": '해당 표현은 모호합니다. 종목, 기간, 원하는 정보(예: 주가, 거래량 등)를 구체적으로 말씀해 주세요.
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
1. 날짜
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

이제 다름 사용자 질문에 대해 JSON 형식(```json ```)으로 답변해주세요.
==============
사용자 질문: {user_query}
output:
"""


sql_generation_prompt = """
질문에 대한 힌트를 참고하여 질문을 krx_stockprice 테이블에 대한 MYSQL 쿼리로 변환해주세요.

<krx_stockprice 칼럼>
- date: 거래 일자 (YYYY-MM-DD)
- adj_close: 수정 종가
- close: 종가
- high: 당일 최고가
- low: 당일 최저가
- open: 당일 시가
- volume: 당일 거래량 (주식 수)
- ticker: 종목 코드 (예: 005930.KS)
- company_name: 종목의 한글회사명 (예: 삼성전자)
- price_change_pct: 전일 대비 등락률 (%)
- volume_change_pct: 전일 대비 거래량 변화율 (%)
- ma_5, ma_20, ma_60: 5일, 20일, 60일 단순 이동평균선
- ma_vol_20: 20일 거래량 평균
- volume_ratio_20: 현재 거래량 / 20일 평균 거래량
- rsi_14: 14일 기준 RSI
- bollinger_mid: 20일 이동평균선
- bollinger_upper: 볼린저 상단 밴드
- bollinger_lower: 볼린저 하단 밴드
- signal_bollinger_upper: 종가가 상단 밴드 초과시 True
- signal_bollinger_lower: 종가가 하단 밴드 이하시 True
- ma_diff: ma_5 - ma_20
- prev_diff: 전날의 ma_diff
- golden_cross: 골든크로스 발생시 True
- dead_cross: 데드크로스 발생시 True

<SQL 쿼리 작성 규칙>
1. 날짜는 항상 YYYY-MM-DD 포맷. 날짜가 없으면 최신 날짜 {latest_date} 사용
2. 특정 주식 시장에 대한 정보가 없으면 전체 시장에서 검색
3. 힌트로 티커가 주어진 경우: ticker = '주어진 티커'를 조건으로 사용하여 검색
4. 가장 비싼: ORDER BY adj_close DESC
5. 상승: price_change_pct > 0
6. 하락: price_change_pct < 0
7. SELECT 문만 사용
8. 모든 컬럼/테이블명은 위에 설명된 이름만 사용
9. 종목 나열을 요청 받은 경우: ticker가 아닌 company_name 컬럼을 사용하여 나열. SELECT company_name, ..

<예시1>
사용자 질문: 2024-10-29에서 KOSPI에서 거래량 많은 종목 10개는? 
힌트: company_name: "", ticker: "", market: "KOSPI"
출력:
```sql
SELECT company_name
FROM krx_stockprice
WHERE date = '2024-10-29' AND ticker LIKE '%.KS'
ORDER BY volume DESC
LIMIT 10
```
<예시2>
사용자 질문: 현대사료의 2025-05-13 시가는?
힌트: company_name: "현대사료", ticker: "016790.KS", market: "")
출력:
```sql
SELECT company_name, open
FROM krx_stockprice
WHERE ticker = '016790.KS' and date = '2025-05-13';
```

이제 다음 사용자 질문을 SQL 쿼리로 변환해주세요.
================
사용자 질문: {query}
힌트: company_name: {company_name}, ticker: {ticker}, market: {market}
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
2. KOSPI: ticker LIKE '%.KS'
3. KOSDAQ: ticker LIKE '%.KQ'
4. 가장 비싼: ORDER BY adj_close DESC
5. 상승: price_change_pct > 0
6. 하락: price_change_pct < 0
7. SELECT 문만 사용
8. SQL query는 ```sql로 시작하고, 마지막에 ```로 끝나야 합니다.
9. 모든 컬럼/테이블명은 위에 설명된 이름만 사용
10. 종목 나열은 ticker가 아닌 company_name 컬럼으로만: SELECT company_name, ..

<krx_stockprice 칼럼 설명>
- date: 거래 일자 (YYYY-MM-DD)
- adj_close: 수정 종가
- close: 종가
- high: 당일 최고가
- low: 당일 최저가
- open: 당일 시가
- volume: 당일 거래량 (주식 수)
- ticker: 종목 코드 (예: 005930.KS)
- company_name: 종목의 회사명
- price_change_pct: 전일 대비 등락률 (%)
- volume_change_pct: 전일 대비 거래량 변화율 (%)
- ma_5, ma_20, ma_60: 5일, 20일, 60일 단순 이동평균선
- ma_vol_20: 20일 거래량 평균
- volume_ratio_20: 현재 거래량 / 20일 평균 거래량
- rsi_14: 14일 기준 RSI
- bollinger_mid: 20일 이동평균선
- bollinger_upper: 볼린저 상단 밴드
- bollinger_lower: 볼린저 하단 밴드
- signal_bollinger_upper: 종가가 상단 밴드 초과시 True
- signal_bollinger_lower: 종가가 하단 밴드 이하시 True
- ma_diff: ma_5 - ma_20
- prev_diff: 전날의 ma_diff
- golden_cross: 골든크로스 발생시 True
- dead_cross: 데드크로스 발생시 True

수정된 SQL:
"""
