"""
LLM Chains: 페이지 엔티티 추출 및 챕터 구조화

OpenAI Structured Output을 사용하여 도메인별 스키마에 맞는 엔티티를 추출합니다.
"""

import json
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from openai import OpenAI
from backend.config.settings import settings
from backend.summarizers.schemas import (
    BasePageSchema,
    BaseChapterSchema,
    get_page_schema_class,
    get_chapter_schema_class,
    HistoryPage,
    EconomyPage,
    HumanitiesPage,
    SciencePage,
    HistoryChapter,
    EconomyChapter,
    HumanitiesChapter,
    ScienceChapter,
)

logger = logging.getLogger(__name__)


class PageExtractionChain:
    """페이지 엔티티 추출 LLM Chain"""

    def __init__(self, domain: str, api_key: Optional[str] = None, timeout: int = 120):
        """
        Args:
            domain: 도메인 코드 ("history", "economy", "humanities", "science")
            api_key: OpenAI API 키 (None이면 settings에서 가져옴)
            timeout: OpenAI API 타임아웃 (초, 기본값: 120)
        """
        if api_key is None:
            api_key = settings.openai_api_key
        self.client = OpenAI(api_key=api_key, timeout=timeout)
        self.model = "gpt-4.1-mini"
        self.temperature = 0.3
        self.domain = domain
        self.schema_class = get_page_schema_class(domain)
        self.timeout = timeout
        self.max_retries = 3  # 최대 재시도 횟수

    def extract_entities(
        self, page_text: str, book_context: Dict[str, Any]
    ) -> Tuple[BasePageSchema, Optional[Dict[str, int]]]:
        """
        Structured Output으로 페이지 엔티티 추출

        Args:
            page_text: 페이지 원문 텍스트
            book_context: 책 컨텍스트 (book_title, chapter_title, chapter_number, domain)

        Returns:
            도메인별 페이지 스키마 객체
        """
        logger.info(
            f"[INFO] Extracting page entities (domain={self.domain}, "
            f"chapter={book_context.get('chapter_title', 'N/A')})"
        )

        # 프롬프트 생성
        prompt = self._build_prompt(page_text, book_context)

        # JSON Schema 생성 및 additionalProperties 추가
        json_schema = self.schema_class.model_json_schema()
        # OpenAI Structured Output은 additionalProperties: false를 요구
        _add_additional_properties_false(json_schema)

        # 재시도 로직 (지수 백오프)
        # OpenAI API 호출 실패 시 자동 재시도 (타임아웃, Rate limit, 일시적 오류 등)
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Structured Output으로 LLM 호출
                # strict=True: JSON Schema를 엄격히 준수해야 함
                response = self.client.beta.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": prompt["system"]},
                        {"role": "user", "content": prompt["user"]},
                    ],
                    temperature=self.temperature,  # 0.3 (낮은 값으로 일관성 유지)
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": f"{self.domain}_page_extraction",
                            "schema": json_schema,
                            "strict": True,  # 추가 필드 허용 안 함
                        },
                    },
                )

                # 응답 파싱 및 검증
                # Pydantic 스키마로 자동 검증 (타입, 필수 필드 등)
                response_text = response.choices[0].message.content
                result = self.schema_class.model_validate_json(response_text)

                # 실제 토큰 사용량 추출 (비용 계산용)
                usage = None
                if hasattr(response, "usage") and response.usage:
                    usage = {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    }
                    logger.debug(
                        f"[TOKEN_USAGE] Page extraction: "
                        f"prompt={usage['prompt_tokens']}, "
                        f"completion={usage['completion_tokens']}, "
                        f"total={usage['total_tokens']}"
                    )

                logger.info(f"[INFO] Page entity extraction completed")
                return result, usage

            # 모든 예외 처리 (타임아웃, Rate limit, JSON 파싱 오류 등)
            except Exception as e:
                last_error = e
                error_type = type(e).__name__

                # 마지막 시도가 아니면 재시도
                if attempt < self.max_retries - 1:
                    wait_time = 2**attempt  # 지수 백오프: 1초, 2초, 4초
                    logger.warning(
                        f"[WARNING] Page extraction attempt {attempt + 1}/{self.max_retries} failed: "
                        f"{error_type}: {str(e)[:100]}, retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    # 모든 재시도 실패 시 에러 로그 및 예외 발생
                    logger.error(
                        f"[ERROR] Page extraction failed after {self.max_retries} attempts: "
                        f"{error_type}: {str(e)[:200]}"
                    )

        # 모든 재시도 실패 시 마지막 오류를 다시 발생시킴
        raise last_error

    def _build_prompt(
        self, page_text: str, book_context: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        페이지 엔티티 추출 프롬프트 생성

        Args:
            page_text: 페이지 원문 텍스트
            book_context: 책 컨텍스트

        Returns:
            {"system": "...", "user": "..."}
        """
        book_title = book_context.get("book_title", "Unknown")
        chapter_title = book_context.get("chapter_title", "Unknown")
        chapter_number = book_context.get("chapter_number", "Unknown")
        domain_name = self._get_domain_name(self.domain)

        # 텍스트 길이 제한 (토큰 제한 고려)
        max_chars = 4000
        if len(page_text) > max_chars:
            page_text = page_text[:max_chars] + "..."
            logger.warning(f"[WARNING] Page text truncated to {max_chars} characters")

        system = f"""You are an expert content analyst specializing in {domain_name} domain.
Your task is to extract structured entities from a single page of text.

**CRITICAL RULES**:
1. **NO HALLUCINATION**: Only extract information that is explicitly mentioned in the text.
   - If a person/event/concept is not mentioned, use empty list [] or null.
   - Do NOT invent names, dates, or facts.
2. **Be Specific**: Extract concrete, actionable information.
3. **Be Accurate**: Ensure all extracted information matches the original text.

**Output Format**:
You must return a JSON object that strictly follows the {domain_name} page schema.
All fields must be present and valid according to the schema."""

        user = f"""# BOOK CONTEXT
- Book Title: {book_title}
- Chapter: {chapter_number}. {chapter_title}
- Domain: {domain_name}

# PAGE TEXT
{page_text}

# TASK
Extract structured entities from this page following the {domain_name} page schema:
- page_summary: 2-4 sentences summarizing this page's role in the chapter
- page_function_tag: The function of this page (e.g., "problem_statement", "example_story", "data_explanation")
- persons: List of people mentioned
- concepts: List of key concepts
- events: List of events or historical occurrences
- examples: List of examples or case studies
- references: List of references or citations
- key_sentences: List of most important sentences (3-5 sentences)
- tone_tag: Tone of the page (e.g., "analytical", "narrative", "instructional")
- topic_tags: List of topic tags
- complexity: Complexity level (e.g., "simple", "moderate", "complex")

{self._get_domain_specific_instructions()}

Remember: Only extract what is explicitly mentioned in the text. Do NOT invent or infer."""

        return {"system": system, "user": user}

    def _get_domain_name(self, domain: str) -> str:
        """도메인 코드를 한글 이름으로 변환"""
        mapping = {
            "history": "역사/사회",
            "economy": "경제/경영",
            "humanities": "인문/자기계발",
            "science": "과학/기술",
        }
        return mapping.get(domain, "인문/자기계발")

    def _get_domain_specific_instructions(self) -> str:
        """도메인별 추가 지침"""
        if self.domain == "history":
            return """
**History/Social Domain - Additional Fields**:
- locations: Cities, countries, regions, rivers mentioned
- time_periods: Eras, centuries, dynasties mentioned
- polities: Empires, kingdoms, civilizations mentioned"""
        elif self.domain == "economy":
            return """
**Economy/Business Domain - Additional Fields**:
- indicators: Economic indicators, statistics, graph summaries
- actors: Stakeholders (government, companies, individual investors)
- strategies: Strategies, principles, rules
- cases: Company, city, industry, investment case studies"""
        elif self.domain == "humanities":
            return """
**Humanities/Self-Development Domain - Additional Fields**:
- psychological_states: Emotional/psychological states mentioned
- life_situations: Specific life situations (work, family, relationships)
- practices: Recommended habits or behaviors
- inner_conflicts: Internal conflicts or dilemmas"""
        elif self.domain == "science":
            return """
**Science/Technology Domain - Additional Fields**:
- technologies: Core technologies mentioned
- systems: System/process structures
- applications: Application areas or case studies
- risks_ethics: Risks, ethics, or policy issues"""
        else:
            return ""


def _add_additional_properties_false(schema: Dict[str, Any]) -> None:
    """
    JSON Schema에 additionalProperties: false 및 required 배열 추가 (재귀적으로)

    OpenAI Structured Output의 strict 모드는 다음을 요구합니다:
    1. 모든 객체에 additionalProperties: false
    2. 모든 필드를 required 배열에 포함 (Optional 필드도 포함)

    공통 유틸리티 함수로 두 클래스에서 사용.
    """
    if isinstance(schema, dict):
        # 현재 레벨 처리
        if "type" in schema and schema["type"] == "object":
            # additionalProperties: false 추가
            schema["additionalProperties"] = False

            # required 배열 추가 (모든 properties 키 포함)
            if "properties" in schema and isinstance(schema["properties"], dict):
                # 모든 properties 키를 required에 포함
                schema["required"] = list(schema["properties"].keys())

        # 재귀적으로 모든 하위 객체 처리
        for key, value in schema.items():
            if key in ["properties", "items", "allOf", "anyOf", "oneOf"]:
                if isinstance(value, dict):
                    _add_additional_properties_false(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            _add_additional_properties_false(item)
            elif isinstance(value, dict):
                _add_additional_properties_false(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        _add_additional_properties_false(item)


class ChapterStructuringChain:
    """챕터 구조화 LLM Chain"""

    def __init__(self, domain: str, api_key: Optional[str] = None, timeout: int = 120):
        """
        Args:
            domain: 도메인 코드 ("history", "economy", "humanities", "science")
            api_key: OpenAI API 키 (None이면 settings에서 가져옴)
            timeout: OpenAI API 타임아웃 (초, 기본값: 120)
        """
        if api_key is None:
            api_key = settings.openai_api_key
        self.client = OpenAI(api_key=api_key, timeout=timeout)
        self.model = "gpt-4.1-mini"
        self.temperature = 0.3
        self.domain = domain
        self.schema_class = get_chapter_schema_class(domain)
        self.timeout = timeout
        self.max_retries = 3  # 최대 재시도 횟수

    def structure_chapter(
        self,
        compressed_page_entities: List[Dict[str, Any]],
        book_context: Dict[str, Any],
    ) -> Tuple[BaseChapterSchema, Optional[Dict[str, int]]]:
        """
        페이지 엔티티를 집계하여 챕터 구조화

        Args:
            compressed_page_entities: 압축된 페이지 엔티티 목록
            book_context: 책 컨텍스트 (book_title, chapter_title, chapter_number, book_summary 등)

        Returns:
            도메인별 챕터 스키마 객체
        """
        logger.info(
            f"[INFO] Structuring chapter (domain={self.domain}, "
            f"chapter={book_context.get('chapter_title', 'N/A')}, "
            f"pages={len(compressed_page_entities)})"
        )

        # 프롬프트 생성
        prompt = self._build_prompt(compressed_page_entities, book_context)

        # JSON Schema 생성 및 additionalProperties 추가
        json_schema = self.schema_class.model_json_schema()
        # OpenAI Structured Output은 additionalProperties: false를 요구
        _add_additional_properties_false(json_schema)

        # 재시도 로직 (지수 백오프)
        # OpenAI API 호출 실패 시 자동 재시도 (타임아웃, Rate limit, 일시적 오류 등)
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Structured Output으로 LLM 호출
                # strict=True: JSON Schema를 엄격히 준수해야 함
                response = self.client.beta.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": prompt["system"]},
                        {"role": "user", "content": prompt["user"]},
                    ],
                    temperature=self.temperature,  # 0.3 (낮은 값으로 일관성 유지)
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": f"{self.domain}_chapter_structuring",
                            "schema": json_schema,
                            "strict": True,  # 추가 필드 허용 안 함
                        },
                    },
                )

                # 응답 파싱 및 검증
                # Pydantic 스키마로 자동 검증 (타입, 필수 필드 등)
                response_text = response.choices[0].message.content
                result = self.schema_class.model_validate_json(response_text)

                # 실제 토큰 사용량 추출 (비용 계산용)
                usage = None
                if hasattr(response, "usage") and response.usage:
                    usage = {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    }
                    logger.debug(
                        f"[TOKEN_USAGE] Chapter structuring: "
                        f"prompt={usage['prompt_tokens']}, "
                        f"completion={usage['completion_tokens']}, "
                        f"total={usage['total_tokens']}"
                    )

                logger.info(f"[INFO] Chapter structuring completed")
                return result, usage

            # 모든 예외 처리 (타임아웃, Rate limit, JSON 파싱 오류 등)
            except Exception as e:
                last_error = e
                error_type = type(e).__name__

                # 마지막 시도가 아니면 재시도
                if attempt < self.max_retries - 1:
                    wait_time = 2**attempt  # 지수 백오프: 1초, 2초, 4초
                    logger.warning(
                        f"[WARNING] Chapter structuring attempt {attempt + 1}/{self.max_retries} failed: "
                        f"{error_type}: {str(e)[:100]}, retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    # 모든 재시도 실패 시 에러 로그 및 예외 발생
                    logger.error(
                        f"[ERROR] Chapter structuring failed after {self.max_retries} attempts: "
                        f"{error_type}: {str(e)[:200]}"
                    )

        # 모든 재시도 실패 시 마지막 오류를 다시 발생시킴
        raise last_error

    def _build_prompt(
        self,
        compressed_page_entities: List[Dict[str, Any]],
        book_context: Dict[str, Any],
    ) -> Dict[str, str]:
        """
        챕터 구조화 프롬프트 생성

        Args:
            compressed_page_entities: 압축된 페이지 엔티티 목록
            book_context: 책 컨텍스트

        Returns:
            {"system": "...", "user": "..."}
        """
        book_title = book_context.get("book_title", "Unknown")
        chapter_title = book_context.get("chapter_title", "Unknown")
        chapter_number = book_context.get("chapter_number", "Unknown")
        book_summary = book_context.get("book_summary", "")
        domain_name = self._get_domain_name(self.domain)

        # 페이지 엔티티를 JSON 문자열로 변환
        pages_json = json.dumps(compressed_page_entities, ensure_ascii=False, indent=2)

        system = f"""You are an expert content analyst specializing in {domain_name} domain.
Your task is to synthesize chapter-level structure from page-level entities.

**CRITICAL RULES**:
1. **NO HALLUCINATION**: Only synthesize information from the provided page entities.
   - Do NOT invent new events, people, or concepts.
   - Use only what is present in the page entities.
2. **Synthesize, Don't Summarize**: Create new insights by connecting page-level information.
3. **Maintain Evidence Links**: When creating insights, reference supporting evidence from pages.

**Output Format**:
You must return a JSON object that strictly follows the {domain_name} chapter schema.
All fields must be present and valid according to the schema."""

        user = f"""# BOOK CONTEXT
- Book Title: {book_title}
- Chapter: {chapter_number}. {chapter_title}
- Domain: {domain_name}
- Book Summary: {book_summary if book_summary else "Not provided"}

# COMPRESSED PAGE ENTITIES
{pages_json}

# TASK
Synthesize chapter-level structure from the page entities above:
- core_message: One-line core message of this chapter
- summary_3_5_sentences: 3-5 sentence summary
- argument_flow: Structure with problem, background, main_claims, evidence_overview, counterpoints_or_limits, conclusion_or_action
- key_events: Select only the MOST IMPORTANT events (max 8-10 items)
  * Remove duplicates and merge similar events
  * Prioritize events that are central to the chapter's argument
  * Exclude minor or peripheral events
- key_examples: Select only the MOST REPRESENTATIVE examples (max 5-7 items)
  * Remove duplicates and merge similar examples
  * Prioritize examples that best illustrate the chapter's main points
  * Exclude redundant or less illustrative examples
- key_persons: Select only the MOST SIGNIFICANT persons (max 8-10 items)
  * Remove duplicates (same person mentioned in multiple pages)
  * Prioritize persons who are central to the chapter's narrative
  * Exclude persons who are only briefly mentioned
- key_concepts: Select only the MOST CRITICAL concepts (max 10-12 items)
  * Remove duplicates and merge related concepts
  * Prioritize concepts that are essential to understanding the chapter
  * Exclude peripheral or less important concepts
- insights: List of insights (type, text, supporting_evidence_ids)
- chapter_level_synthesis: Chapter-level synthesis
- references: Consolidated list of references

{self._get_domain_specific_instructions()}

Remember: Synthesize from the provided page entities. Do NOT invent new information."""

        return {"system": system, "user": user}

    def _get_domain_name(self, domain: str) -> str:
        """도메인 코드를 한글 이름으로 변환"""
        mapping = {
            "history": "역사/사회",
            "economy": "경제/경영",
            "humanities": "인문/자기계발",
            "science": "과학/기술",
        }
        return mapping.get(domain, "인문/자기계발")

    def _get_domain_specific_instructions(self) -> str:
        """도메인별 추가 지침"""
        if self.domain == "history":
            return """
**History/Social Domain - Additional Fields**:
- timeline: Timeline of events
- geo_map: Geographic map structure
- structure_layer: Political/economic/social/cultural structure summary"""
        elif self.domain == "economy":
            return """
**Economy/Business Domain - Additional Fields**:
- claims: List of core claims
- frameworks: Models or frameworks
- scenarios: Future scenarios
- playbooks: Action guides or checklists"""
        elif self.domain == "humanities":
            return """
**Humanities/Self-Development Domain - Additional Fields**:
- life_themes: Major life themes
- practice_recipes: Practice protocols
- dilemmas: Dilemmas or questions for readers
- identity_shifts: Identity or worldview changes"""
        elif self.domain == "science":
            return """
**Science/Technology Domain - Additional Fields**:
- problem_domains: Problem domains addressed
- impact_map: Impact by stakeholder
- ethics_issues: Ethics or social debate issues
- future_scenarios: Technology/social change scenarios"""
        else:
            return ""


class BookSummaryChain:
    """책 전체 요약 LLM Chain (Phase 1: 필수 항목)"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = 120,
        enable_cache: bool = True,
        book_title: Optional[str] = None,
    ):
        """
        Args:
            api_key: OpenAI API 키 (None이면 settings에서 가져옴)
            timeout: OpenAI API 타임아웃 (초, 기본값: 120)
            enable_cache: 캐시 사용 여부
            book_title: 책 제목 (캐시 폴더 분리용)
        """
        if api_key is None:
            api_key = settings.openai_api_key
        self.client = OpenAI(api_key=api_key, timeout=timeout)
        self.model = "gpt-4.1-mini"
        self.temperature = 0.3
        self.timeout = timeout
        self.max_retries = 3
        from backend.summarizers.summary_cache_manager import SummaryCacheManager

        self.cache_manager = (
            SummaryCacheManager(book_title=book_title) if enable_cache else None
        )

    def summarize_book(
        self,
        chapter_summaries: List[Dict[str, Any]],
        book_context: Dict[str, Any],
        use_cache: bool = True,
    ) -> Tuple[Dict[str, str], Optional[Dict[str, int]]]:
        """
        챕터별 요약을 집계하여 책 전체 요약 생성

        Args:
            chapter_summaries: 챕터별 요약 리스트 (각 항목은 {"chapter_number": int, "chapter_title": str, "core_message": str, "summary_3_5_sentences": str})
            book_context: 책 컨텍스트 (book_title, author, category)
            use_cache: 캐시 사용 여부

        Returns:
            ({"core_message": str, "summary_3_5_sentences": str}, usage_info)
        """
        logger.info(
            f"[INFO] Summarizing book (title={book_context.get('book_title', 'N/A')}, "
            f"chapters={len(chapter_summaries)})"
        )

        # 1. 캐시 확인
        if use_cache and self.cache_manager:
            cache_key = self._generate_cache_key(chapter_summaries, book_context)
            cached_result = self.cache_manager.get_cached_summary(cache_key, "book")
            if cached_result:
                logger.info(
                    f"[INFO] Cache hit for book summary (hash: {cache_key[:8]}...)"
                )
                return cached_result, None

        prompt = self._build_prompt(chapter_summaries, book_context)

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": prompt["system"]},
                        {"role": "user", "content": prompt["user"]},
                    ],
                    temperature=self.temperature,
                )

                response_text = response.choices[0].message.content

                # JSON 응답 파싱 (core_message와 summary_3_5_sentences 추출)
                try:
                    result = json.loads(response_text)
                except json.JSONDecodeError:
                    # JSON이 아닌 경우 텍스트에서 추출 시도
                    result = self._parse_text_response(response_text)

                usage = None
                if hasattr(response, "usage") and response.usage:
                    usage = {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    }

                logger.info(f"[INFO] Book summarization completed")

                # 캐시 저장
                if use_cache and self.cache_manager:
                    cache_key = self._generate_cache_key(
                        chapter_summaries, book_context
                    )
                    self.cache_manager.save_cache(cache_key, "book", result)
                    logger.info(
                        f"[INFO] Cached book summary (hash: {cache_key[:8]}...)"
                    )

                return result, usage

            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = 2**attempt
                    logger.warning(
                        f"[WARNING] Book summarization attempt {attempt + 1}/{self.max_retries} failed: "
                        f"{type(e).__name__}: {str(e)[:100]}, retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"[ERROR] Book summarization failed after {self.max_retries} attempts: "
                        f"{type(e).__name__}: {str(e)[:200]}"
                    )

        raise last_error

    def _build_prompt(
        self,
        chapter_summaries: List[Dict[str, Any]],
        book_context: Dict[str, Any],
    ) -> Dict[str, str]:
        """책 전체 요약 프롬프트 생성"""
        book_title = book_context.get("book_title", "Unknown")
        author = book_context.get("author", "Unknown")
        category = book_context.get("category", "Unknown")

        # 챕터별 요약을 텍스트로 변환
        chapters_text = ""
        for ch in chapter_summaries:
            chapters_text += f"\n## Chapter {ch.get('chapter_number', 'N/A')}: {ch.get('chapter_title', 'N/A')}\n"
            chapters_text += f"Core Message: {ch.get('core_message', '')}\n"
            chapters_text += f"Summary: {ch.get('summary_3_5_sentences', '')}\n"

        system = """You are an expert book analyst. Your task is to synthesize a book-level summary from chapter summaries.

**CRITICAL RULES**:
1. **NO HALLUCINATION**: Only synthesize information from the provided chapter summaries.
2. **Be Concise**: Create a clear, comprehensive summary that captures the book's essence.
3. **Maintain Accuracy**: Ensure all information matches the chapter summaries.
4. **LANGUAGE**: All output must be in Korean (한국어). Write all summaries, messages, themes, and arguments in Korean.

**Output Format**:
You must return a JSON object with the following structure:
{
  "core_message": "One-line core message of the entire book (in Korean)",
  "summary_3_5_sentences": "3-5 sentence summary of the entire book (in Korean)",
  "main_themes": ["theme1", "theme2", ...],
  "argument_flow": {
    "overall_problem": "...",
    "overall_background": "...",
    "key_arguments": ["argument1", "argument2", ...],
    "overall_conclusion": "..."
  }
}

**IMPORTANT**: All text content must be written in Korean (한국어)."""

        # argument_flow 정보 수집
        argument_flows_text = ""
        for ch in chapter_summaries:
            arg_flow = ch.get("argument_flow", {})
            if arg_flow:
                argument_flows_text += f"\n## Chapter {ch.get('chapter_number', 'N/A')}: {ch.get('chapter_title', 'N/A')}\n"
                argument_flows_text += f"Problem: {arg_flow.get('problem', '')}\n"
                argument_flows_text += f"Background: {arg_flow.get('background', '')}\n"
                argument_flows_text += (
                    f"Main Claims: {', '.join(arg_flow.get('main_claims', []))}\n"
                )
                argument_flows_text += (
                    f"Conclusion: {arg_flow.get('conclusion_or_action', '')}\n"
                )

        user = f"""# BOOK INFORMATION
- Title: {book_title}
- Author: {author}
- Category: {category}

# CHAPTER SUMMARIES
{chapters_text}

# CHAPTER ARGUMENT FLOWS
{argument_flows_text if argument_flows_text else "No argument flow information available."}

# TASK
Based on the chapter summaries and argument flows above, create a book-level summary (ALL IN KOREAN):
1. core_message: One-line core message that captures the essence of the entire book (한국어로 작성)
2. summary_3_5_sentences: 3-5 sentence summary that synthesizes all chapters (한국어로 작성)
3. main_themes: Extract 5-7 main themes from chapter core messages and summaries (remove duplicates, prioritize central themes, 한국어로 작성)
4. argument_flow:
   - overall_problem: Synthesize the core problem addressed by the entire book from chapter problems (한국어로 작성)
   - overall_background: Integrate background explanations from all chapters (한국어로 작성)
   - key_arguments: Select and integrate 8-12 key arguments from chapter main_claims (remove duplicates, prioritize central arguments, 한국어로 작성)
   - overall_conclusion: Synthesize the overall conclusion from chapter conclusions (한국어로 작성)

**CRITICAL**: All text content must be written in Korean (한국어). Return only valid JSON, no additional text."""

        return {"system": system, "user": user}

    def _parse_text_response(self, text: str) -> Dict[str, str]:
        """텍스트 응답에서 JSON 추출 시도"""
        import re

        # JSON 블록 찾기
        json_match = re.search(
            r'\{[^{}]*"core_message"[^{}]*"summary_3_5_sentences"[^{}]*\}',
            text,
            re.DOTALL,
        )
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass

        # 기본값 반환
        return {
            "core_message": "Unable to extract core message",
            "summary_3_5_sentences": (
                text[:500] if text else "Unable to extract summary"
            ),
            "main_themes": [],
            "argument_flow": {
                "overall_problem": "",
                "overall_background": "",
                "key_arguments": [],
                "overall_conclusion": "",
            },
        }

    def _generate_cache_key(
        self,
        chapter_summaries: List[Dict[str, Any]],
        book_context: Dict[str, Any],
    ) -> str:
        """캐시 키 생성 (챕터 요약 + 책 컨텍스트 해시)"""
        cache_data = {
            "chapter_summaries": chapter_summaries,
            "book_context": book_context,
        }
        cache_json = json.dumps(cache_data, sort_keys=True, ensure_ascii=False)
        return self.cache_manager.get_content_hash(cache_json)


