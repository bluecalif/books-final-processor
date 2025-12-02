"""
Book 176의 기존 PageSummary 및 ChapterSummary 삭제
테스트 재시작을 위한 초기화 스크립트
"""
from backend.api.database import SessionLocal
from backend.api.models.book import Book, BookStatus, PageSummary, ChapterSummary

db = SessionLocal()

book_id = 176

print(f"\n{'='*80}")
print(f"Book {book_id} 초기화 시작")
print(f"{'='*80}")

# 1. 현재 상태 확인
book = db.query(Book).filter(Book.id == book_id).first()
if not book:
    print(f"[ERROR] Book {book_id} not found")
    db.close()
    exit(1)

print(f"\n현재 상태:")
print(f"  제목: {book.title}")
print(f"  상태: {book.status}")

# 2. PageSummary 개수 확인
page_count_before = db.query(PageSummary).filter(PageSummary.book_id == book_id).count()
print(f"  PageSummaries: {page_count_before}개")

# 3. ChapterSummary 개수 확인
chapter_count_before = db.query(ChapterSummary).filter(ChapterSummary.book_id == book_id).count()
print(f"  ChapterSummaries: {chapter_count_before}개")

# 4. PageSummary 삭제
if page_count_before > 0:
    print(f"\n[INFO] Deleting {page_count_before} PageSummaries...")
    db.query(PageSummary).filter(PageSummary.book_id == book_id).delete()
    db.commit()
    print(f"[INFO] PageSummaries deleted")

# 5. ChapterSummary 삭제
if chapter_count_before > 0:
    print(f"\n[INFO] Deleting {chapter_count_before} ChapterSummaries...")
    db.query(ChapterSummary).filter(ChapterSummary.book_id == book_id).delete()
    db.commit()
    print(f"[INFO] ChapterSummaries deleted")

# 6. Book 상태를 structured로 변경
if book.status != BookStatus.STRUCTURED:
    print(f"\n[INFO] Resetting book status to 'structured'...")
    book.status = BookStatus.STRUCTURED
    db.commit()
    print(f"[INFO] Book status updated: {book.status}")

# 7. 최종 확인
page_count_after = db.query(PageSummary).filter(PageSummary.book_id == book_id).count()
chapter_count_after = db.query(ChapterSummary).filter(ChapterSummary.book_id == book_id).count()

print(f"\n{'='*80}")
print(f"초기화 완료")
print(f"{'='*80}")
print(f"  PageSummaries: {page_count_before} → {page_count_after}")
print(f"  ChapterSummaries: {chapter_count_before} → {chapter_count_after}")
print(f"  Book status: {book.status}")
print(f"\n[INFO] Book {book_id} is ready for testing")

db.close()

