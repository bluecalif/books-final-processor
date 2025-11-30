"""
모든 구조 파일 및 DB 조사: 챕터 수가 0, 1, 2개인 책 찾기
"""
import sys
import json
from pathlib import Path
from collections import defaultdict

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.api.database import SessionLocal, init_db
from backend.api.models.book import Book, Chapter

structure_dir = Path("data/output/structure")

# DB 초기화
init_db()
db = SessionLocal()

# 구조 파일 찾기
structure_files = list(structure_dir.glob("*_structure.json"))

print("=" * 80)
print("구조 파일 및 DB 챕터 수 조사")
print("=" * 80)
print(f"전체 구조 파일: {len(structure_files)}개\n")

# 챕터 수별로 분류
chapters_by_count = defaultdict(list)

# DB에서 모든 책 조회
all_books = db.query(Book).all()
book_dict = {book.id: book for book in all_books}

for structure_file in structure_files:
    try:
        with open(structure_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        book_id = data.get("book_id")
        book_title = data.get("book_title", structure_file.stem)
        
        # DB에서 챕터 개수 확인 (우선)
        db_chapter_count = 0
        if book_id:
            db_chapters = db.query(Chapter).filter(Chapter.book_id == book_id).all()
            db_chapter_count = len(db_chapters)
        
        # 구조 파일에서 챕터 추출
        structure = data.get("structure", {})
        main = structure.get("main", {})
        file_chapters = main.get("chapters", [])
        
        # structure_data 형식도 확인
        if not file_chapters:
            structure_data = data.get("structure_data", {})
            if structure_data:
                file_chapters = structure_data.get("chapters", [])
        
        # DB 챕터가 있으면 DB 기준, 없으면 파일 기준
        chapter_count = db_chapter_count if db_chapter_count > 0 else len(file_chapters)
        chapters = db_chapters if db_chapter_count > 0 else file_chapters
        
        chapters_by_count[chapter_count].append({
            "file": structure_file.name,
            "book_id": book_id,
            "title": book_title,
            "chapters": chapters,
            "db_chapter_count": db_chapter_count,
            "file_chapter_count": len(file_chapters),
        })
        
    except Exception as e:
        print(f"[ERROR] {structure_file.name}: {e}")

db.close()

# 결과 출력
print("[챕터 수별 분류]")
for count in sorted(chapters_by_count.keys()):
    books = chapters_by_count[count]
    print(f"\n챕터 {count}개: {len(books)}권")
    
    if 1 <= count <= 5:  # 1, 2, 3, 4, 5개만 상세 출력
        for book in books:
            print(f"  - ID {book['book_id']}: {book['title']}")
            if book['chapters']:
                for idx, ch in enumerate(book['chapters'], 1):
                    # DB Chapter 객체인지 딕셔너리인지 확인
                    if hasattr(ch, 'title'):
                        # SQLAlchemy 모델 객체
                        print(f"      {idx}. {ch.title} (페이지 {ch.start_page}-{ch.end_page})")
                    else:
                        # 딕셔너리
                        print(f"      {idx}. {ch.get('title', 'N/A')} (페이지 {ch.get('start_page', 'N/A')}-{ch.get('end_page', 'N/A')})")

print("\n" + "=" * 80)
print("[요약]")
print(f"  챕터 0개: {len(chapters_by_count.get(0, []))}권")
print(f"  챕터 1개: {len(chapters_by_count.get(1, []))}권")
print(f"  챕터 2개: {len(chapters_by_count.get(2, []))}권")
print(f"  챕터 3개: {len(chapters_by_count.get(3, []))}권")
print(f"  챕터 4개: {len(chapters_by_count.get(4, []))}권")
print(f"  챕터 5개: {len(chapters_by_count.get(5, []))}권")
print(f"  챕터 6개 이상: {sum(len(chapters_by_count.get(i, [])) for i in range(6, 100))}권")
print("=" * 80)

