# 주식 초보를 위한 Finance Multi-Agent System

LangGraph를 사용한 주가 관련 Q&A 및 뉴스 요약 및 보고서 생성 AI 에이전트입니다.


## 🚀 설치 및 설정

### 1. 환경 설정
```bash
# 환경 생성
conda create -n finance-agent python=3.10
conda activate finance-agent

# 패키지 설치
pip install -r requirements.txt
```

## 🎯 사용법

### 기본 실행
```bash
# Graph Framework 기반 에이전트 실행
python scripts/run_agent.py
```

### 데이터 업데이트
```bash
# 매일 주가 데이터 업데이트
python scripts/run_daily_update.py --mode daily

# 매일 뉴스 데이터 업데이트
python scripts/run_news_daily_update.py


## 📁 프로젝트 구조

```
미래에셋/
├── README.md
├── requirements.txt
├── config/
│   ├── _init_.py
│   └── config.py                 # 설정 관리
├── data/
│   ├── krx.tickers.csv          # ticker 정보 엑셀 파일
├── finance_agent/               # 핵심 Finance Agent 패키지
│   ├── _init_.py
│   ├── agent.py                  # 메인 그래프 프레임워크
│   ├── database.py               # 주가 데이터베이스 연결 관리
│   ├── news_db_manager.py        # 뉴스 데이터베이스 연결 관리
│   ├── news_bot.py               # 뉴스 요약 보고서 task
│   ├── updater.py                # 데이터 업데이트
│   ├── llm.py                    # llm 연결 관리
│   ├── prompts.py                # 프롬프트
│   ├── utils.py                  # 날짜, 실시간 정보 등 추출
│   └── nodes/                    # 모듈화된 노드들
│       ├── __init__.py
│       ├── input_node.py         # 입력 처리 & 재질문 노드
│       ├── sql_generator_node.py # SQL 생성 노드(주가 질문)
│       ├── news_handler.py       # SQL 생성 노드(뉴스 요약)
│       ├── query_parser_node.py  # Query parsing
│       ├── sql_refiner_node.py   # SQL 수정 노드
│       └── output_formatter_node.py # 출력 포맷팅 노드
├── scripts/                      # 실행 스크립트
│   ├── run_agent.py             # 에이전트 실행
│   ├── run_daily_update.py      # 데이터 업데이트
│   ├── run_news_daily_update.py      # 데이터 업데이트
├── logs/                        # 로그 파일
└── web_demo.py                  # 데모
```

## 🔧 Graph Framework 아키텍처

```
Input → SQL Generation → Refinement → Output
  ↓           ↓              ↓          ↓
입력 처리 → SQL 쿼리 생성 → 오류 수정 → 결과 포맷팅
```

### 노드별 역할
1. **Input Node**: 사용자 질문 처리 및 명확성 확인
2. **Query Parser Node** : 질문 parsing 처리
3. **SQL Generator Node**: 자연어를 SQL 쿼리로 변환
4. **News Handler**: 뉴스 요약 관련 task 처리
5. **SQL Refiner Node**: SQL 실행 실패 시 자동 수정 (최대 3회)
6. **Output Formatter Node**: 결과를 지정된 형식으로 포맷팅


## 에이전트 기능 
1. 주가 관련 정보 전달
2. 모호한 정보 재질의
3. DB, 실시간 브라우저 검색 기반 뉴스 요약
4. 최근 핫한 뉴스를 선별하여 요약
5. 사용자 관심 키워드 기반 요약 보고서 작성 및 스케줄링
