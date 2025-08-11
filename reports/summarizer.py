# -*- coding: utf-8 -*-
from typing import List, Dict, Tuple
from collections import defaultdict
import math

def _clean(s: str) -> str:
    return (s or "").strip()

def simple_dedup(items: List[Dict], key_fields=("title",)) -> List[Dict]:
    seen = set()
    out = []
    for it in items:
        k = "||".join([_clean(it.get(kf, "")) for kf in key_fields])
        if k not in seen and it.get("url"):
            seen.add(k)
            out.append(it)
    return out

def naive_rank(items: List[Dict], company: str, keywords: List[str] = None) -> List[Dict]:
    """아주 단순한 점수: 최신+키워드 매칭."""
    keywords = keywords or []
    scored = []
    for it in items:
        title = (it.get("title") or "").lower()
        base = 1.0
        if company.lower() in title:
            base += 1.0
        for kw in keywords:
            if kw.lower() in title:
                base += 0.5
        # source 가중(임의)
        src = (it.get("source") or "")
        if src == "dart":
            base += 0.8
        elif src == "naver":
            base += 0.3
        scored.append((base, it))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [it for _, it in scored]

def cluster_by_keyword(items: List[Dict], buckets: List[Tuple[str, List[str]]]) -> Dict[str, List[Dict]]:
    """키워드 바스켓으로 토픽 묶기. (간단 규칙 기반)"""
    groups = defaultdict(list)
    for it in items:
        title = (it.get("title") or "").lower()
        assigned = False
        for label, kws in buckets:
            if any(kw.lower() in title for kw in kws):
                groups[label].append(it)
                assigned = True
                break
        if not assigned:
            groups["기타"].append(it)
    return groups

def bullets(items: List[Dict], topk=5) -> List[str]:
    lines = []
    for it in items[:topk]:
        lines.append(f"- {it.get('title')}  \n  {it.get('url')}")
    return lines

def make_daily_markdown(company: str, ranked: List[Dict], groups: Dict[str, List[Dict]]) -> str:
    top3 = bullets(ranked, topk=3)
    sec = ["# Daily Briefing",
           f"**대상 기업:** {company}",
           "## 헤드라인 Top 3",
           *top3,
           "## 이슈별 묶음"]
    for g, lst in groups.items():
        if not lst: 
            continue
        sec.append(f"### {g}")
        sec += bullets(lst, topk=5)
    return "\n".join(sec)

def make_weekly_markdown(company: str, days: List[str], ranked: List[Dict], groups: Dict[str, List[Dict]]) -> str:
    sec = ["# Weekly Summary",
           f"**대상 기업:** {company}",
           f"**기간:** {days[0]} ~ {days[-1]}",
           "## 주간 Top 5",
           *bullets(ranked, topk=5),
           "## 이슈 클러스터"]
    for g, lst in groups.items():
        if not lst: 
            continue
        sec.append(f"### {g}")
        sec += bullets(lst, topk=7)
    return "\n".join(sec)
