"""
기존 캐시 파일에 분야(category) 정보 추가 마이그레이션 스크립트

기존 캐시 파일의 _cache_meta에 category 필드를 추가합니다.
DB의 Book 레코드와 매칭하여 분야 정보를 가져옵니다.
"""
import json
import logging
from pathlib import Path
from sqlalchemy.orm import Session

from backend.api.database import SessionLocal
from backend.api.models.book import Book
from backend.config.settings import settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def migrate_cache_category():
    """기존 캐시 파일에 분야 정보 추가"""
    cache_dir = settings.cache_dir / "upstage"
    
    if not cache_dir.exists():
        logger.warning(f"[WARNING] 캐시 디렉토리가 존재하지 않습니다: {cache_dir}")
        return
    
    cache_files = list(cache_dir.glob("*.json"))
    logger.info(f"[INFO] 총 {len(cache_files)}개의 캐시 파일 발견")
    
    # DB 세션 생성
    db: Session = SessionLocal()
    
    try:
        # DB에서 모든 Book 레코드 조회 (category가 있는 것만)
        books = db.query(Book).filter(Book.category.isnot(None)).all()
        
        # source_file_path -> category 매핑 생성
        book_category_map = {}
        for book in books:
            if book.source_file_path and book.category:
                # 절대 경로 정규화
                book_category_map[Path(book.source_file_path).resolve()] = book.category
                # 상대 경로도 추가
                book_category_map[book.source_file_path] = book.category
        
        logger.info(f"[INFO] DB에서 {len(book_category_map)}개의 분야 정보 매핑 생성")
        
        updated_count = 0
        skipped_count = 0
        
        for cache_file in cache_files:
            try:
                # 캐시 파일 읽기
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                # _cache_meta 확인
                if '_cache_meta' not in cache_data:
                    logger.warning(f"[WARNING] {cache_file.name}: _cache_meta 없음")
                    skipped_count += 1
                    continue
                
                cache_meta = cache_data['_cache_meta']
                
                # 이미 category가 있으면 스킵
                if 'category' in cache_meta and cache_meta['category']:
                    logger.debug(f"[DEBUG] {cache_file.name}: 이미 category 있음 ({cache_meta['category']})")
                    skipped_count += 1
                    continue
                
                # pdf_path에서 분야 정보 찾기
                pdf_path_str = cache_meta.get('pdf_path')
                if not pdf_path_str:
                    logger.warning(f"[WARNING] {cache_file.name}: pdf_path 없음")
                    skipped_count += 1
                    continue
                
                # 경로 정규화
                pdf_path = Path(pdf_path_str)
                pdf_path_resolved = pdf_path.resolve() if pdf_path.exists() else pdf_path
                
                # 매핑에서 분야 찾기
                category = None
                if pdf_path_resolved in book_category_map:
                    category = book_category_map[pdf_path_resolved]
                elif pdf_path_str in book_category_map:
                    category = book_category_map[pdf_path_str]
                
                if not category:
                    logger.warning(f"[WARNING] {cache_file.name}: 분야 정보를 찾을 수 없음 (pdf_path: {pdf_path_str})")
                    skipped_count += 1
                    continue
                
                # category 추가
                cache_meta['category'] = category
                
                # 임시 파일로 저장
                temp_file = cache_file.with_suffix('.tmp')
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, ensure_ascii=False, indent=2)
                
                # 원자적 이동
                temp_file.replace(cache_file)
                
                updated_count += 1
                logger.info(f"[INFO] {cache_file.name}: category 추가 완료 ({category})")
                
            except Exception as e:
                logger.error(f"[ERROR] {cache_file.name} 처리 실패: {e}")
                continue
        
        logger.info("=" * 80)
        logger.info(f"[INFO] 마이그레이션 완료")
        logger.info(f"[INFO] 업데이트된 파일: {updated_count}개")
        logger.info(f"[INFO] 스킵된 파일: {skipped_count}개")
        logger.info("=" * 80)
        
    finally:
        db.close()


if __name__ == "__main__":
    migrate_cache_category()

