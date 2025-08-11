# -*- coding: utf-8 -*-
from typing import Dict
from ..reports.report_generator import build_daily_report, build_weekly_report


class ReportBuilderNode:
    """
    parsed_query.intent:
      - 'daily_report_request'
      - 'weekly_report_request'
    parsed_query fields:
      - company: str
      - keywords: List[str] (optional)
    """
    def process(self, state: Dict) -> Dict:
        pq = state.get("parsed_query", {}) or {}
        intent = pq.get("intent", "")
        company = pq.get("company") or pq.get("target") or ""
        keywords = pq.get("keywords") or []

        if not company:
            state["clarification_needed"] = True
            state["clarification_question"] = "어떤 기업의 보고서를 생성할까요? (예: KB금융)"
            return state

        if intent == "daily_report_request":
            res = build_daily_report(company, keywords=keywords)
            state["final_output"] = res["markdown"]
            state["is_complete"] = True
            return state

        if intent == "weekly_report_request":
            res = build_weekly_report(company, keywords=keywords)
            state["final_output"] = res["markdown"]
            state["is_complete"] = True
            return state

        # 의도 불명확 시 pass-through
        state["final_output"] = "보고서 의도를 인식하지 못했습니다. '데일리 보고서' 또는 '주간 보고서'라고 말씀해 주세요."
        state["is_complete"] = True
        return state
