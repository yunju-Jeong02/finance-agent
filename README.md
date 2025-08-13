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
# 스케줄링 실행
뉴스 스케줄링 입력
```

## 웹 데모
```bash
conda activate finance-agent
pip install streamlit
```
이후 email어쩌고 나오면 암것도 없이 enter해주면 됩니다

```bash
streamlit run web_demo.py
```
끝!
