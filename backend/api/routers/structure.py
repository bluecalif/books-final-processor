"""구조 분석 관련 API 라우터"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.database import get_db
from backend.api.services.structure_service import StructureService
from backend.api.schemas.structure import (
    StructureCandidatesResponse,
    FinalStructureInput,
)
from backend.api.schemas.book import BookResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/books", tags=["structure"])


@router.get("/{book_id}/structure/candidates", response_model=StructureCandidatesResponse)
def get_structure_candidates(book_id: int, db: Session = Depends(get_db)):
    """
    구조 후보 조회

    휴리스틱 구조 + LLM 보정 구조를 반환합니다.
    """
    try:
        service = StructureService(db)
        candidates = service.get_structure_candidates(book_id)
        return candidates
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"[ERROR] Failed to get structure candidates: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{book_id}/structure/final", response_model=BookResponse)
def apply_final_structure(
    book_id: int, final_structure: FinalStructureInput, db: Session = Depends(get_db)
):
    """
    최종 구조 확정

    사용자가 선택한 최종 구조를 DB에 저장하고 Chapter 테이블을 재생성합니다.
    상태가 parsed → structured로 변경됩니다.
    """
    try:
        service = StructureService(db)
        book = service.apply_final_structure(book_id, final_structure)
        return book
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"[ERROR] Failed to apply final structure: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

