# utils/llm_manager.py

from langchain_openai import ChatOpenAI
from langchain_naver import ChatClovaX
from langchain.schema import BaseOutputParser
from config.config import Config

class LLM:
    def __init__(self, model_type="Hyperclova", model_name="HCX-005", temperature=0.1):
        self.config = Config()
        self.model_type = model_type
        self.model_name = model_name
        self.temperature = temperature
        self.llm = self._init_llm()

        from langchain_naver import ChatClovaX

    def _init_llm(self):
        if self.model_type == "Hyperclova":
            return ChatClovaX(
                model=self.model_name, # HCX-DASH-002 or HCX-005
                temperature=self.temperature,
                api_key=self.config.HYPERCLOVA_API_KEY,
            )
        elif self.model_type == "OpenAI":
            return ChatOpenAI(
                model=self.model_name,
                temperature=self.temperature,
                openai_api_key=self.config.OPENAI_API_KEY
            )

    def run(self, prompt: str, parser: BaseOutputParser = None) -> str:
        """
        prompt: str 형태의 프롬프트
        parser: 선택적으로 사용할 output parser
        return: 응답 텍스트 또는 parser 결과
        """
        response = self.llm.invoke(prompt)
        if parser:
            return parser.parse(response.content)
        return response.content

    def get_llm(self):
        return self.llm