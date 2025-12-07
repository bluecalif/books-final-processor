"""
기존 Summary 캐시를 시각화 가능한 구조로 변환하는 스크립트

현재 구조:
{
  "summary_text": "{\"page_summary\":\"...\",\"persons\":[...],...}",
  "summary_type": "page",
  "content_hash": "...",
  "cached_at": 1234567890
}

변경 후 구조:
{
  "page_summary": "...",
  "persons": [...],
  "concepts": [...],
  "summary_type": "page",
  "content_hash": "...",
  "cached_at": 1234567890
}
"""
import json
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, List, Tuple
from backend.api.database import SessionLocal
from backend.api.models.book import Book, BookStatus
from backend.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_books_with_summaries(db_session) -> List[Book]:
    """Summary가 생성된 도서 조회"""
    books = db_session.query(Book).filter(
        Book.status.in_([
            BookStatus.PAGE_SUMMARIZED,
            BookStatus.SUMMARIZED
        ])
    ).all()
    return books


def normalize_book_title_for_path(title: str) -> str:
    """책 제목을 파일 경로에 사용 가능한 형태로 변환"""
    if not title:
        return "unknown"
    # 파일명으로 사용 불가능한 문자 제거
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_title = safe_title.replace(' ', '_')[:100]  # 길이 제한
    return safe_title


def convert_cache_file(cache_file: Path) -> Tuple[bool, str]:
    """
    캐시 파일을 새 형식으로 변환
    
    Returns:
        (성공 여부, 에러 메시지)
    """
    try:
        # 1. 기존 파일 읽기
        with open(cache_file, 'r', encoding='utf-8') as f:
            old_data = json.load(f)
        
        # 2. summary_text 필드 확인
        if "summary_text" not in old_data:
            return False, "summary_text 필드가 없음"
        
        summary_text = old_data.get("summary_text")
        if not summary_text:
            return False, "summary_text가 비어있음"
        
        # 3. JSON 문자열 파싱
        try:
            parsed_data = json.loads(summary_text)
        except json.JSONDecodeError as e:
            return False, f"JSON 파싱 실패: {e}"
        
        # 4. 새 구조 생성
        new_data = {
            **parsed_data,  # 파싱된 필드들을 루트 레벨로 전개
            "summary_type": old_data.get("summary_type"),
            "content_hash": old_data.get("content_hash"),
            "cached_at": old_data.get("cached_at")
        }
        
        # 5. 기존 파일 백업
        backup_file = cache_file.with_suffix('.json.backup')
        shutil.copy2(cache_file, backup_file)
        
        # 6. 새 형식으로 저장
        temp_file = cache_file.with_suffix('.tmp')
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(new_data, f, ensure_ascii=False, indent=2)
        
        # 7. 원자적 이동
        temp_file.replace(cache_file)
        
        return True, ""
        
    except Exception as e:
        return False, f"변환 실패: {e}"


def migrate_book_cache(book: Book, cache_dir: Path) -> Dict[str, Any]:
    """특정 도서의 캐시 파일 변환"""
    book_title = normalize_book_title_for_path(book.title)
    book_cache_dir = cache_dir / book_title
    
    if not book_cache_dir.exists():
        logger.warning(f"[WARNING] Book {book.id} ({book.title}): 캐시 디렉토리 없음: {book_cache_dir}")
        return {
            "book_id": book.id,
            "book_title": book.title,
            "status": "skipped",
            "reason": "캐시 디렉토리 없음",
            "page_count": 0,
            "chapter_count": 0
        }
    
    # 캐시 파일 찾기
    page_files = list(book_cache_dir.glob("page_*.json"))
    chapter_files = list(book_cache_dir.glob("chapter_*.json"))
    
    # .backup 파일 제외
    page_files = [f for f in page_files if not f.name.endswith('.backup')]
    chapter_files = [f for f in chapter_files if not f.name.endswith('.backup')]
    
    logger.info(
        f"[INFO] Book {book.id} ({book.title}): "
        f"페이지 캐시 {len(page_files)}개, 챕터 캐시 {len(chapter_files)}개 발견"
    )
    
    # 변환 실행
    page_success = 0
    page_failed = 0
    chapter_success = 0
    chapter_failed = 0
    errors = []
    
    for cache_file in page_files:
        success, error_msg = convert_cache_file(cache_file)
        if success:
            page_success += 1
        else:
            page_failed += 1
            errors.append(f"페이지 {cache_file.name}: {error_msg}")
    
    for cache_file in chapter_files:
        success, error_msg = convert_cache_file(cache_file)
        if success:
            chapter_success += 1
        else:
            chapter_failed += 1
            errors.append(f"챕터 {cache_file.name}: {error_msg}")
    
    return {
        "book_id": book.id,
        "book_title": book.title,
        "status": "completed" if (page_failed == 0 and chapter_failed == 0) else "partial",
        "page_count": len(page_files),
        "page_success": page_success,
        "page_failed": page_failed,
        "chapter_count": len(chapter_files),
        "chapter_success": chapter_success,
        "chapter_failed": chapter_failed,
        "errors": errors[:10]  # 최대 10개만 저장
    }


