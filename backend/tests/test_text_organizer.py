"""텍스트 정리 테스트 스크립트"""
import json
import logging
from pathlib import Path
from backend.structure.text_organizer import TextOrganizer
from backend.config.settings import settings
from backend.api.database import SessionLocal
from backend.api.models.book import Book

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_text_organizer():
    """구조 분석 결과 파일이 있는 모든 책에 대해 텍스트 정리 실행"""
    structure_dir = settings.output_dir / "structure"
    
    # 구조 분석 결과 파일 목록
    structure_files = list(structure_dir.glob("*_structure.json"))
    
    logger.info(f"[INFO] 구조 분석 결과 파일 {len(structure_files)}개 발견")
    
    text_organizer = TextOrganizer()
    db = SessionLocal()
    
    try:
        for structure_file in structure_files:
            try:
                # 구조 분석 결과 로드
                with open(structure_file, "r", encoding="utf-8") as f:
                    structure_data = json.load(f)
                
                book_id = structure_data.get("book_id")
                book_title = structure_data.get("book_title", "")
                
                logger.info(f"[INFO] 텍스트 정리 시작: book_id={book_id}, title={book_title}")
                
                # DB에서 책 정보 조회
                book = db.query(Book).filter(Book.id == book_id).first()
                if not book:
                    logger.warning(f"[WARNING] DB에서 책을 찾을 수 없음: book_id={book_id}")
                    continue
                
                pdf_path = book.source_file_path
                if not Path(pdf_path).exists():
                    logger.warning(f"[WARNING] PDF 파일이 존재하지 않음: {pdf_path}")
                    continue
                
                logger.info(f"[INFO] PDF 파일: {pdf_path}")
                
                # 텍스트 정리 실행
                output_path = text_organizer.organize_text(
                    book_id=book_id,
                    structure_data=structure_data,
                    pdf_path=pdf_path,
                    book_title=book_title or book.title,
                )
                
                logger.info(f"[INFO] 텍스트 정리 완료: {output_path}")
                
                # 결과 확인
                if output_path.exists():
                    with open(output_path, "r", encoding="utf-8") as f:
                        text_data = json.load(f)
                    
                    chapter_count = len(text_data.get("text_content", {}).get("chapters", []))
                    total_pages = sum(
                        len(ch.get("pages", []))
                        for ch in text_data.get("text_content", {}).get("chapters", [])
                    )
                    
                    logger.info(
                        f"[INFO] 결과 확인: 챕터 {chapter_count}개, "
                        f"총 페이지 {total_pages}개"
                    )
                else:
                    logger.error(f"[ERROR] 출력 파일이 생성되지 않음: {output_path}")
                    
            except Exception as e:
                logger.error(f"[ERROR] 텍스트 정리 실패: {structure_file}, error={e}")
                import traceback
                logger.error(traceback.format_exc())
    finally:
        db.close()


if __name__ == "__main__":
    test_text_organizer()

