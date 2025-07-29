import json, re

def extract_json_from_response(response: str):
    """
    LLM 응답에서 ```json ... ``` 블록을 추출하고,
    홑따옴표(')가 섞인 경우에도 JSON으로 변환할 수 있게 처리.
    """
    match = re.search(r"```json\s*(.*?)```", response, re.DOTALL)
    if not match:
        raise ValueError("No JSON block found")

    json_str = match.group(1).strip()

    # 홑따옴표를 큰따옴표로 치환 (JSON 호환성 확보)
    # 단, 이미 큰따옴표가 있는 경우는 그대로 유지
    if "'" in json_str and '"' not in json_str:
        json_str = json_str.replace("'", '"')

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"[DEBUG:extract_json_from_response] JSON 파싱 실패: {e}, 원본: {json_str[:200]}")
        return {}
