import re
from datetime import datetime

TODAY_KEYWORDS = ['오늘', '최근', '방금', '지금', '실시간']

def is_today_related(query: str) -> bool:
    return any(k in query for k in TODAY_KEYWORDS)

from datetime import datetime, timedelta
import calendar

def extract_date(query: str):
    current_year = str(datetime.now().year)

    # '7월 3일' 또는 '7월' 패턴
    month_day_pattern = re.search(r'(\d{1,2})[월\s./-](\d{1,2})?일?', query)
    if month_day_pattern:
        month, day = month_day_pattern.groups()
        month = month.zfill(2)
        if day:
            return f"{current_year}-{month}-{day.zfill(2)}"
        # '7월'만 있으면 → 7월 마지막 날
        last_day = calendar.monthrange(int(current_year), int(month))[1]
        return f"{current_year}-{month}-{last_day}"

    # 연도 포함 (YYYY-MM-DD 또는 YYYY-MM)
    full_pattern = re.search(r'(\d{4})[./년\s-](\d{1,2})(?:[월\s./-](\d{1,2}))?', query)
    if full_pattern:
        year, month, day = full_pattern.groups()
        month = month.zfill(2)
        if day:
            return f"{year}-{month}-{day.zfill(2)}"
        last_day = calendar.monthrange(int(year), int(month))[1]
        return f"{year}-{month}-{last_day}"

    # 날짜 없으면 오늘 날짜 반환
    return datetime.now().strftime("%Y-%m-%d")
def is_url(text: str) -> bool:
    # 문장 안 어디에 있든 URL이 있으면 True
    url_pattern = re.compile(r'https?://[^\s]+')
    return bool(url_pattern.search(text))