def main():
    """메인 함수"""
    logger.info("=" * 80)
    logger.info("[INFO] Summary 캐시 시각화 변환 스크립트 시작")
    logger.info("=" * 80)
    
    # 1. DB에서 Summary 생성된 도서 조회
    db = SessionLocal()
    try:
        books = get_books_with_summaries(db)
        logger.info(f"[INFO] Summary 생성된 도서 {len(books)}개 발견")
        
        if len(books) == 0:
            logger.info("[INFO] 변환할 도서가 없습니다.")
            return
        
        # 2. 캐시 디렉토리 확인
        cache_dir = settings.cache_dir / "summaries"
        if not cache_dir.exists():
            logger.error(f"[ERROR] 캐시 디렉토리가 없습니다: {cache_dir}")
            return
        
        logger.info(f"[INFO] 캐시 디렉토리: {cache_dir}")
        
        # 3. 각 도서별 캐시 변환
        results = []
        for book in books:
            logger.info(f"\n[INFO] Book {book.id} ({book.title}) 변환 시작...")
            result = migrate_book_cache(book, cache_dir)
            results.append(result)
            
            if result["status"] == "completed":
                logger.info(
                    f"[INFO] Book {book.id} 변환 완료: "
                    f"페이지 {result['page_success']}/{result['page_count']}, "
                    f"챕터 {result['chapter_success']}/{result['chapter_count']}"
                )
            elif result["status"] == "partial":
                logger.warning(
                    f"[WARNING] Book {book.id} 부분 변환: "
                    f"페이지 {result['page_success']}/{result['page_count']}, "
                    f"챕터 {result['chapter_success']}/{result['chapter_count']}"
                )
                for error in result.get("errors", []):
                    logger.warning(f"[WARNING]   - {error}")
            else:
                logger.warning(f"[WARNING] Book {book.id} 스킵: {result.get('reason', '알 수 없음')}")
        
        # 4. 결과 요약
        logger.info("\n" + "=" * 80)
        logger.info("[INFO] 변환 결과 요약")
        logger.info("=" * 80)
        
        total_page_success = sum(r.get("page_success", 0) for r in results)
        total_page_failed = sum(r.get("page_failed", 0) for r in results)
        total_chapter_success = sum(r.get("chapter_success", 0) for r in results)
        total_chapter_failed = sum(r.get("chapter_failed", 0) for r in results)
        
        logger.info(f"[INFO] 총 페이지 캐시: 성공 {total_page_success}개, 실패 {total_page_failed}개")
        logger.info(f"[INFO] 총 챕터 캐시: 성공 {total_chapter_success}개, 실패 {total_chapter_failed}개")
        
        # 5. 결과를 JSON 파일로 저장
        output_file = Path("data/output/cache_migration_results.json")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "summary": {
                    "total_books": len(books),
                    "total_page_success": total_page_success,
                    "total_page_failed": total_page_failed,
                    "total_chapter_success": total_chapter_success,
                    "total_chapter_failed": total_chapter_failed
                },
                "details": results
            }, f, ensure_ascii=False, indent=2)
        
        logger.info(f"[INFO] 결과 파일: {output_file}")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()

