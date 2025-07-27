import http.client, json, uuid, requests, re
from config import Config
from utils import is_today_related, is_url, extract_date

class CompletionExecutor:
    def __init__(self, host, api_key):
        self._host = host
        self._api_key = api_key

    def execute_summarization(self, text):
        endpoint = "/testapp/v1/api-tools/summarization/v2"
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'Authorization': f'Bearer {self._api_key}',
            'X-NCP-CLOVASTUDIO-REQUEST-ID': str(uuid.uuid4())
        }
        payload = {
            "texts": [text],
            "segMinSize": 300,
            "includeAiFilters": True,
            "autoSentenceSplitter": True,
            "segCount": -1,
            "segMaxSize": 1000
        }
        conn = http.client.HTTPSConnection(self._host)
        conn.request('POST', endpoint, json.dumps(payload), headers)
        res = conn.getresponse()
        data = json.loads(res.read().decode('utf-8'))
        conn.close()
        if data.get('status', {}).get('code') == '20000':
            return data['result']['text']
        return f"[요약 오류] {data.get('status', {}).get('message', '응답 없음')}"

class ClovaClient:
    def __init__(self):
        self.executor = CompletionExecutor(Config.CLOVA_HOST, Config.CLOVA_API_KEY)
        self.hyperclova_host = "https://" + Config.CLOVA_HOST
        self.api_key = Config.CLOVA_API_KEY
        self.model_endpoint = "/v3/chat-completions/HCX-005"

    def summarize(self, text):
        return self.executor.execute_summarization(text)

    def classify_intent(self, user_query):
        # URL은 무조건 우선
        if is_url(user_query):  # 무조건 최우선
            return "url_summary_request"

        # HyperClova 기반 분류
        prompt = f"""
        사용자의 뉴스 요청을 6가지 중 하나로 분류해 JSON으로만 출력해.
        가능한 카테고리:
        - "hot_news_request"
        - "today_news_request"
        - "url_summary_request"
        - "news_summary_request"
        - "clarification_needed"
        - "unknown"
        입력: "{user_query}"
        """
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'X-NCP-CLOVASTUDIO-REQUEST-ID': str(uuid.uuid4()),
            'Content-Type': 'application/json; charset=utf-8'
        }
        payload = {
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
            "topP": 0.8, "temperature": 0.2, "maxTokens": 100
        }
        try:
            resp = requests.post(self.hyperclova_host + self.model_endpoint, headers=headers, json=payload)
            raw = resp.json().get("result", {}).get("message", {}).get("content", [{}])[0].get("text", "")
            match = re.search(r'\{.*\}', raw)
            if match:
                return json.loads(match.group(0)).get("intent", "unknown")
        except:
            pass

        # Fallback
        if is_today_related(user_query):
            return "today_news_request"
        if extract_date(user_query):
            return "news_summary_request"
        words = [w for w in re.sub(r'[^가-힣a-zA-Z0-9\s]', '', user_query).split() if len(w) > 1]
        if words:
            return "news_summary_request"
        return "unknown"
