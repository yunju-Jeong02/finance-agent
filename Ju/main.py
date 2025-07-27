import warnings
# pandas UserWarning을 무시하도록 설정
warnings.filterwarnings('ignore', category=UserWarning, module='pandas')

from clova_client import ClovaClient
from db_client import DBClient
from crawler_client import NewsCrawler
from url_client import URLSummaryClient
from news_agent import NewsAgent

def main():
    clova = ClovaClient()
    db = DBClient()
    crawler = NewsCrawler()
    url_client = URLSummaryClient(clova)
    agent = NewsAgent(clova, db, crawler, url_client)

    print("=== 네이버 Clova 기반 뉴스 요약 Agent ===")
    print("원하는 뉴스를 물어보세요. (예: '오늘 삼성전자 뉴스', '2025년 7월 AI 기사', 기사 URL 등)")
    print("종료하려면 'q' 입력.\n")

    while True:
        user_input = input("\n질문을 입력해주세요: ").strip()
        if user_input.lower() == 'q':
            print("뉴스 요약 에이전트를 종료합니다.")
            break

        answer = agent.process_query(user_input)
        print(f"\n[답변]\n{answer}")

if __name__ == "__main__":
    main()