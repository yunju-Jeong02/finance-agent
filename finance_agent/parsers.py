import json, re
import logging


def extract_json_from_response(response: str) -> dict:
    """
    LLM 응답에서 ```json … ``` 블록을 꺼내고,
    홑따옴표 문자열 값, 트레일링 콤마를 정제하여 JSON으로 파싱.
    성공·실패 시 모두 디버그 로그를 남깁니다.
    """
    # 1) ```json … ``` 블록 추출
    match = re.search(r"```json\s*(\{.*?\})\s*```", response, re.DOTALL)
    if not match:
        logging.error("No JSON block found in response.")
        raise ValueError("No JSON block found")
    json_str = match.group(1)

    # 2) 값 위치의 홑따옴표 → 쌍따옴표 변환
    json_str = re.sub(
        r"(:\s*)'([^']*?)'",
        lambda m: f'{m.group(1)}\"{m.group(2)}\"',
        json_str
    )

    # 3) 트레일링 콤마 제거 (예: {"a":1,} → {"a":1})
    json_str = re.sub(r",\s*([}\]])", r"\1", json_str)


    # 5) 파싱 시도
    try:
        parsed = json.loads(json_str)
        return parsed
    except json.JSONDecodeError as e:
        return {}
