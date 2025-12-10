"""중복된 책 DB 레코드 삭제 (input 기준 87권으로 정리) - 최적화 버전"""

import json
import hashlib
from pathlib import Path
from datetime import datetime
from backend.api.database import SessionLocal
from backend.api.models.book import Book, Chapter, PageSummary, ChapterSummary


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
    print(f"[INFO] 시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. input 폴더의 PDF 파일 해시 계산 (한 번만)
    print("\n[STEP 1] input 폴더 PDF 파일 해시 계산 중...")
    input_dir = Path("data/input")
    pdf_hash_map = {}  # hash_6 -> pdf_info

    pdf_files_list = list(input_dir.glob("*.pdf"))
    pdf_files_list = [f for f in pdf_files_list if f.parent.name != "처리완료"]

    total_pdf = len(pdf_files_list)
    print(f"  - 총 {total_pdf}개 PDF 파일 처리 예정")

    for idx, pdf_file in enumerate(pdf_files_list, 1):
        if idx % 10 == 0 or idx == total_pdf:
            elapsed = (datetime.now() - start_time).total_seconds()
            avg_time = elapsed / idx
            remaining = avg_time * (total_pdf - idx)
            print(
                f"  - 진행: {idx}/{total_pdf} ({idx*100//total_pdf}%) | "
                f"경과: {int(elapsed)}초 | 예상 남은 시간: {int(remaining)}초"
            )

        try:
            pdf_hash = get_pdf_hash(pdf_file)
            hash_6 = pdf_hash[:6]
            pdf_hash_map[hash_6] = {
                "file_path": pdf_file,
                "file_name": pdf_file.name,
                "hash": pdf_hash,
                "hash_6": hash_6,
            }
        except Exception as e:
            print(f"  [WARNING] {pdf_file.name} 해시 계산 실패: {e}")

    print(f"[OK] PDF 해시 계산 완료: {len(pdf_hash_map)}개")

    # 2. DB의 모든 책을 source_file_path 기준으로 그룹화 (해시 계산 최소화)
    print("\n[STEP 2] DB 책 분석 중...")
    all_books = db.query(Book).all()
    print(f"  - DB 총 책 수: {len(all_books)}권")

    # source_file_path로 빠르게 그룹화
    books_by_path = {}
    books_hash_cache = {}  # path -> hash_6 캐시

    for book in all_books:
        if book.source_file_path:
            pdf_path = Path(book.source_file_path)
            if pdf_path.exists():
                path_str = str(pdf_path)
                if path_str not in books_hash_cache:
                    try:
                        pdf_hash = get_pdf_hash(pdf_path)
                        hash_6 = pdf_hash[:6]
                        books_hash_cache[path_str] = hash_6
                    except:
                        books_hash_cache[path_str] = None

                hash_6 = books_hash_cache[path_str]
                if hash_6:
                    if hash_6 not in books_by_path:
                        books_by_path[hash_6] = []
                    books_by_path[hash_6].append(book)

    print(f"  - 해시 계산 완료: {len(books_hash_cache)}개")
    print(f"  - 그룹 수: {len(books_by_path)}개")

    # 3. 중복 제거: 각 hash_6 그룹에서 가장 좋은 책 하나만 유지
    print("\n[STEP 3] 중복 제거 분석 중...")
    books_to_keep = []
    books_to_delete = []

    status_order = {
        "summarized": 5,
        "page_summarized": 4,
        "structured": 3,
        "parsed": 2,
        "uploaded": 1,
        "error_parsing": 0,
        "error_structuring": 0,
        "error_summarizing": 0,
        "failed": 0,
    }

    def get_sort_key(book):
        status = str(book.status).replace("BookStatus.", "").lower()
        return (
            status_order.get(status, 0),
            -book.id,
        )  # 상태 높은 것 우선, 같으면 ID 작은 것 우선

    for hash_6, books in books_by_path.items():
        if len(books) == 1:
            # 중복 없음, 그대로 유지
            books_to_keep.append(books[0])
        else:
            # 중복 있음, 가장 좋은 것 하나만 유지
            sorted_books = sorted(books, key=get_sort_key, reverse=True)
            keep_book = sorted_books[0]
            delete_books = sorted_books[1:]

            books_to_keep.append(keep_book)
            books_to_delete.extend(delete_books)

            print(f"\n  [중복 그룹] hash_6: {hash_6} (총 {len(books)}개)")
            print(
                f"    [유지] Book ID {keep_book.id}: {keep_book.title}, status={keep_book.status}"
            )
            for delete_book in delete_books:
                print(
                    f"    [삭제] Book ID {delete_book.id}: {delete_book.title}, status={delete_book.status}"
                )

    print(f"\n[OK] 중복 분석 완료")
    print(f"  - 유지할 책: {len(books_to_keep)}권")
    print(f"  - 삭제할 책: {len(books_to_delete)}권")

    # 4. 삭제 확인 및 실행
    if books_to_delete:
        print("\n[STEP 4] 중복 책 삭제 중...")

        deleted_count = 0
        total_delete = len(books_to_delete)

        for idx, book in enumerate(books_to_delete, 1):
            # 진행 상황 매번 출력
            elapsed = (datetime.now() - start_time).total_seconds()
            avg_time = elapsed / idx if idx > 0 else 0
            remaining = avg_time * (total_delete - idx) if idx > 0 else 0
            print(
                f"  [{idx}/{total_delete}] Book ID {book.id} 삭제 중... "
                f"(경과: {int(elapsed)}초, 예상 남은 시간: {int(remaining)}초)"
            )

            try:
                # 관련 데이터는 CASCADE로 자동 삭제됨
                # SQLAlchemy가 각 관련 레코드를 개별 삭제하므로 시간이 오래 걸릴 수 있음
                db.delete(book)
                db.flush()  # 즉시 반영 (진행 상황 확인용)
                deleted_count += 1
                print(f"    [OK] Book ID {book.id} 삭제 완료")
            except Exception as e:
                print(f"    [ERROR] Book ID {book.id} 삭제 실패: {e}")
                db.rollback()

        # 모든 삭제 완료 후 한 번에 커밋
        db.commit()
        print(f"\n[OK] {deleted_count}건의 중복 책 삭제 완료")
    else:
        print("\n[INFO] 삭제할 중복 책이 없습니다.")

    # 5. 최종 확인
    print("\n[STEP 5] 최종 확인 중...")
    remaining_books = db.query(Book).count()
    total_time = (datetime.now() - start_time).total_seconds()

    print(f"\n[SUMMARY]")
    print(f"  - 남은 책 수: {remaining_books}권")
    print(f"  - input 폴더 책 수: {len(pdf_hash_map)}권")
    print(f"  - 총 소요 시간: {int(total_time)}초")

    if remaining_books == len(pdf_hash_map):
        print("[OK] 책 수가 input 폴더와 일치합니다!")
    else:
        print(
            f"[WARNING] 책 수가 일치하지 않습니다. (차이: {remaining_books - len(pdf_hash_map)}권)"
        )
        print("\n[INFO] input 폴더에 있는데 DB에 없는 책 확인 중...")
        # input 폴더에 있는데 DB에 없는 책 확인
        db_hash_set = set(books_by_path.keys())
        input_hash_set = set(pdf_hash_map.keys())
        missing_in_db = input_hash_set - db_hash_set
        if missing_in_db:
            print(f"  - DB에 없는 책: {len(missing_in_db)}권")
            for hash_6 in list(missing_in_db)[:5]:
                print(f"    - {pdf_hash_map[hash_6]['file_name']}")

finally:
    db.close()
