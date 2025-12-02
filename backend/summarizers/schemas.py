"""
도메인별 엔티티 추출 스키마 정의

entity_extraction_guideline.md를 기반으로 페이지 및 챕터 단위 구조화 스키마를 정의합니다.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


# =============================================================================
# 페이지 공통 스키마
# =============================================================================


class BasePageSchema(BaseModel):
    """페이지 공통 스키마"""

    page_summary: str = Field(
        ..., description="페이지 요약 (2~4문장, 장 전체 논지에서의 역할 포함)"
    )
    page_function_tag: Optional[str] = Field(
        None,
        description="페이지 기능 태그 (예: problem_statement, example_story, data_explanation)",
    )
    persons: List[str] = Field(default_factory=list, description="인물 목록")
    concepts: List[str] = Field(default_factory=list, description="개념 목록")
    events: List[str] = Field(default_factory=list, description="사건 목록")
    examples: List[str] = Field(default_factory=list, description="예시 목록")
    references: List[str] = Field(default_factory=list, description="참고자료 목록")
    key_sentences: List[str] = Field(default_factory=list, description="핵심 문장 목록")
    tone_tag: Optional[str] = Field(None, description="톤 태그")
    topic_tags: List[str] = Field(default_factory=list, description="주제 태그 목록")
    complexity: Optional[str] = Field(None, description="복잡도 태그")


# =============================================================================
# 도메인별 페이지 스키마
# =============================================================================


class HistoryPage(BasePageSchema):
    """역사/사회 페이지 스키마"""

    locations: List[str] = Field(
        default_factory=list, description="도시/국가/지역/강 등"
    )
    time_periods: List[str] = Field(default_factory=list, description="연대/세기/시대")
    polities: List[str] = Field(default_factory=list, description="왕조/제국/문명")


class EconomyPage(BasePageSchema):
    """경제/경영 페이지 스키마"""

    indicators: List[str] = Field(
        default_factory=list, description="지표/수치/그래프 요약"
    )
    actors: List[str] = Field(
        default_factory=list, description="정부/기업/개인 투자자 등 이해관계자"
    )
    strategies: List[str] = Field(default_factory=list, description="전략/원칙/규칙")
    cases: List[str] = Field(
        default_factory=list, description="회사/도시/산업/투자 사례"
    )


class HumanitiesPage(BasePageSchema):
    """인문/자기계발 페이지 스키마"""

    psychological_states: List[str] = Field(
        default_factory=list, description="정서/심리 상태"
    )
    life_situations: List[str] = Field(
        default_factory=list, description="직장/가족/관계 등 구체 상황"
    )
    practices: List[str] = Field(default_factory=list, description="추천 습관/행동")
    inner_conflicts: List[str] = Field(
        default_factory=list, description="내적 갈등/딜레마"
    )


class SciencePage(BasePageSchema):
    """과학/기술 페이지 스키마"""

    technologies: List[str] = Field(default_factory=list, description="핵심 기술")
    systems: List[str] = Field(default_factory=list, description="시스템/프로세스 구조")
    applications: List[str] = Field(default_factory=list, description="적용 영역/사례")
    risks_ethics: List[str] = Field(
        default_factory=list, description="위험/윤리/정책 이슈"
    )


# =============================================================================
# 챕터 공통 스키마
# =============================================================================


class ArgumentFlow(BaseModel):
    """논증 흐름 구조"""

    problem: str = Field(default="", description="문제 제기")
    background: str = Field(default="", description="배경 설명")
    main_claims: List[str] = Field(default_factory=list, description="주요 주장 목록")
    evidence_overview: str = Field(default="", description="증거 개요")
    counterpoints_or_limits: str = Field(default="", description="반론 또는 한계")
    conclusion_or_action: str = Field(default="", description="결론 또는 행동 촉구")


class BaseChapterSchema(BaseModel):
    """챕터 공통 스키마"""

    core_message: str = Field(..., description="핵심 메시지 (한 줄)")
    summary_3_5_sentences: str = Field(..., description="3~5문장 요약")
    argument_flow: ArgumentFlow = Field(
        default_factory=ArgumentFlow, description="논증 흐름 구조"
    )
    key_events: List[str] = Field(
        default_factory=list,
        description="핵심 사건 목록 (페이지 엔티티 통합/중복 제거)",
    )
    key_examples: List[str] = Field(
        default_factory=list,
        description="핵심 예시 목록 (페이지 엔티티 통합/중복 제거)",
    )
    key_persons: List[str] = Field(
        default_factory=list,
        description="핵심 인물 목록 (페이지 엔티티 통합/중복 제거)",
    )
    key_concepts: List[str] = Field(
        default_factory=list,
        description="핵심 개념 목록 (페이지 엔티티 통합/중복 제거)",
    )
    insights: List[str] = Field(
        default_factory=list, description="인사이트 목록 (각 인사이트는 텍스트 형태)"
    )
    chapter_level_synthesis: str = Field(..., description="챕터 수준 종합")
    references: List[str] = Field(
        default_factory=list, description="참고 문헌·자료 통합 정리"
    )


# =============================================================================
# 도메인별 챕터 스키마
# =============================================================================


class HistoryChapter(BaseChapterSchema):
    """역사/사회 챕터 스키마"""

    timeline: List[str] = Field(
        default_factory=list, 
        description="타임라인 (예: '1000년: 정화의 항해', '1433년: 명나라 항해 종료')"
    )
    geo_map: str = Field(
        default="", 
        description="지리적 맵 (텍스트 설명: 주요 지역 및 경로)"
    )
    structure_layer: str = Field(
        default="", 
        description="정치/경제/사회/문화 구조 요약 (텍스트 설명)"
    )


class EconomyChapter(BaseChapterSchema):
    """경제/경영 챕터 스키마"""

    claims: List[str] = Field(default_factory=list, description="핵심 주장 목록")
    frameworks: List[str] = Field(default_factory=list, description="모델/프레임워크")
    scenarios: List[str] = Field(default_factory=list, description="미래 시나리오")
    playbooks: List[str] = Field(
        default_factory=list, description="행동 가이드/체크리스트"
    )


class HumanitiesChapter(BaseChapterSchema):
    """인문/자기계발 챕터 스키마"""

    life_themes: List[str] = Field(default_factory=list, description="삶의 큰 주제")
    practice_recipes: List[str] = Field(
        default_factory=list, description="실천 프로토콜"
    )
    dilemmas: List[str] = Field(
        default_factory=list, description="독자에게 던지는 딜레마/질문"
    )
    identity_shifts: List[str] = Field(
        default_factory=list, description="정체성/세계관 변화"
    )


class ScienceChapter(BaseChapterSchema):
    """과학/기술 챕터 스키마"""

    problem_domains: List[str] = Field(
        default_factory=list, description="다루는 문제 영역"
    )
    impact_map: str = Field(
        default="", 
        description="이해관계자별 영향 (텍스트 설명: 정부, 기업, 개인 등)"
    )
    ethics_issues: List[str] = Field(default_factory=list, description="윤리/사회 논쟁")
    future_scenarios: List[str] = Field(
        default_factory=list, description="기술/사회 변화 시나리오"
    )


# =============================================================================
# 도메인 매핑 함수
# =============================================================================


def get_domain_from_category(category: str) -> str:
    """
    Book.category를 도메인 코드로 변환

    Args:
        category: 책 분야 (예: "역사/사회", "경제/경영" 등)

    Returns:
        도메인 코드 ("history", "economy", "humanities", "science")
    """
    mapping = {
        "역사/사회": "history",
        "경제/경영": "economy",
        "인문/자기계발": "humanities",
        "과학/기술": "science",
    }
    return mapping.get(category, "humanities")  # 기본값: humanities


def get_page_schema_class(domain: str) -> type[BasePageSchema]:
    """
    도메인 코드에 해당하는 페이지 스키마 클래스 반환

    Args:
        domain: 도메인 코드 ("history", "economy", "humanities", "science")

    Returns:
        페이지 스키마 클래스
    """
    schema_map = {
        "history": HistoryPage,
        "economy": EconomyPage,
        "humanities": HumanitiesPage,
        "science": SciencePage,
    }
    return schema_map.get(domain, HumanitiesPage)  # 기본값: HumanitiesPage


def get_chapter_schema_class(domain: str) -> type[BaseChapterSchema]:
    """
    도메인 코드에 해당하는 챕터 스키마 클래스 반환

    Args:
        domain: 도메인 코드 ("history", "economy", "humanities", "science")

    Returns:
        챕터 스키마 클래스
    """
    schema_map = {
        "history": HistoryChapter,
        "economy": EconomyChapter,
        "humanities": HumanitiesChapter,
        "science": ScienceChapter,
    }
    return schema_map.get(domain, HumanitiesChapter)  # 기본값: HumanitiesChapter
