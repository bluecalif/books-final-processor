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
        
        # book_id -> category 매핑 생성
        book_id_category_map = {book.id: book.category for book in books}
        
        # source_file_path -> category 매핑 생성
        book_category_map = {}
        for book in books:
            if book.source_file_path and book.category:
                # 절대 경로 정규화
                book_category_map[Path(book.source_file_path).resolve()] = book.category
                # 상대 경로도 추가
                book_category_map[book.source_file_path] = book.category
                # 파일명만으로도 매핑
                book_category_map[Path(book.source_file_path).name] = book.category
        
        logger.info(f"[INFO] DB에서 {len(books)}개 책의 분야 정보 매핑 생성")
        
        # text 파일에서 book_id 추출하여 매핑
        text_dir = Path(__file__).parent.parent.parent / "data" / "output" / "text"
        text_file_book_id_map = {}  # text 파일 해시 -> book_id
        
        if text_dir.exists():
            for text_file in text_dir.glob("*.json"):
                try:
                    with open(text_file, 'r', encoding='utf-8') as f:
                        text_data = json.load(f)
                        book_id = text_data.get('book_id')
                        if book_id:
                            # text 파일명의 해시 부분 추출 (예: 3e9a6e_xxx.json -> 3e9a6e)
                            text_file_hash = text_file.stem.split('_')[0]
                            text_file_book_id_map[text_file_hash] = book_id
                except Exception as e:
                    logger.debug(f"[DEBUG] text 파일 읽기 실패: {text_file.name}: {e}")
            
            logger.info(f"[INFO] text 파일에서 {len(text_file_book_id_map)}개 book_id 매핑 생성")
        
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
                pdf_filename = pdf_path.name  # 파일명만 추출
                
                # 매핑에서 분야 찾기 (여러 방법 시도)
                category = None
                
                # 방법 1: 캐시 파일명의 해시로 text 파일 찾아서 book_id 매칭
                cache_file_hash = cache_file.stem  # 확장자 제거
                for text_hash, book_id in text_file_book_id_map.items():
                    if cache_file_hash.startswith(text_hash):
                        if book_id in book_id_category_map:
                            category = book_id_category_map[book_id]
                            logger.info(f"[INFO] 캐시 파일 해시로 매칭: {cache_file.name} -> book_id {book_id} -> 분야: {category}")
                            break
                
                # 방법 2: 절대 경로로 매칭
                if not category and pdf_path_resolved in book_category_map:
                    category = book_category_map[pdf_path_resolved]
                # 방법 3: 원본 경로로 매칭
                elif not category and pdf_path_str in book_category_map:
                    category = book_category_map[pdf_path_str]
                # 방법 4: 파일명으로 매칭 (경로 무관)
                elif not category and pdf_filename in book_category_map:
                    category = book_category_map[pdf_filename]
                    logger.info(f"[INFO] 파일명으로 매칭: {pdf_filename} -> 분야: {category}")
                
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

