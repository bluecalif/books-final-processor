"""
Book 184 (AI지도책) 분석 스크립트
- 챕터 수 및 서머리 연결 관계 확인
- 챕터 3 중복 문제 분석
- 내용이 없는 챕터 확인
"""
import json
from pathlib import Path
from sqlalchemy.orm import Session

from backend.api.database import SessionLocal
from backend.api.models.book import Book, Chapter, PageSummary, ChapterSummary

def analyze_book_184():
    """Book 184 분석"""
    db = SessionLocal()
    try:
        book = db.query(Book).filter(Book.id == 184).first()
        if not book:
            print("[ERROR] Book 184 not found")
            return
        
        print(f"\n{'='*80}")
        print(f"Book 184: {book.title}")
        print(f"{'='*80}\n")
        
        # 챕터 목록 조회
        chapters = (
            db.query(Chapter)
            .filter(Chapter.book_id == 184)
            .order_by(Chapter.order_index)
            .all()
        )
        
        print(f"[1] 실제 도서의 챕터 수: {len(chapters)}개\n")
        print("챕터 목록:")
        for i, ch in enumerate(chapters, 1):
            print(f"  {i}. Chapter ID: {ch.id}, Order: {ch.order_index}, Title: {ch.title}")
            print(f"     Pages: {ch.start_page}~{ch.end_page} (총 {ch.end_page - ch.start_page + 1}페이지)")
        
        # 챕터 서머리 조회
        chapter_summaries = (
            db.query(ChapterSummary)
            .filter(ChapterSummary.book_id == 184)
            .all()
        )
        
        print(f"\n[2] 챕터 서머리 수: {len(chapter_summaries)}개\n")
        print("챕터 서머리 목록:")
        for cs in chapter_summaries:
            chapter = db.query(Chapter).filter(Chapter.id == cs.chapter_id).first()
            if chapter:
                print(f"  Chapter ID: {cs.chapter_id}, Order: {chapter.order_index}, Title: {chapter.title}")
                print(f"    Summary ID: {cs.id}")
                print(f"    Has structured_data: {cs.structured_data is not None}")
                if cs.structured_data:
                    core_msg = cs.structured_data.get("core_message", "")[:50]
                    print(f"    Core message: {core_msg}...")
            else:
                print(f"  Chapter ID: {cs.chapter_id} (Chapter not found!)")
        
        # 챕터별 서머리 매핑 확인
        print(f"\n[3] 챕터-서머리 연결 관계:\n")
        chapter_summary_map = {cs.chapter_id: cs for cs in chapter_summaries}
        
        for i, ch in enumerate(chapters, 1):
            cs = chapter_summary_map.get(ch.id)
            if cs:
                print(f"  ✓ 챕터 {i} (ID: {ch.id}, Order: {ch.order_index}): 서머리 있음 (ID: {cs.id})")
            else:
                print(f"  ✗ 챕터 {i} (ID: {ch.id}, Order: {ch.order_index}): 서머리 없음")
        
        # 챕터 3 중복 문제 분석
        print(f"\n[4] 챕터 3 중복 문제 분석:\n")
        chapter_3 = [ch for ch in chapters if ch.order_index == 2]  # order_index는 0-based
        if chapter_3:
            ch3 = chapter_3[0]
            print(f"  챕터 3 정보:")
            print(f"    Chapter ID: {ch3.id}")
            print(f"    Title: {ch3.title}")
            print(f"    Pages: {ch3.start_page}~{ch3.end_page}")
            
            # 챕터 3의 서머리 확인
            cs3 = chapter_summary_map.get(ch3.id)
            if cs3:
                print(f"    서머리 ID: {cs3.id}")
                if cs3.structured_data:
                    print(f"    Core message: {cs3.structured_data.get('core_message', '')[:100]}")
            
            # 같은 페이지 범위를 가진 다른 챕터 확인
            overlapping = [
                ch for ch in chapters 
                if ch.id != ch3.id 
                and ch.start_page <= ch3.end_page 
                and ch.end_page >= ch3.start_page
            ]
            if overlapping:
                print(f"\n  ⚠️ 중복 가능성: 다음 챕터들과 페이지 범위가 겹침:")
                for ch in overlapping:
                    print(f"    - Chapter ID: {ch.id}, Order: {ch.order_index}, Title: {ch.title}")
                    print(f"      Pages: {ch.start_page}~{ch.end_page}")
        
        # 내용이 없는 챕터 확인
        print(f"\n[5] 내용이 없는 챕터 확인:\n")
        for i, ch in enumerate(chapters, 1):
            cs = chapter_summary_map.get(ch.id)
            if not cs:
                print(f"  ✗ 챕터 {i} (ID: {ch.id}, Order: {ch.order_index}, Title: {ch.title}): 서머리 없음")
            elif not cs.structured_data:
                print(f"  ⚠️ 챕터 {i} (ID: {ch.id}, Order: {ch.order_index}, Title: {ch.title}): structured_data 없음")
            else:
                # 페이지 엔티티 확인
                page_count = (
                    db.query(PageSummary)
                    .filter(
                        PageSummary.book_id == 184,
                        PageSummary.page_number >= ch.start_page,
                        PageSummary.page_number <= ch.end_page
                    )
                    .count()
                )
                if page_count == 0:
                    print(f"  ⚠️ 챕터 {i} (ID: {ch.id}): 페이지 엔티티 없음 (서머리는 있음)")
        
        # 캐시 파일 확인
        print(f"\n[6] 캐시 파일 확인:\n")
        cache_dir = Path("data/cache/summaries/AI지도책")
        if cache_dir.exists():
            chapter_cache_files = list(cache_dir.glob("chapter_*.json"))
            print(f"  캐시된 챕터 서머리 파일: {len(chapter_cache_files)}개")
            for cache_file in sorted(chapter_cache_files):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    core_msg = cache_data.get("core_message", "")[:50] if isinstance(cache_data, dict) else ""
                    print(f"    {cache_file.name}: {core_msg}...")
        
        print(f"\n{'='*80}\n")
        
    finally:
        db.close()

if __name__ == "__main__":
    analyze_book_184()

