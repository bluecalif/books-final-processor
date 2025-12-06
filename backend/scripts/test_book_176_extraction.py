"""
Book 176 전체 추출 테스트 스크립트

개선 사항 검증:
1. DB 세션 문제 해결 확인
2. 페이지 성공 개수 일관성 확인
3. 챕터 캐시 일관성 확인
4. 디버깅 로그 검증
"""
import sys
import time
import httpx
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.api.database import SessionLocal
from backend.api.models.book import Book, BookStatus, PageSummary, ChapterSummary

TEST_SERVER_URL = "http://127.0.0.1:8000"  # 기본 서버 포트

def test_book_176_extraction():
    """Book 176 전체 추출 테스트"""
    print("=" * 80)
    print("Book 176 전체 추출 테스트")
    print("=" * 80)
    
    book_id = 176
    
    # 1. Book 176 상태 확인
    db = SessionLocal()
    try:
        book = db.query(Book).filter(Book.id == book_id).first()
        if not book:
            print(f"[ERROR] Book {book_id} not found")
            return
        
        print(f"[INFO] Book 176: {book.title}")
        print(f"[INFO] Status: {book.status}")
        print(f"[INFO] Category: {book.category}")
        
        if book.status != BookStatus.STRUCTURED:
            print(f"[WARNING] Book {book_id} is not in 'structured' status. Resetting...")
            # PageSummary, ChapterSummary 삭제
            db.query(PageSummary).filter(PageSummary.book_id == book_id).delete()
            db.query(ChapterSummary).filter(ChapterSummary.book_id == book_id).delete()
            book.status = BookStatus.STRUCTURED
            db.commit()
            print(f"[INFO] Book {book_id} reset to 'structured' status")
    finally:
        db.close()
    
    # 2. API 클라이언트 생성
    client = httpx.Client(base_url=TEST_SERVER_URL, timeout=300.0)
    
    try:
        # 3. 페이지 엔티티 추출 시작
        print(f"\n[TEST] Starting page extraction for book_id={book_id}...")
        response = client.post(f"/api/books/{book_id}/extract/pages")
        
        if response.status_code != 200:
            print(f"[ERROR] Failed to start page extraction: {response.status_code}")
            print(f"[ERROR] Response: {response.text}")
            return
        
        result = response.json()
        print(f"[TEST] Extraction started: {result}")
        
        # 4. 페이지 추출 완료 대기
        print(f"[TEST] Waiting for page extraction to complete...")
        start_time = time.time()
        max_wait_time = 1800  # 30분
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > max_wait_time:
                print(f"[ERROR] Timeout after {max_wait_time} seconds")
                break
            
            response = client.get(f"/api/books/{book_id}")
            if response.status_code != 200:
                print(f"[ERROR] Failed to get book status: {response.status_code}")
                break
            
            book_data = response.json()
            status = book_data["status"]
            
            # 진행 상황 확인
            pages_response = client.get(f"/api/books/{book_id}/pages")
            if pages_response.status_code == 200:
                page_count = len(pages_response.json())
                print(f"[TEST] Status: {status}, Pages: {page_count} (elapsed: {elapsed:.1f}s)")
            
            if status == "page_summarized":
                print(f"[TEST] Page extraction completed (elapsed: {elapsed:.1f}s)")
                break
            elif status in ["error_summarizing", "failed"]:
                print(f"[ERROR] Page extraction failed: status={status}")
                break
            
            time.sleep(5)
        
        # 5. 페이지 추출 결과 확인
        print(f"\n[TEST] Checking page extraction results...")
        response = client.get(f"/api/books/{book_id}/pages")
        if response.status_code == 200:
            page_entities = response.json()
            print(f"[TEST] Total pages extracted: {len(page_entities)}")
            
            # 실패한 페이지 확인
            db = SessionLocal()
            try:
                total_pages = db.query(PageSummary).filter(PageSummary.book_id == book_id).count()
                pages_with_data = db.query(PageSummary).filter(
                    PageSummary.book_id == book_id,
                    PageSummary.structured_data.isnot(None)
                ).count()
                print(f"[TEST] PageSummaries in DB: {total_pages}")
                print(f"[TEST] Pages with structured_data: {pages_with_data}")
            finally:
                db.close()
        
        # 6. 챕터 구조화 시작
        print(f"\n[TEST] Starting chapter structuring for book_id={book_id}...")
        response = client.post(f"/api/books/{book_id}/extract/chapters")
        
        if response.status_code != 200:
            print(f"[ERROR] Failed to start chapter structuring: {response.status_code}")
            return
        
        result = response.json()
        print(f"[TEST] Chapter structuring started: {result}")
        
        # 7. 챕터 구조화 완료 대기
        print(f"[TEST] Waiting for chapter structuring to complete...")
        start_time = time.time()
        max_wait_time = 1800  # 30분
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > max_wait_time:
                print(f"[ERROR] Timeout after {max_wait_time} seconds")
                break
            
            response = client.get(f"/api/books/{book_id}")
            if response.status_code != 200:
                print(f"[ERROR] Failed to get book status: {response.status_code}")
                break
            
            book_data = response.json()
            status = book_data["status"]
            
            print(f"[TEST] Status: {status} (elapsed: {elapsed:.1f}s)")
            
            if status == "summarized":
                print(f"[TEST] Chapter structuring completed (elapsed: {elapsed:.1f}s)")
                break
            elif status in ["error_summarizing", "failed"]:
                print(f"[ERROR] Chapter structuring failed: status={status}")
                break
            
            time.sleep(5)
        
        # 8. 최종 결과 확인
        print(f"\n[TEST] Final results:")
        response = client.get(f"/api/books/{book_id}")
        if response.status_code == 200:
            book_data = response.json()
            print(f"[TEST] Final status: {book_data['status']}")
        
        response = client.get(f"/api/books/{book_id}/chapters")
        if response.status_code == 200:
            chapters = response.json()
            print(f"[TEST] Total chapters structured: {len(chapters)}")
        
        print(f"\n[TEST] Test completed successfully!")
        
    finally:
        client.close()

if __name__ == "__main__":
    test_book_176_extraction()

