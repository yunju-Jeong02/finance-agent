##  url 요약
User input : https://www.newsis.com/view/NISX20250814_0003290136 요약해줘
state["parsed_query"] = {
                "intent": intent,
                "date": None,               # URL엔 날짜 불필요
                "keywords": ["https://www.newsis.com/view/NISX20250814_0003290136"],          # 원본 URL 그대로
                "company_name": "",
                "market": ""
            }

## DB 뉴스 검색
User input : 삼성전자 7월 4일 뉴스 요약해줘
state["parsed_query"] = {
                "intent": intent,
                "date": 2025-07-04,
                "keywords": "삼성전자",
                "company_name": "",
                "market": ""
            }
query = text(f"""
            SELECT DISTINCT title, link, date, NULL as content
            FROM News WHERE ticker=="005930.KS" and date =="20250704"
            ORDER BY date DESC, id DESC LIMIT :limit;
        """)


## DB 검색 실패 시 크롤링
User input : 삼성전자 7월 4일 뉴스 요약해줘
url = (
                f"https://search.naver.com/search.naver"
                f"?where=news&query={삼성전자}&sm=tab_opt&sort=0"
                f"&ds={ds}&de={de}&nso=so%3Ar%2Cp%3Afrom{20250704}to{20250704}"
            )
elements = driver.find_elements(By.XPATH, '//span[contains(@class, "sds-comps-text-type-headline1")]/parent::a')

articles.append({
                    "title": title,
                    "link": href,
                    "date": "20250704",
                    "content": content,
                })
## 실시간 요약에서는 date : 오늘날짜 (이외 동작 동일)


## Hot News 요약
User input : 핫한 뉴스 요약해줘
top_5_keywords = ["삼성전자", "AI", "2분기", "실적", "한화시스템"]
df = self.news_db.get_recent_news_titles(limit=100)

for _, row in df.iterrows():
    matched_keywords = [kw for kw in top_5_keywords if kw in row['title']]
    if len(matched_keywords) >= 2:
        # 일치하는 키워드 수와 가장 상위의 키워드 인덱스로 우선순위 점수 부여
        score = len(matched_keywords) * 100 - min([top_5_keywords.index(kw) for kw in matched_keywords])
        candidate_news.append({"score": score, "item": row.to_dict()})

# 점수 순으로 정렬
candidate_news.sort(key=lambda x: x['score'], reverse=True)
selected_news = [item['item'] for item in candidate_news]



## 크롤링 및 본문 요약 단계 - llm prompt 활용
news_summary_prompt = """
다음 뉴스 기사 본문을 간결하게 요약해 주세요.
- 핵심 이슈, 관련 회사, 숫자 데이터가 있다면 유지합니다.
- 5줄 이내로 요약합니다.
- 불필요한 수식어나 사설은 제외합니다.

기사 제목: {title}

기사 본문:
{content}

요약:
기사 출처: {url}
"""
                
  
