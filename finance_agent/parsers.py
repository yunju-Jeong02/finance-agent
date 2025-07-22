# from pydantic import BaseModel
# from langchain.output_parsers import PydanticOutputParser
import re, json

def extract_json_from_response(response: str):
    # 정규식으로 ```json ... ``` 블록만 추출
    match = re.search(r"```json\s*(.*?)```", response, re.DOTALL)
    if not match:
        raise ValueError("No JSON block found")
    json_str = match.group(1).strip()
    return json.loads(json_str)