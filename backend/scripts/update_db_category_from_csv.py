"""
CSV 파일에서 분야 정보를 읽어서 DB의 Book 레코드에 업데이트하는 스크립트

CSV 파일의 Title과 DB의 title을 매칭하여 분야 정보를 업데이트합니다.
"""
import logging
from pathlib import Path
from sqlalchemy.orm import Session

from backend.api.database import SessionLocal
from backend.api.models.book import Book
from backend.utils.csv_parser import parse_book_list

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def normalize_title(title: str) -> str:
    """
    제목 정규화 (매칭을 위해)
    
    - 공백 제거
    - 특수문자 제거 (% 등)
    - 숫자, 한글, 영문만 남기기
    """
    if not title:
        return ""
    
    import re
    
    # 공백 제거, 앞뒤 공백 제거
    normalized = title.strip().replace(" ", "").replace("　", "")  # 전각/반각 공백 모두
    
    # 특수문자 제거 (% 등) - 숫자, 한글, 영문만 남기기
    normalized = re.sub(r'[^0-9가-힣a-zA-Z]', '', normalized)
    
    return normalized


def find_matching_book(csv_title: str, db_books: list[Book]) -> Book | None:
    """
    CSV 제목과 DB 제목 매칭
    
    Args:
        csv_title: CSV의 제목
        db_books: DB의 Book 리스트
        
    Returns:
        매칭된 Book 객체 또는 None
    """
    csv_normalized = normalize_title(csv_title)
    
    for book in db_books:
        if not book.title:
            continue
        
        db_normalized = normalize_title(book.title)
        
        # 정확히 일치
        if csv_normalized == db_normalized:
            return book
        
        # 부분 일치 (CSV 제목이 DB 제목에 포함되거나 그 반대)
        if csv_normalized in db_normalized or db_normalized in csv_normalized:
            # 너무 짧은 제목은 제외 (예: "1" 같은 것)
            if len(csv_normalized) >= 3:
                logger.debug(f"[DEBUG] 부분 일치: CSV '{csv_title}' <-> DB '{book.title}'")
                return book
    
    return None


def update_db_category_from_csv(csv_path: str | Path):
    """
    CSV 파일에서 분야 정보를 읽어서 DB의 Book 레코드에 업데이트
    
    Args:
        csv_path: CSV 파일 경로
    """
    csv_path = Path(csv_path)
    
    logger.info("=" * 80)
    logger.info(f"[INFO] DB 분야 정보 업데이트 시작: {csv_path}")
    logger.info("=" * 80)
    
    # 1. CSV 파일 파싱
    logger.info("[STEP 1] CSV 파일 파싱 중...")
    csv_books = parse_book_list(csv_path)
    logger.info(f"[INFO] CSV에서 {len(csv_books)}개 도서 발견")
    
    # 2. DB에서 모든 Book 조회
    db: Session = SessionLocal()
    
    try:
        logger.info("[STEP 2] DB에서 모든 Book 레코드 조회 중...")
        db_books = db.query(Book).all()
        logger.info(f"[INFO] DB에서 {len(db_books)}개 Book 레코드 발견")
        
        # 3. CSV의 각 도서와 DB의 Book 매칭하여 업데이트
        logger.info("[STEP 3] CSV와 DB 매칭하여 분야 정보 업데이트 중...")
        
        updated_count = 0
        not_found_count = 0
        already_has_category_count = 0
        
        for csv_book in csv_books:
            csv_title = csv_book.get("Title", "")
            csv_category = csv_book.get("분야", "")
            
            if not csv_title:
                continue
            
            # DB에서 매칭되는 Book 찾기
            matching_book = find_matching_book(csv_title, db_books)
            
            if not matching_book:
                logger.warning(f"[WARNING] 매칭되는 Book을 찾을 수 없음: '{csv_title}'")
                not_found_count += 1
                continue
            
            # 이미 분야 정보가 있으면 스킵 (또는 업데이트 여부 확인)
            if matching_book.category:
                logger.debug(f"[DEBUG] 이미 분야 정보 있음: '{csv_title}' (분야: {matching_book.category})")
                already_has_category_count += 1
                # 기존 분야 정보를 덮어쓰기 (선택적 - 필요시 주석 처리)
                # continue
            
            # 분야 정보 업데이트
            matching_book.category = csv_category
            logger.info(f"[INFO] 업데이트: '{csv_title}' (ID: {matching_book.id}) -> 분야: {csv_category}")
            updated_count += 1
        
        # 4. 커밋
        logger.info("[STEP 4] 변경사항 커밋 중...")
        db.commit()
        logger.info(f"[INFO] 커밋 완료")
        
        # 5. 결과 요약
        logger.info("=" * 80)
        logger.info(f"[INFO] 업데이트 완료")
        logger.info(f"[INFO] 업데이트된 레코드: {updated_count}개")
        logger.info(f"[INFO] 이미 분야 정보 있음: {already_has_category_count}개")
        logger.info(f"[INFO] 매칭 실패: {not_found_count}개")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"[ERROR] 업데이트 실패: {e}")
        db.rollback()
        raise
    
    finally:
        db.close()


if __name__ == "__main__":
    csv_path = Path(__file__).parent.parent.parent / "docs" / "100권 노션 원본_수정.csv"
    update_db_category_from_csv(csv_path)

