# 한국 주식 시장 Finance Agent

LangGraph와 Yahoo Finance API를 사용한 한국 주식 시장 데이터 분석 에이전트입니다.

## 기능

- **단순조회**: 특정 종목의 특정 날짜 데이터 조회 (시가, 고가, 저가, 종가, 등락률, 거래량)
- **시장통계**: KOSPI/KOSDAQ 지수, 거래대금, 상승/하락 종목 수
- **순위조회**: 상승률, 하락률, 거래량, 가격 순위
- **조건검색**: 구체적인 수치 조건으로 종목 검색
- **기술적 분석**: RSI, 이동평균, 볼린저밴드 등 기술적 신호

## 설치

```bash
# 환경 생성
conda create -n finance-agent python=3.9
conda activate finance-agent

# 패키지 설치
pip install -r requirements.txt
```

## 사용법

### 대화형 실행
```bash
python scripts/run_agent.py
```

### 테스트 실행
```bash
python scripts/test_agent.py
```

### 예시 질문
- "삼성전자의 2024-01-01 종가는?"
- "2024-07-15 KOSPI 지수는?"
- "2024-08-16에 상승한 종목은 몇 개?"
- "등락률이 +5% 이상인 종목을 알려줘"
- "상승률 높은 종목 5개"

## 프로젝트 구조

```
├── src/
│   ├── core/               # 핵심 에이전트 로직
│   │   ├── agent_nodes.py  # 노드 구현
│   │   └── finance_agent.py # 메인 에이전트
│   ├── data/               # 데이터 관련 모듈
│   │   ├── data_fetcher.py # 데이터 수집
│   │   ├── database.py     # 데이터베이스 연결
│   │   └── technical_analyzer.py # 기술적 분석
│   └── utils/              # 유틸리티
│       ├── prompts.py      # 프롬프트 관리
│       └── schemas.py      # 데이터 스키마
├── config/
│   └── config.py           # 설정 관리
├── data/                   # 예시 쿼리 및 데이터 저장소
│   ├── simple_queries.csv  # 단순 조회 예시
│   ├── conditional_queries.csv # 조건 검색 예시
│   └── signal_queries.csv  # 시그널 감지 예시
└── scripts/                # 실행 스크립트
    ├── run_agent.py        # 에이전트 실행
    └── test_agent.py       # 테스트 스크립트
```