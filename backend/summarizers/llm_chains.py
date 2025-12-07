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
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Structured Output으로 LLM 호출
                response = self.client.beta.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": prompt["system"]},
                        {"role": "user", "content": prompt["user"]},
                    ],
                    temperature=self.temperature,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": f"{self.domain}_page_extraction",
                            "schema": json_schema,
                            "strict": True,
                        },
                    },
                )

                # 응답 파싱 및 검증
                response_text = response.choices[0].message.content
                result = self.schema_class.model_validate_json(response_text)

                # 실제 토큰 사용량 추출
                usage = None
                if hasattr(response, 'usage') and response.usage:
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

            except Exception as e:
                last_error = e
                error_type = type(e).__name__
                
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # 지수 백오프: 1, 2, 4초
                    logger.warning(
                        f"[WARNING] Page extraction attempt {attempt + 1}/{self.max_retries} failed: "
                        f"{error_type}: {str(e)[:100]}, retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"[ERROR] Page extraction failed after {self.max_retries} attempts: "
                        f"{error_type}: {str(e)[:200]}"
                    )
        
        # 모든 재시도 실패
        raise last_error

    def _build_prompt(self, page_text: str, book_context: Dict[str, Any]) -> Dict[str, str]:
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
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Structured Output으로 LLM 호출
                response = self.client.beta.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": prompt["system"]},
                        {"role": "user", "content": prompt["user"]},
                    ],
                    temperature=self.temperature,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": f"{self.domain}_chapter_structuring",
                            "schema": json_schema,
                            "strict": True,
                        },
                    },
                )

                # 응답 파싱 및 검증
                response_text = response.choices[0].message.content
                result = self.schema_class.model_validate_json(response_text)

                # 실제 토큰 사용량 추출
                usage = None
                if hasattr(response, 'usage') and response.usage:
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

            except Exception as e:
                last_error = e
                error_type = type(e).__name__
                
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # 지수 백오프: 1, 2, 4초
                    logger.warning(
                        f"[WARNING] Chapter structuring attempt {attempt + 1}/{self.max_retries} failed: "
                        f"{error_type}: {str(e)[:100]}, retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"[ERROR] Chapter structuring failed after {self.max_retries} attempts: "
                        f"{error_type}: {str(e)[:200]}"
                    )
        
        # 모든 재시도 실패
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

