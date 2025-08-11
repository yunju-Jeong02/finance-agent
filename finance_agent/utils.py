import re
from datetime import datetime
import calendar

TODAY_KEYWORDS = ['오늘', '최근', '방금', '지금', '실시간']

def is_url(text: str) -> bool:
    # 문장 안 어디에 있든 URL이 있으면 True
    url_pattern = re.compile(r'https?://[^\s]+')
    return bool(url_pattern.search(text))

def is_today_related(query: str) -> bool:
    return any(k in query for k in TODAY_KEYWORDS)

def extract_date(query: str) -> str:
    print(f"[DEBUG:extract_date] Raw query: {query}")

    # YYYY-MM-DD or YYYY/MM/DD or YYYY.MM.DD
    full_date = re.search(r'(\d{4})[./년\s-](\d{1,2})[./월\s-](\d{1,2})', query)
    if full_date:
        y, m, d = full_date.groups()
        date = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        print(f"[DEBUG:extract_date] Found full date: {date}")
        return date

    # YYYY-MM (월만 있는 경우 → 그 달의 마지막 날)
    year_month = re.search(r'(\d{4})[./년\s-](\d{1,2})', query)
    if year_month:
        y, m = year_month.groups()
        last_day = calendar.monthrange(int(y), int(m))[1]
        date = f"{y}-{m.zfill(2)}-{last_day}"
        print(f"[DEBUG:extract_date] Found year-month, set to last day: {date}")
        return date

    # MM-DD or MM월DD일 (연도는 현재 연도)
    current_year = str(datetime.now().year)
    md = re.search(r'(\d{1,2})[월\s./-](\d{1,2})일?', query)
    if md:
        m, d = md.groups()
        date = f"{current_year}-{m.zfill(2)}-{d.zfill(2)}"
        print(f"[DEBUG:extract_date] Found month-day: {date}")
        return date

    # 날짜 없으면 오늘 날짜
    date = datetime.now().strftime("%Y-%m-%d")
    print(f"[DEBUG:extract_date] Default to today: {date}")
    return date



def extract_keywords(query: str) -> list:
    stopwords = {"요약", "뉴스", "알려줘", "해줘", "핫한", "실시간", "오늘", "요약해줘"}
    words = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', query).split()
    return [w for w in words if w not in stopwords and len(w) > 1]