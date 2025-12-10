"""구조 파일이 있지만 DB에 없는 책 추가 (구조 분석까지 완료 상태)"""
import json
import hashlib
from pathlib import Path
from datetime import datetime
from backend.api.database import SessionLocal
from backend.api.models.book import Book, Chapter, BookStatus

def get_pdf_hash(file_path: Path) -> str:
    """PDF 파일의 해시 계산"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

db = SessionLocal()
try:
    start_time = datetime.now()
    print(f"[INFO] 시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 1. "10년후 이곳은 제2의 판교" 파일 확인
    pdf_file = Path("data/input/10년후 이곳은 제2의 판교.pdf")
    if not pdf_file.exists():
        print(f"[ERROR] PDF 파일 없음: {pdf_file}")
        exit(1)
    
    print(f"[STEP 1] PDF 파일 해시 계산 중...")
    pdf_hash = get_pdf_hash(pdf_file)
    hash_6 = pdf_hash[:6]
    print(f"  - 파일: {pdf_file.name}")
    print(f"  - 해시: {hash_6}\n")
    
    # 2. 이미 DB에 있는지 확인
    print(f"[STEP 2] DB 중복 확인 중...")
    all_books = db.query(Book).all()
    total_books = len(all_books)
    print(f"  - DB 총 책 수: {total_books}권")
    
    check_start_time = datetime.now()
    for idx, book in enumerate(all_books, 1):
        # 진행 상황 표시 (10개마다 또는 마지막)
        if idx % 10 == 0 or idx == total_books:
            elapsed = (datetime.now() - check_start_time).total_seconds()
            avg_time = elapsed / idx
            remaining = avg_time * (total_books - idx)
            print(
                f"  - 진행: {idx}/{total_books} ({idx*100//total_books}%) | "
                f"경과: {int(elapsed)}초 | 예상 남은 시간: {int(remaining)}초"
            )
        
        if book.source_file_path:
            book_path = Path(book.source_file_path)
            if book_path.exists():
                try:
                    book_hash = get_pdf_hash(book_path)
                    book_hash_6 = book_hash[:6]
                    if book_hash_6 == hash_6:
                        print(f"\n  [SKIP] 이미 DB에 존재: Book ID {book.id}, title={book.title}")
                        print(f"\n[INFO] 작업 완료 - DB에 이미 존재하는 책입니다.")
                        exit(0)
                except Exception as e:
                    pass
    print(f"\n  [OK] DB에 없음 - 새로 추가 가능\n")
    
    # 3. 구조 파일 로드
    print(f"[STEP 3] 구조 파일 로드 중...")
    structure_file = Path(f"data/output/structure/{hash_6}_10년후이곳은제2의판교_structure.json")
    if not structure_file.exists():
        # 대체 파일명 시도
        structure_file = Path(f"data/output/structure/{hash_6}_10년후이곳은제2의_structure.json")
    
    if not structure_file.exists():
        print(f"  [ERROR] 구조 파일 없음: {structure_file}")
        print(f"  [INFO] 구조 파일 검색 중...")
        structure_dir = Path("data/output/structure")
        matching_files = list(structure_dir.glob(f"{hash_6}*.json"))
        if matching_files:
            structure_file = matching_files[0]
            print(f"  [INFO] 찾은 구조 파일: {structure_file.name}")
        else:
            print(f"  [ERROR] 해시 {hash_6}에 해당하는 구조 파일 없음")
            exit(1)
    
    with open(structure_file, 'r', encoding='utf-8') as f:
        structure_data = json.load(f)
    
    book_title = structure_data.get("book_title", "10년후이곳은제2의판교")
    structure_info = structure_data.get("structure", {})
    chapters_data = structure_info.get("chapters", [])
    main_start_page = structure_info.get("main_start_page")
    main_end_page = structure_info.get("main_end_page")
    
    print(f"  - 제목: {book_title}")
    print(f"  - 챕터 수: {len(chapters_data)}")
    print(f"  - 본문 페이지: {main_start_page}~{main_end_page}")
    if main_end_page:
        page_count = main_end_page
    else:
        page_count = max([ch.get("end_page", 0) for ch in chapters_data] + [0])
    print(f"  - 추정 페이지 수: {page_count}\n")
    
    # 4. Book 레코드 생성
    print(f"[STEP 4] Book 레코드 생성 중...")
    book = Book(
        title=book_title,
        author=None,
        category=None,  # 나중에 설정 가능
        source_file_path=str(pdf_file.absolute()),
        page_count=page_count,
        status=BookStatus.PARSED,  # 파싱 완료 상태
        structure_data={
            "main_start_page": main_start_page,
            "main_end_page": main_end_page,
            "chapters": chapters_data,
            "notes_pages": structure_info.get("notes_pages", []),
            "start_pages": structure_info.get("start_pages", []),
            "end_pages": structure_info.get("end_pages", []),
        }
    )
    db.add(book)
    db.flush()  # ID 할당을 위해 flush
    book_id = book.id
    print(f"  [OK] Book ID {book_id} 생성 완료\n")
    
    # 5. Chapter 레코드 생성
    print(f"[STEP 5] Chapter 레코드 생성 중... (총 {len(chapters_data)}개)")
    for idx, ch_data in enumerate(chapters_data):
        chapter = Chapter(
            book_id=book_id,
            title=ch_data.get("title", ""),
            order_index=ch_data.get("order_index", idx),
            start_page=ch_data.get("start_page"),
            end_page=ch_data.get("end_page"),
            section_type="main",
        )
        db.add(chapter)
        if (idx + 1) % 5 == 0 or idx + 1 == len(chapters_data):
            print(f"  - 진행: {idx + 1}/{len(chapters_data)} 챕터 생성 완료")
    print(f"  [OK] {len(chapters_data)}개 챕터 생성 완료\n")
    
    # 6. 상태를 STRUCTURED로 변경
    print(f"[STEP 6] 상태 업데이트 중...")
    book.status = BookStatus.STRUCTURED
    db.commit()
    print(f"  [OK] 상태: {book.status}\n")
    
    # 7. 최종 확인
    total_time = (datetime.now() - start_time).total_seconds()
    print(f"[SUMMARY]")
    print(f"  - Book ID: {book_id}")
    print(f"  - 제목: {book.title}")
    print(f"  - 챕터 수: {len(chapters_data)}")
    print(f"  - 페이지 수: {book.page_count}")
    print(f"  - 상태: {book.status}")
    print(f"  - 총 소요 시간: {int(total_time)}초")
    print(f"\n[OK] 작업 완료!")
    
finally:
    db.close()

