"""전체 프로젝트 도서 분석 및 상태 리포트 생성"""
import json
import hashlib
from pathlib import Path
from datetime import datetime
from backend.api.database import SessionLocal
from backend.api.models.book import Book, Chapter, PageSummary, ChapterSummary
from backend.config.settings import settings

def get_pdf_hash(file_path: Path) -> str:
    """PDF 파일의 해시 계산"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def load_structure_file(structure_path: Path) -> dict:
    """구조 파일 로드"""
    try:
        with open(structure_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARNING] 구조 파일 로드 실패: {structure_path}: {e}")
        return {}

def count_chapters(structure_data: dict) -> int:
    """구조 데이터에서 챕터 수 계산"""
    if not structure_data:
        return 0
    
    # 형식 1: main.chapters
    if "main" in structure_data and "chapters" in structure_data["main"]:
        return len(structure_data["main"]["chapters"])
    
    # 형식 2: chapters
    if "chapters" in structure_data:
        return len(structure_data["chapters"])
    
    return 0

db = SessionLocal()
try:
    start_time = datetime.now()
    print(f"[INFO] 시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 1. PDF 파일 목록 수집
    print("[STEP 1] PDF 파일 해시 계산 중...")
    input_dir = Path("data/input")
    pdf_files_list = list(input_dir.glob("*.pdf"))
    pdf_files_list = [f for f in pdf_files_list if f.parent.name != "처리완료"]
    
    total_pdf = len(pdf_files_list)
    print(f"  - 총 {total_pdf}개 PDF 파일 처리 예정")
    
    pdf_files = {}
    for idx, pdf_file in enumerate(pdf_files_list, 1):
        if idx % 10 == 0 or idx == total_pdf:
            elapsed = (datetime.now() - start_time).total_seconds()
            avg_time = elapsed / idx
            remaining = avg_time * (total_pdf - idx)
            print(
                f"  - 진행: {idx}/{total_pdf} ({idx*100//total_pdf}%) | "
                f"경과: {int(elapsed)}초 | 예상 남은 시간: {int(remaining)}초"
            )
        
        pdf_hash = get_pdf_hash(pdf_file)
        pdf_files[pdf_hash] = {
            "file_path": pdf_file,
            "file_name": pdf_file.name,
            "hash": pdf_hash,
            "hash_6": pdf_hash[:6]
        }
    
    print(f"\n[OK] PDF 파일 해시 계산 완료: {len(pdf_files)}개\n")
    
    # 2. 구조 파일 수집 및 매칭
    print("[STEP 2] 구조 파일 로드 중...")
    structure_dir = Path("data/output/structure")
    structure_files_list = list(structure_dir.glob("*.json"))
    total_struct = len(structure_files_list)
    print(f"  - 총 {total_struct}개 구조 파일 처리 예정")
    
    structure_files = {}
    for idx, struct_file in enumerate(structure_files_list, 1):
        if idx % 20 == 0 or idx == total_struct:
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"  - 진행: {idx}/{total_struct} ({idx*100//total_struct}%) | 경과: {int(elapsed)}초")
        
        hash_6 = struct_file.name.split("_")[0]
        structure_data = load_structure_file(struct_file)
        chapter_count = count_chapters(structure_data)
        
        structure_files[hash_6] = {
            "file_path": struct_file,
            "file_name": struct_file.name,
            "hash_6": hash_6,
            "structure_data": structure_data,
            "chapter_count": chapter_count
        }
    
    print(f"\n[OK] 구조 파일 로드 완료: {len(structure_files)}개\n")
    
    # 3. PDF와 구조 파일 매칭
    books_info = {}
    for pdf_hash, pdf_info in pdf_files.items():
        hash_6 = pdf_info["hash_6"]
        struct_info = structure_files.get(hash_6)
        
        book_key = pdf_info["file_name"]
        books_info[book_key] = {
            "pdf_file": pdf_info["file_name"],
            "pdf_hash": pdf_hash,
            "hash_6": hash_6,
            "structure_file": struct_info["file_name"] if struct_info else None,
            "chapter_count": struct_info["chapter_count"] if struct_info else 0,
            "structure_data": struct_info["structure_data"] if struct_info else {}
        }
    
    # 4. DB와 매칭
    print("[STEP 3] DB 책 해시 계산 및 매칭 중...")
    all_db_books = db.query(Book).all()
    total_db = len(all_db_books)
    print(f"  - DB 총 책 수: {total_db}권")
    
    db_books_by_hash = {}
    db_books_by_path = {}
    
    hash_start_time = datetime.now()
    for idx, book in enumerate(all_db_books, 1):
        if idx % 10 == 0 or idx == total_db:
            elapsed = (datetime.now() - hash_start_time).total_seconds()
            avg_time = elapsed / idx if idx > 0 else 0
            remaining = avg_time * (total_db - idx) if idx > 0 else 0
            print(
                f"  - 진행: {idx}/{total_db} ({idx*100//total_db}%) | "
                f"경과: {int(elapsed)}초 | 예상 남은 시간: {int(remaining)}초"
            )
        
        if book.source_file_path:
            # PDF 해시 계산
            pdf_path = Path(book.source_file_path)
            if pdf_path.exists():
                try:
                    pdf_hash = get_pdf_hash(pdf_path)
                    hash_6 = pdf_hash[:6]
                    db_books_by_hash[hash_6] = book
                except:
                    pass
            # 경로로도 매칭
            db_books_by_path[pdf_path.name] = book
    
    print(f"\n[OK] DB 매칭 완료: {len(db_books_by_hash)}개\n")
    
    # 5. 북 서머리 파일 확인
    book_summary_dir = settings.output_dir / "book_summaries"
    book_summary_files = {}
    if book_summary_dir.exists():
        for summary_file in book_summary_dir.glob("*.json"):
            book_summary_files[summary_file.name] = summary_file
    
    # 6. 각 도서별 상세 정보 수집
    print("[STEP 4] 도서별 상세 정보 수집 중...")
    final_books = []
    total_books_info = len(books_info)
    
    for idx, (book_key, book_info) in enumerate(books_info.items(), 1):
        if idx % 20 == 0 or idx == total_books_info:
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"  - 진행: {idx}/{total_books_info} ({idx*100//total_books_info}%) | 경과: {int(elapsed)}초")
        # DB 매칭
        db_book = db_books_by_hash.get(book_info["hash_6"]) or db_books_by_path.get(book_key)
        
        # 북 서머리 파일 찾기
        summary_file = None
        if db_book:
            # Book ID로 찾기
            for sf_name, sf_path in book_summary_files.items():
                if str(db_book.id) in sf_name:
                    summary_file = sf_name
                    break
            # 제목으로 찾기
            if not summary_file and db_book.title:
                title_variants = [
                    db_book.title.replace(" ", "_"),
                    db_book.title.replace(" ", ""),
                    db_book.title
                ]
                for variant in title_variants:
                    for sf_name in book_summary_files.keys():
                        if variant in sf_name or variant.replace("_", "") in sf_name.replace("_", ""):
                            summary_file = sf_name
                            break
                    if summary_file:
                        break
        
        # DB 정보 수집
        book_id = db_book.id if db_book else None
        title = db_book.title if db_book else book_key.replace(".pdf", "")
        category = db_book.category if db_book else "미분류"
        status = str(db_book.status) if db_book else "없음"
        page_count = db_book.page_count if db_book else 0
        
        # DB에서 챕터/요약 수 조회
        chapter_count_db = 0
        page_summary_count = 0
        chapter_summary_count = 0
        if db_book:
            chapter_count_db = db.query(Chapter).filter(Chapter.book_id == db_book.id).count()
            page_summary_count = db.query(PageSummary).filter(PageSummary.book_id == db_book.id).count()
            chapter_summary_count = db.query(ChapterSummary).filter(ChapterSummary.book_id == db_book.id).count()
        
        # 챕터 수는 구조 파일 기준 우선
        final_chapter_count = book_info["chapter_count"] or chapter_count_db
        
        # 처리 상태 결정
        completion_status = "미완료"
        last_step = "STEP 0: 초기 상태"
        
        # 노이즈는 처리 제외
        if (title and "노이즈" in title) or "노이즈" in book_key:
            completion_status = "🚫 처리 제외 (이중구조 문제)"
            last_step = "STEP 4: 구조 확정 완료 (처리 제외)"
        elif summary_file:
            completion_status = "✅ 완료"
            last_step = "STEP 8: 최종 결과 조회 검증 완료"
        elif chapter_summary_count > 0 and page_summary_count > 0:
            completion_status = "⚠️ 북 서머리 미생성"
            last_step = "STEP 6: 챕터 구조화 완료"
        elif page_summary_count > 0:
            completion_status = "⚠️ 챕터 구조화 미완료"
            last_step = "STEP 5: 페이지 엔티티 추출 완료"
        elif final_chapter_count > 0 or chapter_count_db > 0:
            completion_status = "⚠️ 페이지 추출 미완료"
            last_step = "STEP 4: 구조 확정 완료"
        elif status == "structured":
            completion_status = "⚠️ 페이지 추출 미완료"
            last_step = "STEP 4: 구조 확정 완료"
        elif status == "parsed":
            completion_status = "⚠️ 구조 분석 미완료"
            last_step = "STEP 2: PDF 파싱 완료"
        elif status == "uploaded":
            completion_status = "⚠️ 파싱 미완료"
            last_step = "STEP 1: PDF 업로드 완료"
        elif status in ["error_parsing", "error_structuring", "error_summarizing", "failed"]:
            completion_status = "❌ 에러"
            last_step = f"에러: {status}"
        
        final_books.append({
            "book_id": book_id,
            "title": title,
            "pdf_file": book_key,
            "category": category,
            "status": status,
            "chapter_count": final_chapter_count,
            "page_count": page_count,
            "page_summary_count": page_summary_count,
            "chapter_summary_count": chapter_summary_count,
            "book_summary_file": summary_file,
            "last_completed_step": last_step,
            "completion_status": completion_status,
            "hash_6": book_info["hash_6"]
        })
    
    print(f"\n[OK] 도서 정보 수집 완료: {len(final_books)}권\n")
    
    # Book ID 순으로 정렬 (None은 마지막)
    final_books.sort(key=lambda x: (x["book_id"] is None, x["book_id"] or 0))
    
    # 7. 챕터 수 기준 분류
    print("[STEP 5] 도서 분류 중...")
    books_6plus = [b for b in final_books if b["chapter_count"] >= 6 and (not b["title"] or "노이즈" not in b["title"]) and "노이즈" not in b["pdf_file"]]
    books_under_6 = [b for b in final_books if b["chapter_count"] < 6]
    books_excluded = [b for b in final_books if (b["title"] and "노이즈" in b["title"]) or "노이즈" in b["pdf_file"]]
    
    print(f"  - 챕터 6개 이상 (처리 대상): {len(books_6plus)}권")
    print(f"  - 챕터 6개 미만 (재분석 후 처리): {len(books_under_6)}권")
    print(f"  - 처리 제외 (노이즈): {len(books_excluded)}권\n")
    
    # 8. 마크다운 파일 생성
    print("[STEP 6] 마크다운 파일 생성 중...")
    md_content = "# 전체 도서 처리 현황\n\n"
    md_content += f"**생성 일시**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    md_content += f"**총 도서 수**: {len(final_books)}권\n\n"
    
    # 통계
    completed_6plus = len([b for b in books_6plus if "✅ 완료" in b["completion_status"]])
    warning_6plus = len([b for b in books_6plus if "⚠️" in b["completion_status"]])
    error_6plus = len([b for b in books_6plus if "❌" in b["completion_status"]])
    
    md_content += "## 처리 현황 요약\n\n"
    md_content += f"### 챕터 6개 이상 도서 (처리 대상)\n"
    md_content += f"- 총: {len(books_6plus)}권\n"
    md_content += f"- ✅ 완료: {completed_6plus}권 ({completed_6plus*100//len(books_6plus) if len(books_6plus) > 0 else 0}%)\n"
    md_content += f"- ⚠️ 부분 완료: {warning_6plus}권 ({warning_6plus*100//len(books_6plus) if len(books_6plus) > 0 else 0}%)\n"
    md_content += f"- ❌ 에러: {error_6plus}권\n\n"
    
    md_content += f"### 챕터 6개 미만 도서\n"
    md_content += f"- 총: {len(books_under_6)}권\n"
    md_content += f"- 상태: 🚧 챕터 구조 재분석 후 처리 예정\n\n"
    
    md_content += f"### 처리 제외 도서\n"
    md_content += f"- 총: {len(books_excluded)}권\n"
    md_content += f"- 상태: 🚫 챕터 구조 재분석 후 처리 예정 (이중구조 문제)\n\n"
    
    md_content += "---\n\n"
    
    # 챕터 6개 이상 도서 상세
    md_content += "## 챕터 6개 이상 도서 상세 현황\n\n"
    md_content += "| Book ID | 제목 | 분야 | 상태 | 페이지 | 챕터 | 페이지<br>요약 | 챕터<br>요약 | 북<br>서머리 | 마지막 완료 단계 | 처리 상태 |\n"
    md_content += "|---------|------|------|------|--------|------|--------------|------------|----------|------------------|------------|\n"
    
    for book in books_6plus:
        title = (book["title"][:30] + ".." if book["title"] and len(book["title"]) > 32 else book["title"]) or "-"
        category = (book["category"][:15] + "..") if len(book["category"]) > 17 else book["category"]
        status = str(book["status"])[:18] + ".." if len(str(book["status"])) > 20 else str(book["status"])
        book_summary = "✅" if book["book_summary_file"] else "❌"
        last_step = book["last_completed_step"][:30] + ".." if len(book["last_completed_step"]) > 32 else book["last_completed_step"]
        completion = book["completion_status"]
        book_id_str = str(book["book_id"]) if book["book_id"] else "-"
        
        md_content += f"| {book_id_str} | {title} | {category} | {status} | {book['page_count']} | {book['chapter_count']} | {book['page_summary_count']} | {book['chapter_summary_count']} | {book_summary} | {last_step} | {completion} |\n"
    
    md_content += "\n---\n\n"
    
    # 완료 상태별 분류
    md_content += "## 완료 상태별 분류\n\n"
    
    completed_books = [b for b in books_6plus if "✅ 완료" in b["completion_status"]]
    if completed_books:
        md_content += f"### ✅ 완료된 책 ({len(completed_books)}권)\n\n"
        md_content += "| Book ID | 제목 | 북 서머리 파일 |\n"
        md_content += "|---------|------|----------------|\n"
        for book in completed_books:
            title = (book["title"][:40] + ".." if book["title"] and len(book["title"]) > 42 else book["title"]) or "-"
            summary_file = book["book_summary_file"] or "없음"
            book_id_str = str(book["book_id"]) if book["book_id"] else "-"
            md_content += f"| {book_id_str} | {title} | {summary_file} |\n"
        md_content += "\n"
    
    warning_books = [b for b in books_6plus if "⚠️" in b["completion_status"]]
    if warning_books:
        md_content += f"### ⚠️ 부분 완료된 책 ({len(warning_books)}권)\n\n"
        md_content += "| Book ID | 제목 | 마지막 완료 단계 | 누락 사항 |\n"
        md_content += "|---------|------|------------------|----------|\n"
        for book in warning_books:
            title = (book["title"][:40] + ".." if book["title"] and len(book["title"]) > 42 else book["title"]) or "-"
            last_step = book["last_completed_step"][:35] + ".." if len(book["last_completed_step"]) > 37 else book["last_completed_step"]
            missing = ""
            if "북 서머리 미생성" in book["completion_status"]:
                missing = "북 서머리 생성"
            elif "챕터 구조화 미완료" in book["completion_status"]:
                missing = "챕터 구조화"
            elif "페이지 추출 미완료" in book["completion_status"]:
                missing = "페이지 엔티티 추출"
            elif "구조 분석 미완료" in book["completion_status"]:
                missing = "구조 분석"
            elif "파싱 미완료" in book["completion_status"]:
                missing = "PDF 파싱"
            book_id_str = str(book["book_id"]) if book["book_id"] else "-"
            md_content += f"| {book_id_str} | {title} | {last_step} | {missing} |\n"
        md_content += "\n"
    
    error_books = [b for b in books_6plus if "❌" in b["completion_status"]]
    if error_books:
        md_content += f"### ❌ 에러 발생 책 ({len(error_books)}권)\n\n"
        md_content += "| Book ID | 제목 | 상태 | 마지막 완료 단계 |\n"
        md_content += "|---------|------|------|------------------|\n"
        for book in error_books:
            title = (book["title"][:40] + ".." if book["title"] and len(book["title"]) > 42 else book["title"]) or "-"
            status = str(book["status"])[:30] + ".." if len(str(book["status"])) > 32 else str(book["status"])
            last_step = book["last_completed_step"][:35] + ".." if len(book["last_completed_step"]) > 37 else book["last_completed_step"]
            book_id_str = str(book["book_id"]) if book["book_id"] else "-"
            md_content += f"| {book_id_str} | {title} | {status} | {last_step} |\n"
        md_content += "\n"
    
    # 챕터 6개 미만 도서
    if books_under_6:
        md_content += f"### 🚧 챕터 6개 미만 도서 ({len(books_under_6)}권) - 챕터 구조 재분석 후 처리 예정\n\n"
        md_content += "| Book ID | 제목 | 분야 | 챕터 수 | 상태 |\n"
        md_content += "|---------|------|------|---------|------|\n"
        for book in sorted(books_under_6, key=lambda x: x["chapter_count"], reverse=True):
            title = (book["title"][:40] + ".." if book["title"] and len(book["title"]) > 42 else book["title"]) or "-"
            category = book.get("category") or "미분류"
            category = (category[:20] + "..") if len(category) > 22 else category
            status = str(book["status"])[:20] + ".." if len(str(book["status"])) > 22 else str(book["status"])
            book_id_str = str(book["book_id"]) if book["book_id"] else "-"
            md_content += f"| {book_id_str} | {title} | {category} | {book['chapter_count']} | {status} |\n"
        md_content += "\n"
    
    # 처리 제외 도서
    if books_excluded:
        md_content += f"### 🚫 처리 제외 도서 ({len(books_excluded)}권) - 챕터 구조 재분석 후 처리 예정\n\n"
        md_content += "| Book ID | 제목 | 챕터 수 | 제외 사유 |\n"
        md_content += "|---------|------|---------|----------|\n"
        for book in books_excluded:
            title = (book["title"][:40] + ".." if book["title"] and len(book["title"]) > 42 else book["title"]) or "-"
            reason = "이중구조 문제 (1부 아래 하부구조 겹침)"
            book_id_str = str(book["book_id"]) if book["book_id"] else "-"
            md_content += f"| {book_id_str} | {title} | {book['chapter_count']} | {reason} |\n"
        md_content += "\n"
    
    # 파일 저장
    output_file = Path("docs/books_6plus_chapters_status.md")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(md_content, encoding="utf-8")
    
    total_time = (datetime.now() - start_time).total_seconds()
    print(f"\n[OK] 마크다운 파일 생성 완료: {output_file}")
    print(f"\n[SUMMARY]")
    print(f"  - 총 소요 시간: {int(total_time)}초")
    print(f"  - 전체 도서: {len(final_books)}권")
    print(f"  - 챕터 6개 이상 (처리 대상): {len(books_6plus)}권")
    print(f"    - 완료: {completed_6plus}권")
    print(f"    - 부분 완료: {warning_6plus}권")
    print(f"    - 에러: {error_6plus}권")
    print(f"  - 챕터 6개 미만: {len(books_under_6)}권")
    print(f"  - 처리 제외: {len(books_excluded)}권")
    
finally:
    db.close()

