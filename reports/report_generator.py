# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

from .news_sources import fetch_naver_news, fetch_google_rss, fetch_dart_filings
from .summarizer import simple_dedup, naive_rank, cluster_by_keyword, make_daily_markdown, make_weekly_markdown

DEFAULT_BUCKETS = [
    ("실적/가이던스", ["실적", "가이던스", "분기", "매출", "영업이익", "순이익"]),
    ("규제/소송/제재", ["규제", "소송", "벌금", "제재", "조사", "환수"]),
    ("M&A/투자/조인트", ["인수", "합병", "M&A", "지분", "투자", "전략적"]),
    ("제품/서비스/고객", ["출시", "서비스", "고객", "계약", "수주", "파트너"]),
    ("리스크/안전/ESG", ["사고", "안전", "ESG", "노조", "환경", "지배구조"]),
]

def gather_items(company: str, keywords: Optional[List[str]] = None, size=30) -> List[Dict]:
    items = []
    try:
        items += fetch_naver_news(company, keywords, size=size)
    except Exception:
        pass
    try:
        items += fetch_google_rss(company, keywords, size=size)
    except Exception:
        pass
    try:
        items += fetch_dart_filings(company, size=size)
    except Exception:
        pass
    return items

def build_daily_report(company: str, keywords: Optional[List[str]] = None) -> Dict:
    raw = gather_items(company, keywords)
    deduped = simple_dedup(raw, key_fields=("title",))
    ranked = naive_rank(deduped, company, keywords or [])
    groups = cluster_by_keyword(ranked, DEFAULT_BUCKETS)
    md = make_daily_markdown(company, ranked, groups)
    return {"markdown": md, "items": ranked, "groups": groups}

def build_weekly_report(company: str, keywords: Optional[List[str]] = None, days: int = 7) -> Dict:
    # 단순히 현재 시점 수집으로 구성(운영에선 일일 결과 합산 권장)
    raw = gather_items(company, keywords, size=60)
    deduped = simple_dedup(raw, key_fields=("title",))
    ranked = naive_rank(deduped, company, keywords or [])
    groups = cluster_by_keyword(ranked, DEFAULT_BUCKETS)
    end = datetime.now().date()
    start = end - timedelta(days=days-1)
    md = make_weekly_markdown(company, [start.isoformat(), end.isoformat()], ranked, groups)
    return {"markdown": md, "items": ranked, "groups": groups, "start": start, "end": end}
