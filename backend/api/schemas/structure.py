"""구조 분석 관련 Pydantic 스키마"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class LLMChapterSuggestion(BaseModel):
    """LLM 챕터 제안 스키마"""
    number: Optional[int] = None
    title: str
    start_page: int
    end_page: int


class LLMStructureSuggestion(BaseModel):
    """LLM 구조 제안 스키마"""
    main_start_page: int
    main_end_page: Optional[int] = None
    chapters: List[LLMChapterSuggestion]
    notes_pages: List[int] = []
    issues: Optional[str] = None


class FinalChapterInput(BaseModel):
    """최종 챕터 입력 스키마"""
    title: str
    start_page: int
    end_page: int
    order_index: Optional[int] = None


class FinalStructureInput(BaseModel):
    """최종 구조 입력 스키마"""
    main_start_page: int
    main_end_page: Optional[int] = None
    chapters: List[FinalChapterInput]
    notes_pages: List[int] = []
    start_pages: List[int] = []
    end_pages: List[int] = []


class StructureCandidate(BaseModel):
    """구조 후보 스키마"""
    label: str
    structure: Dict[str, Any]


class StructureCandidatesResponse(BaseModel):
    """구조 후보 응답 스키마"""
    meta: Dict[str, Any]
    auto_candidates: List[StructureCandidate]
    chapter_title_candidates: List[str]
    samples: Dict[str, List[Dict[str, Any]]]

