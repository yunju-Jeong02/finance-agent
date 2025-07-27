
import uuid
from config.config import Config
from langchain.schema import BaseOutputParser
from langchain_naver import ChatClovaX

class LLM:
    def __init__(self, model_name="HCX-005", temperature=0.1):
        self.config = Config()
        self.model_name = model_name
        self.temperature = temperature
        self.llm = self._init_llm()

    def _init_llm(self):
        return ChatClovaX(
            model=self.model_name,
            temperature=self.temperature,
            api_key=self.config.CLOVA_API_KEY,
            default_headers={
                "X-NCP-CLOVASTUDIO-REQUEST-ID": str(uuid.uuid4())
            }
        )

    def run(self, prompt: str, parser: BaseOutputParser = None) -> str:
        response = self.llm.invoke(prompt)
        if parser:
            return parser.parse(response.content)
        return response.content

    def get_llm(self):
        return self.llm
