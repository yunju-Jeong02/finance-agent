# -*- coding: utf-8 -*-
import os
import time
import json
import feedparser
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional

def _headers():
    cid = os.getenv("NAVER_CLIENT_ID")
    csc = os.getenv("NAVER_CLIENT_SECRET")
    return {"X-Naver-Client-Id": cid or "", "X-Naver-Client-Secret": csc or ""}

def fetch_naver_news(company: str, keywords: Optional[List[str]] = None, size: int = 20) -> List[Dict]:
    """네이버 뉴스 검색 API (간단 REST). 환경변수 NAVER_CLIENT_ID/SECRET 필요."""
    q = company if not keywords else f"{company} {' '.join(keywords)}"
    url = "https://openapi.naver.com/v1/search/news.json"
    params = {"query": q, "display": min(size, 100), "sort": "date"}
    r = requests.get(url, headers=_headers(), params=params, timeout=10)
    r.raise_for_status()
    data = r.json().get("items", [])
    out = []
    for it in data:
        out.append({
            "source": "naver",
            "title": it.get("title", "").replace("<b>", "").replace("</b>", ""),
            "summary": it.get("description", ""),
            "url": it.get("link"),
            "published": it.get("pubDate"),
        })
    return out

def fetch_google_rss(company: str, keywords: Optional[List[str]] = None, size: int = 20, lang="ko", region="KR") -> List[Dict]:
    """구글 뉴스 RSS (키 기반 제한 없음)."""
    q = company if not keywords else f"{company} {' '.join(keywords)}"
    rss = f"https://news.google.com/rss/search?q={q}&hl={lang}&gl={region}&ceid={region}:{lang}"
    parsed = feedparser.parse(rss)
    out = []
    for e in parsed.entries[:size]:
        out.append({
            "source": "google_rss",
            "title": e.get("title", ""),
            "summary": e.get("summary", ""),
            "url": e.get("link", ""),
            "published": e.get("published", ""),
        })
    return out

def fetch_dart_filings(corp_name: str, size: int = 20) -> List[Dict]:
    """DART 공시 (간단 REST). 환경변수 DART_API_KEY 필요. corp_name 텍스트 검색."""
    api_key = os.getenv("DART_API_KEY")
    if not api_key:
        return []
    # 공시 목록(회사명 검색은 추가 매칭 필요: 여기선 간단 필터)
    base = "https://opendart.fss.or.kr/api/list.json"
    today = datetime.now().date()
    start = (today - timedelta(days=7)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")
    params = {"crtfc_key": api_key, "page_no": 1, "page_count": size, "bgn_de": start, "end_de": end}
    r = requests.get(base, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    out = []
    if data.get("status") == "013":  # too many requests 등
        time.sleep(1)
        return out
    for it in data.get("list", []):
        title = it.get("report_nm", "")
        if corp_name in it.get("corp_name", "") or corp_name in title:
            out.append({
                "source": "dart",
                "title": f"[공시]{title}",
                "summary": it.get("rm", "") or "",
                "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={it.get('rcp_no')}",
                "published": it.get("rpt_nm", "") or it.get("rpt_nm", ""),
            })
    return out
