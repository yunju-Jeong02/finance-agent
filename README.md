# 한국 주식 시장 Finance Agent

LangGraph를 사용한 한국 주식 시장 데이터 분석 에이전트입니다.


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


### 테스트 실행
```bash
# 모든 테스트 실행
pytest tests/

# 특정 테스트 실행
pytest tests/test_agent.py
pytest tests/test_database.py
```

## 📁 프로젝트 구조

```
미래에셋/
├── README.md
├── requirements.txt
├── config/
│   ├── __init__.py
│   └── config.py                 # 설정 관리
├── finance_agent/               # 핵심 Finance Agent 패키지
│   ├── __init__.py
│   ├── agent.py                  # 메인 그래프 프레임워크
│   ├── database.py               # 데이터베이스 연결 관리
│   ├── updater.py                # 매일 데이터 업데이트
│   └── nodes/                    # 모듈화된 노드들
│       ├── __init__.py
│       ├── input_node.py         # 입력 처리 노드
│       ├── clarification_node.py # 재질문 노드
│       ├── sql_generator_node.py # SQL 생성 노드
│       ├── sql_refiner_node.py   # SQL 수정 노드
│       └── output_formatter_node.py # 출력 포맷팅 노드
├── data/                         # 데이터 저장소
│   ├── examples/                 # 예시 쿼리
│   │   ├── simple_queries.csv
│   │   ├── conditional_queries.csv
│   │   └── signal_queries.csv
│   └── stock/                    # 주식 데이터
│       ├── krx_stockprice.csv
│       ├── krx_tickers.csv
│       └── upload.py
├── api/                          # API 서버
│   ├── __init__.py
│   └── main.py                   # FastAPI 메인
├── scripts/                      # 실행 스크립트
│   ├── run_agent.py             # 에이전트 실행
│   ├── run_api.py               # API 서버 실행
│   ├── run_daily_update.py      # 데이터 업데이트
│   ├── deploy_ngrok.py          # ngrok 배포
│   └── test_agent.py            # 테스트 스크립트
├── tests/                        # 테스트 코드
│   ├── test_agent.py            # 에이전트 테스트
│   └── test_database.py         # 데이터베이스 테스트
└── logs/                         # 로그 파일
```

## 🔧 Graph Framework 아키텍처

```
Input → SQL Generation → Refinement → Output
  ↓           ↓              ↓          ↓
입력 처리 → SQL 쿼리 생성 → 오류 수정 → 결과 포맷팅
```

### 노드별 역할
1. **Input Node**: 사용자 질문 처리 및 명확성 확인
2. **SQL Generator Node**: 자연어를 SQL 쿼리로 변환
3. **SQL Refiner Node**: SQL 실행 실패 시 자동 수정 (최대 3회)
4. **Output Formatter Node**: 결과를 지정된 형식으로 포맷팅
