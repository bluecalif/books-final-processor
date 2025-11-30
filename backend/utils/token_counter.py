"""
토큰 계산 유틸리티

LLM 호출 시 입력/출력 토큰 수를 계산하고 비용을 예상합니다.
"""
import tiktoken
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TokenCounter:
    """토큰 계산 클래스"""

    def __init__(self, model: str = "gpt-4o-mini"):
        """
        Args:
            model: 모델 이름 (gpt-4o-mini는 cl100k_base 인코딩 사용)
        """
        self.model = model
        # gpt-4o-mini는 cl100k_base 인코딩 사용
        try:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.error(f"[ERROR] Failed to load tiktoken encoding: {e}")
            raise

    def count_tokens(self, text: str) -> int:
        """
        텍스트의 토큰 수 계산

        Args:
            text: 입력 텍스트

        Returns:
            토큰 수
        """
        if not text:
            return 0
        try:
            return len(self.encoding.encode(text))
        except Exception as e:
            logger.warning(f"[WARNING] Failed to count tokens: {e}")
            return 0

    def estimate_output_tokens(self, schema: BaseModel) -> int:
        """
        출력 토큰 예상치 계산 (스키마 기반)

        Args:
            schema: Pydantic 스키마 클래스

        Returns:
            예상 출력 토큰 수
        """
        try:
            # 스키마의 JSON 스키마를 문자열로 변환하여 토큰 수 계산
            json_schema = schema.model_json_schema()
            schema_str = str(json_schema)

            # 스키마 크기 + 실제 데이터 예상치 (스키마의 2-3배)
            schema_tokens = self.count_tokens(schema_str)
            estimated_data_tokens = int(schema_tokens * 2.5)

            return schema_tokens + estimated_data_tokens
        except Exception as e:
            logger.warning(f"[WARNING] Failed to estimate output tokens: {e}")
            # 기본값: 1000 토큰
            return 1000

    def calculate_cost(
        self, input_tokens: int, output_tokens: int, model: Optional[str] = None
    ) -> float:
        """
        비용 계산 (USD)

        Args:
            input_tokens: 입력 토큰 수
            output_tokens: 출력 토큰 수
            model: 모델 이름 (None이면 self.model 사용)

        Returns:
            예상 비용 (USD)
        """
        if model is None:
            model = self.model

        # gpt-4o-mini 가격 (2024년 기준, 1M tokens 기준)
        if model == "gpt-4o-mini":
            input_price_per_1m = 0.4  # $0.4 per 1M input tokens
            output_price_per_1m = 1.6  # $1.6 per 1M output tokens
        else:
            # 기본값 (다른 모델은 여기에 추가)
            input_price_per_1m = 0.4
            output_price_per_1m = 1.6

        input_cost = (input_tokens / 1_000_000) * input_price_per_1m
        output_cost = (output_tokens / 1_000_000) * output_price_per_1m

        return input_cost + output_cost

    def calculate_prompt_tokens(
        self, system_prompt: str, user_prompt: str
    ) -> int:
        """
        프롬프트 토큰 수 계산 (system + user)

        Args:
            system_prompt: 시스템 프롬프트
            user_prompt: 사용자 프롬프트

        Returns:
            총 프롬프트 토큰 수
        """
        system_tokens = self.count_tokens(system_prompt)
        user_tokens = self.count_tokens(user_prompt)
        # OpenAI API는 메시지 형식 오버헤드가 있지만, 여기서는 텍스트만 계산
        return system_tokens + user_tokens

