"""
캐시 일관성 문제 조사 스크립트

Book 176의 페이지 추출 상태와 챕터 구조화 상태를 분석합니다.
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.api.database import SessionLocal
from backend.api.models.book import Book, Chapter, PageSummary
from collections import defaultdict

def investigate_book_176():
    """Book 176의 상태 조사"""
    db = SessionLocal()
    
    try:
        # Book 176 조회
        book = db.query(Book).filter(Book.id == 176).first()
        if not book:
            print("Book 176 not found")
            return
        
        print(f"=== Book 176 조사 ===")
        print(f"제목: {book.title}")
        print(f"분야: {book.category}")
        print(f"상태: {book.status}")
        print(f"페이지 수: {book.page_count}")
        print()
        
        # 구조 데이터 확인
        if book.structure_data:
            if "main_start_page" in book.structure_data:
                main_start = book.structure_data["main_start_page"]
                main_end = book.structure_data["main_end_page"]
                main_pages = list(range(main_start, main_end + 1))
                print(f"본문 페이지 범위: {main_start} ~ {main_end} (총 {len(main_pages)} 페이지)")
            elif "main" in book.structure_data and "pages" in book.structure_data["main"]:
                main_pages = book.structure_data["main"]["pages"]
                print(f"본문 페이지: {len(main_pages)} 페이지")
        else:
            print("구조 데이터 없음")
            return
        
        print()
        
        # PageSummary 상태 확인
        page_summaries = db.query(PageSummary).filter(PageSummary.book_id == 176).all()
        print(f"=== PageSummary 상태 ===")
        print(f"총 PageSummary 레코드 수: {len(page_summaries)}")
        
        # structured_data가 있는 페이지
        pages_with_data = [ps for ps in page_summaries if ps.structured_data]
        print(f"structured_data가 있는 페이지: {len(pages_with_data)}")
        
        # structured_data가 없는 페이지
        pages_without_data = [ps for ps in page_summaries if not ps.structured_data]
        if pages_without_data:
            print(f"structured_data가 없는 페이지: {len(pages_without_data)}")
            print(f"  페이지 번호: {[ps.page_number for ps in pages_without_data]}")
        
        # 페이지 번호 리스트
        page_numbers = sorted([ps.page_number for ps in pages_with_data])
        print(f"성공한 페이지 번호 범위: {page_numbers[0]} ~ {page_numbers[-1]} (총 {len(page_numbers)} 페이지)")
        print()
        
        # 챕터별 분석
        chapters = db.query(Chapter).filter(Chapter.book_id == 176).order_by(Chapter.order_index).all()
        print(f"=== 챕터별 분석 (총 {len(chapters)}개 챕터) ===")
        
        for chapter in chapters:
            chapter_pages = list(range(chapter.start_page, chapter.end_page + 1))
            
            # 해당 챕터의 PageSummary 조회
            chapter_page_summaries = [
                ps for ps in pages_with_data 
                if chapter.start_page <= ps.page_number <= chapter.end_page
            ]
            
            # 챕터에 포함되어야 할 페이지 수
            expected_pages = len(chapter_pages)
            # 실제로 structured_data가 있는 페이지 수
            actual_pages = len(chapter_page_summaries)
            
            missing_pages = [p for p in chapter_pages if p not in [ps.page_number for ps in chapter_page_summaries]]
            
            print(f"\nChapter {chapter.order_index + 1}: {chapter.title}")
            print(f"  페이지 범위: {chapter.start_page} ~ {chapter.end_page} (총 {expected_pages} 페이지)")
            print(f"  structured_data가 있는 페이지: {actual_pages}/{expected_pages}")
            if missing_pages:
                print(f"  누락된 페이지: {missing_pages}")
        
        print()
        
        # 챕터 구조화에 사용될 페이지 엔티티 확인
        print(f"=== 챕터 구조화 입력 데이터 분석 ===")
        for chapter in chapters:
            chapter_pages = list(range(chapter.start_page, chapter.end_page + 1))
            
            # extract_chapters 로직과 동일하게 페이지 엔티티 수집
            page_entities_list = []
            for page_number in chapter_pages:
                page_summary = (
                    db.query(PageSummary)
                    .filter(
                        PageSummary.book_id == 176,
                        PageSummary.page_number == page_number,
                    )
                    .first()
                )
                
                if page_summary and page_summary.structured_data:
                    entity = page_summary.structured_data.copy()
                    entity["page_number"] = page_number
                    page_entities_list.append(entity)
            
            print(f"Chapter {chapter.order_index + 1}: {chapter.title}")
            print(f"  챕터 구조화에 사용될 페이지 엔티티 수: {len(page_entities_list)}/{len(chapter_pages)}")
            if len(page_entities_list) < len(chapter_pages):
                missing = [p for p in chapter_pages if p not in [e["page_number"] for e in page_entities_list]]
                print(f"  누락된 페이지: {missing}")
        
    finally:
        db.close()

if __name__ == "__main__":
    investigate_book_176()