class EntitySynthesisChain:
    """엔티티 집계 LLM Chain (Phase 1: 필수 항목)"""

    def __init__(
        self,
        entity_type: str,
        api_key: Optional[str] = None,
        timeout: int = 120,
        enable_cache: bool = True,
        book_title: Optional[str] = None,
    ):
        """
        Args:
            entity_type: 엔티티 타입 ("insights", "key_events", "key_examples", "key_persons", "key_concepts")
            api_key: OpenAI API 키 (None이면 settings에서 가져옴)
            timeout: OpenAI API 타임아웃 (초, 기본값: 120)
            enable_cache: 캐시 사용 여부
            book_title: 책 제목 (캐시 폴더 분리용)
        """
        if api_key is None:
            api_key = settings.openai_api_key
        self.client = OpenAI(api_key=api_key, timeout=timeout)
        self.model = "gpt-4.1-mini"
        self.temperature = 0.3
        self.entity_type = entity_type
        self.timeout = timeout
        self.max_retries = 3
        from backend.summarizers.summary_cache_manager import SummaryCacheManager

        self.cache_manager = (
            SummaryCacheManager(book_title=book_title) if enable_cache else None
        )

        # 엔티티 타입별 최대 개수 설정
        self.max_items = {
            "insights": 15,
            "key_events": 20,
            "key_examples": 15,
            "key_persons": 20,
            "key_concepts": 25,
        }.get(entity_type, 20)

    def synthesize_entities(
        self,
        chapter_entities: List[List[str]],
        book_context: Dict[str, Any],
        use_cache: bool = True,
    ) -> Tuple[List[str], Optional[Dict[str, int]]]:
        """
        챕터별 엔티티를 집계하여 책 전체 엔티티 생성

        Args:
            chapter_entities: 챕터별 엔티티 리스트 (각 항목은 문자열 리스트)
            book_context: 책 컨텍스트 (book_title, category)
            use_cache: 캐시 사용 여부

        Returns:
            (집계된 엔티티 리스트, usage_info)
        """
        logger.info(
            f"[INFO] Synthesizing {self.entity_type} (book={book_context.get('book_title', 'N/A')}, "
            f"chapters={len(chapter_entities)})"
        )

        # 1. 캐시 확인
        if use_cache and self.cache_manager:
            cache_key = self._generate_cache_key(chapter_entities, book_context)
            cached_result = self.cache_manager.get_cached_summary(
                cache_key, f"book_{self.entity_type}"
            )
            if cached_result:
                # 캐시된 결과가 딕셔너리인 경우 리스트 추출
                if (
                    isinstance(cached_result, dict)
                    and self.entity_type in cached_result
                ):
                    entities = cached_result[self.entity_type]
                elif isinstance(cached_result, list):
                    entities = cached_result
                else:
                    entities = cached_result
                logger.info(
                    f"[INFO] Cache hit for {self.entity_type} (hash: {cache_key[:8]}...)"
                )
                return entities, None

        prompt = self._build_prompt(chapter_entities, book_context)

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": prompt["system"]},
                        {"role": "user", "content": prompt["user"]},
                    ],
                    temperature=self.temperature,
                )

                response_text = response.choices[0].message.content

                # JSON 응답 파싱 (리스트 추출)
                try:
                    result = json.loads(response_text)
                    if isinstance(result, dict) and self.entity_type in result:
                        entities = result[self.entity_type]
                    elif isinstance(result, list):
                        entities = result
                    else:
                        entities = self._parse_text_response(response_text)
                except json.JSONDecodeError:
                    entities = self._parse_text_response(response_text)

                # 최대 개수 제한
                if len(entities) > self.max_items:
                    entities = entities[: self.max_items]

                usage = None
                if hasattr(response, "usage") and response.usage:
                    usage = {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    }

                logger.info(
                    f"[INFO] Entity synthesis completed: {self.entity_type} "
                    f"({len(entities)} items)"
                )

                # 캐시 저장
                if use_cache and self.cache_manager:
                    cache_key = self._generate_cache_key(chapter_entities, book_context)
                    cache_data = {self.entity_type: entities}
                    self.cache_manager.save_cache(
                        cache_key, f"book_{self.entity_type}", cache_data
                    )
                    logger.info(
                        f"[INFO] Cached {self.entity_type} (hash: {cache_key[:8]}...)"
                    )

                return entities, usage

            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = 2**attempt
                    logger.warning(
                        f"[WARNING] Entity synthesis attempt {attempt + 1}/{self.max_retries} failed: "
                        f"{type(e).__name__}: {str(e)[:100]}, retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"[ERROR] Entity synthesis failed after {self.max_retries} attempts: "
                        f"{type(e).__name__}: {str(e)[:200]}"
                    )

        raise last_error

    def _build_prompt(
        self,
        chapter_entities: List[List[str]],
        book_context: Dict[str, Any],
    ) -> Dict[str, str]:
        """엔티티 집계 프롬프트 생성"""
        book_title = book_context.get("book_title", "Unknown")
        category = book_context.get("category", "Unknown")

        # 챕터별 엔티티를 텍스트로 변환
        chapters_text = ""
        for idx, entities in enumerate(chapter_entities, 1):
            if entities:
                chapters_text += f"\n## Chapter {idx}\n"
                for entity in entities:
                    chapters_text += f"- {entity}\n"

        entity_name_map = {
            "insights": "인사이트",
            "key_events": "핵심 사건",
            "key_examples": "핵심 예시",
            "key_persons": "핵심 인물",
            "key_concepts": "핵심 개념",
            "main_arguments": "핵심 주장",
            # 도메인별 엔티티
            "timeline": "타임라인",
            "geo_map": "지리적 맵",
            "structure_layer": "구조 레이어",
            "frameworks": "프레임워크",
            "scenarios": "시나리오",
            "playbooks": "행동 가이드",
            "life_themes": "삶의 주제",
            "practice_recipes": "실천 프로토콜",
            "dilemmas": "딜레마",
            "identity_shifts": "정체성 변화",
            "technologies": "기술",
            "systems": "시스템",
            "applications": "적용 영역",
            "risks_ethics": "위험/윤리",
        }
        entity_name = entity_name_map.get(self.entity_type, self.entity_type)

        system = f"""You are an expert content analyst. Your task is to synthesize book-level {entity_name} from chapter-level {entity_name}.

**CRITICAL RULES**:
1. **NO HALLUCINATION**: Only synthesize information from the provided chapter {entity_name}.
2. **Remove Duplicates**: Merge similar or duplicate items.
3. **Select Key Items**: Choose only the most important and representative items (max {self.max_items} items).
4. **Prioritize**: Focus on items that are central to the book's overall narrative.
5. **LANGUAGE**: All output must be in Korean (한국어). Write all items in Korean.

**Output Format**:
You must return a JSON array of strings (all in Korean):
["item1", "item2", "item3", ...]

**IMPORTANT**: All items must be written in Korean (한국어)."""

        user = f"""# BOOK INFORMATION
- Title: {book_title}
- Category: {category}

# CHAPTER {entity_name.upper()}
{chapters_text}

# TASK
Based on the chapter {entity_name} above, synthesize book-level {entity_name} (ALL IN KOREAN):
- Remove duplicates and merge similar items
- Select only the most important items (max {self.max_items} items)
- Prioritize items that are central to the book's overall narrative
- Write all items in Korean (한국어)

**CRITICAL**: All items must be written in Korean (한국어). Return only valid JSON array, no additional text."""

        return {"system": system, "user": user}

    def _parse_text_response(self, text: str) -> List[str]:
        """텍스트 응답에서 리스트 추출 시도"""
        import re

        # JSON 배열 찾기
        json_match = re.search(r"\[.*?\]", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass

        # 줄 단위로 파싱 시도
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        # "- " 또는 숫자로 시작하는 줄 추출
        items = []
        for line in lines:
            line = re.sub(r"^[-•\d.\s]+", "", line).strip()
            if line and len(line) > 5:  # 최소 길이 체크
                items.append(line)

        return items[: self.max_items] if items else []

    def _generate_cache_key(
        self,
        chapter_entities: List[List[str]],
        book_context: Dict[str, Any],
    ) -> str:
        """캐시 키 생성 (챕터 엔티티 + 책 컨텍스트 해시)"""
        cache_data = {
            "entity_type": self.entity_type,
            "chapter_entities": chapter_entities,
            "book_context": book_context,
        }
        cache_json = json.dumps(cache_data, sort_keys=True, ensure_ascii=False)
        return self.cache_manager.get_content_hash(cache_json)
