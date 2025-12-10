"""책별 상세 리스트 생성 (메타데이터 및 처리 상태 포함)"""

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
        return {}


def count_chapters(structure_data: dict) -> int:
    """구조 데이터에서 챕터 수 계산"""
    if not structure_data:
        return 0
    
    if "main" in structure_data and "chapters" in structure_data["main"]:
        return len(structure_data["main"]["chapters"])
    
    if "chapters" in structure_data:
        return len(structure_data["chapters"])
    
    return 0


def get_completion_status(db_book, chapter_count_db, page_summary_count, chapter_summary_count, summary_file, book_key):
    """처리 상태 결정"""
    title = db_book.title if db_book else book_key.replace(".pdf", "")
    
    # 노이즈는 처리 제외
    if (title and "노이즈" in title) or "노이즈" in book_key:
        return {
            "status": "처리 제외",
            "status_code": "EXCLUDED",
            "reason": "이중구조 문제 (1부 아래 하부구조 겹침)",
            "last_completed_step": "STEP 4: 구조 확정 완료 (처리 제외)",
            "can_process": False,
            "missing_steps": []
        }
    
    # 완료 상태
    if summary_file:
        return {
            "status": "완료",
            "status_code": "COMPLETED",
            "reason": "전체 파이프라인 완료",
            "last_completed_step": "STEP 8: 최종 결과 조회 검증 완료",
            "can_process": False,
            "missing_steps": []
        }
    
    # 부분 완료 상태
    missing_steps = []
    
    if chapter_summary_count > 0 and page_summary_count > 0:
        return {
            "status": "부분 완료",
            "status_code": "PARTIAL",
            "reason": "북 서머리 미생성",
            "last_completed_step": "STEP 6: 챕터 구조화 완료",
            "can_process": True,
            "missing_steps": ["STEP 7: 북 서머리 생성"]
        }
    
    if page_summary_count > 0:
        return {
            "status": "부분 완료",
            "status_code": "PARTIAL",
            "reason": "챕터 구조화 미완료",
            "last_completed_step": "STEP 5: 페이지 엔티티 추출 완료",
            "can_process": True,
            "missing_steps": ["STEP 6: 챕터 구조화", "STEP 7: 북 서머리 생성"]
        }
    
    db_status = str(db_book.status) if db_book else "없음"
    if db_status in ["structured", "BookStatus.STRUCTURED"]:
        return {
            "status": "부분 완료",
            "status_code": "PARTIAL",
            "reason": "페이지 추출 미완료",
            "last_completed_step": "STEP 4: 구조 확정 완료",
            "can_process": True,
            "missing_steps": ["STEP 5: 페이지 엔티티 추출", "STEP 6: 챕터 구조화", "STEP 7: 북 서머리 생성"]
        }
    
    if db_status in ["parsed", "BookStatus.PARSED"]:
        return {
            "status": "부분 완료",
            "status_code": "PARTIAL",
            "reason": "구조 분석 미완료",
            "last_completed_step": "STEP 2: PDF 파싱 완료",
            "can_process": True,
            "missing_steps": ["STEP 3: 구조 후보 생성", "STEP 4: 구조 확정", "STEP 5: 페이지 엔티티 추출", "STEP 6: 챕터 구조화", "STEP 7: 북 서머리 생성"]
        }
    
    if db_status in ["uploaded", "BookStatus.UPLOADED"]:
        return {
            "status": "부분 완료",
            "status_code": "PARTIAL",
            "reason": "파싱 미완료",
            "last_completed_step": "STEP 1: PDF 업로드 완료",
            "can_process": True,
            "missing_steps": ["STEP 2: PDF 파싱", "STEP 3: 구조 후보 생성", "STEP 4: 구조 확정", "STEP 5: 페이지 엔티티 추출", "STEP 6: 챕터 구조화", "STEP 7: 북 서머리 생성"]
        }
    
    if db_status in ["error_parsing", "error_structuring", "error_summarizing", "failed"]:
        return {
            "status": "에러",
            "status_code": "ERROR",
            "reason": f"에러 발생: {db_status}",
            "last_completed_step": f"에러: {db_status}",
            "can_process": True,
            "missing_steps": ["에러 해결 후 재처리 필요"]
        }
    
    return {
        "status": "미처리",
        "status_code": "NOT_STARTED",
        "reason": "처리 시작 안 됨",
        "last_completed_step": "STEP 0: 초기 상태",
        "can_process": True,
        "missing_steps": ["STEP 1: PDF 업로드", "STEP 2: PDF 파싱", "STEP 3: 구조 후보 생성", "STEP 4: 구조 확정", "STEP 5: 페이지 엔티티 추출", "STEP 6: 챕터 구조화", "STEP 7: 북 서머리 생성"]
    }


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
        if idx % 20 == 0 or idx == total_pdf:
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"  - 진행: {idx}/{total_pdf} ({idx*100//total_pdf}%) | 경과: {int(elapsed)}초")
        
        pdf_hash = get_pdf_hash(pdf_file)
        pdf_files[pdf_hash] = {
            "file_path": pdf_file,
            "file_name": pdf_file.name,
            "hash": pdf_hash,
            "hash_6": pdf_hash[:6],
            "file_size": pdf_file.stat().st_size if pdf_file.exists() else 0
        }
    
    print(f"\n[OK] PDF 파일 해시 계산 완료: {len(pdf_files)}개\n")
    
    # 2. 구조 파일 수집
    print("[STEP 2] 구조 파일 로드 중...")
    structure_dir = Path("data/output/structure")
    structure_files = {}
    for struct_file in structure_dir.glob("*.json"):
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
    
    print(f"[OK] 구조 파일 로드 완료: {len(structure_files)}개\n")
    
    # 3. DB 책 조회
    print("[STEP 3] DB 책 정보 수집 중...")
    all_db_books = db.query(Book).all()
    db_books_by_hash = {}
    db_books_by_path = {}
    
    for book in all_db_books:
        if book.source_file_path:
            pdf_path = Path(book.source_file_path)
            if pdf_path.exists():
                try:
                    pdf_hash = get_pdf_hash(pdf_path)
                    hash_6 = pdf_hash[:6]
                    db_books_by_hash[hash_6] = book
                except:
                    pass
            db_books_by_path[pdf_path.name] = book
    
    print(f"[OK] DB 책 정보 수집 완료: {len(db_books_by_hash)}개\n")
    
    # 4. 북 서머리 파일 확인
    print("[STEP 4] 북 서머리 파일 확인 중...")
    book_summary_dir = settings.output_dir / "book_summaries"
    book_summary_files = {}
    if book_summary_dir.exists():
        for summary_file in book_summary_dir.glob("*.json"):
            book_summary_files[summary_file.name] = summary_file
    
    print(f"[OK] 북 서머리 파일 확인 완료: {len(book_summary_files)}개\n")
    
    # 5. 각 도서별 상세 정보 수집
    print("[STEP 5] 도서별 상세 정보 수집 중...")
    books_detail = []
    
    for pdf_hash, pdf_info in pdf_files.items():
        hash_6 = pdf_info["hash_6"]
        struct_info = structure_files.get(hash_6)
        db_book = db_books_by_hash.get(hash_6) or db_books_by_path.get(pdf_info["file_name"])
        
        # 북 서머리 파일 찾기
        summary_file = None
        if db_book:
            for sf_name in book_summary_files.keys():
                if str(db_book.id) in sf_name:
                    summary_file = sf_name
                    break
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
        
        # DB 정보
        book_id = db_book.id if db_book else None
        title = db_book.title if db_book else pdf_info["file_name"].replace(".pdf", "")
        author = db_book.author if db_book else None
        category = db_book.category if db_book else None
        status = str(db_book.status) if db_book else None
        page_count = db_book.page_count if db_book else None
        created_at = db_book.created_at.isoformat() if db_book and db_book.created_at else None
        updated_at = db_book.updated_at.isoformat() if db_book and db_book.updated_at else None
        
        # DB에서 챕터/요약 수 조회
        chapter_count_db = 0
        page_summary_count = 0
        chapter_summary_count = 0
        if db_book:
            chapter_count_db = db.query(Chapter).filter(Chapter.book_id == db_book.id).count()
            page_summary_count = db.query(PageSummary).filter(PageSummary.book_id == db_book.id).count()
            chapter_summary_count = db.query(ChapterSummary).filter(ChapterSummary.book_id == db_book.id).count()
        
        # 챕터 수는 구조 파일 기준 우선
        final_chapter_count = struct_info["chapter_count"] if struct_info else chapter_count_db
        
        # 처리 상태 결정
        completion = get_completion_status(
            db_book, chapter_count_db, page_summary_count, 
            chapter_summary_count, summary_file, pdf_info["file_name"]
        )
        
        books_detail.append({
            "book_id": book_id,
            "title": title,
            "author": author,
            "category": category,
            "pdf_file": pdf_info["file_name"],
            "pdf_hash_6": hash_6,
            "pdf_file_size": pdf_info["file_size"],
            "page_count": page_count,
            "chapter_count": final_chapter_count,
            "chapter_count_db": chapter_count_db,
            "page_summary_count": page_summary_count,
            "chapter_summary_count": chapter_summary_count,
            "book_summary_file": summary_file,
            "structure_file": struct_info["file_name"] if struct_info else None,
            "status": status,
            "completion_status": completion["status"],
            "completion_status_code": completion["status_code"],
            "completion_reason": completion["reason"],
            "last_completed_step": completion["last_completed_step"],
            "can_process": completion["can_process"],
            "missing_steps": completion["missing_steps"],
            "created_at": created_at,
            "updated_at": updated_at
        })
    
    # Book ID 순으로 정렬 (None은 마지막)
    books_detail.sort(key=lambda x: (x["book_id"] is None, x["book_id"] or 0))
    
    print(f"[OK] 도서 정보 수집 완료: {len(books_detail)}권\n")
    
    # 6. 마크다운 파일 생성
    print("[STEP 6] 상세 마크다운 파일 생성 중...")
    
    md_content = "# 전체 도서 상세 리스트\n\n"
    md_content += f"**생성 일시**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    md_content += f"**총 도서 수**: {len(books_detail)}권\n\n"
    
    # 통계
    completed = len([b for b in books_detail if b["completion_status_code"] == "COMPLETED"])
    partial = len([b for b in books_detail if b["completion_status_code"] == "PARTIAL"])
    error = len([b for b in books_detail if b["completion_status_code"] == "ERROR"])
    excluded = len([b for b in books_detail if b["completion_status_code"] == "EXCLUDED"])
    not_started = len([b for b in books_detail if b["completion_status_code"] == "NOT_STARTED"])
    
    md_content += "## 처리 현황 요약\n\n"
    md_content += f"- ✅ **완료**: {completed}권 ({completed*100//len(books_detail) if len(books_detail) > 0 else 0}%)\n"
    md_content += f"- ⚠️ **부분 완료**: {partial}권 ({partial*100//len(books_detail) if len(books_detail) > 0 else 0}%)\n"
    md_content += f"- ❌ **에러**: {error}권\n"
    md_content += f"- 🚫 **처리 제외**: {excluded}권\n"
    md_content += f"- ⚪ **미처리**: {not_started}권\n\n"
    
    md_content += "---\n\n"
    
    # 챕터 수 기준 분류
    books_6plus = [b for b in books_detail if b["chapter_count"] >= 6 and (not b["title"] or "노이즈" not in b["title"]) and "노이즈" not in b["pdf_file"]]
    books_under_6 = [b for b in books_detail if b["chapter_count"] < 6]
    books_excluded = [b for b in books_detail if (b["title"] and "노이즈" in b["title"]) or "노이즈" in b["pdf_file"]]
    
    md_content += "## 챕터 수 기준 분류\n\n"
    md_content += f"- **챕터 6개 이상 (처리 대상)**: {len(books_6plus)}권\n"
    md_content += f"- **챕터 6개 미만**: {len(books_under_6)}권\n"
    md_content += f"- **처리 제외**: {len(books_excluded)}권\n\n"
    md_content += "---\n\n"
    
    # 각 도서별 상세 정보
    md_content += "## 도서별 상세 정보\n\n"
    
    for idx, book in enumerate(books_detail, 1):
        md_content += f"### {idx}. {book['title'] or book['pdf_file'].replace('.pdf', '')}\n\n"
        md_content += f"#### 기본 정보\n\n"
        md_content += f"- **Book ID**: {book['book_id'] or '없음'}\n"
        md_content += f"- **제목**: {book['title'] or '없음'}\n"
        md_content += f"- **저자**: {book['author'] or '없음'}\n"
        md_content += f"- **분야**: {book['category'] or '미분류'}\n"
        md_content += f"- **PDF 파일**: `{book['pdf_file']}`\n"
        md_content += f"- **PDF 해시 (6자리)**: `{book['pdf_hash_6']}`\n"
        md_content += f"- **PDF 파일 크기**: {book['pdf_file_size']:,} bytes ({book['pdf_file_size']/1024/1024:.2f} MB)\n"
        md_content += f"- **페이지 수**: {book['page_count'] or '미확인'}\n"
        md_content += f"- **챕터 수**: {book['chapter_count']}개\n"
        
        md_content += f"\n#### 처리 상태\n\n"
        status_emoji = {
            "COMPLETED": "✅",
            "PARTIAL": "⚠️",
            "ERROR": "❌",
            "EXCLUDED": "🚫",
            "NOT_STARTED": "⚪"
        }
        emoji = status_emoji.get(book["completion_status_code"], "❓")
        md_content += f"- **처리 상태**: {emoji} {book['completion_status']}\n"
        md_content += f"- **상태 코드**: `{book['completion_status_code']}`\n"
        md_content += f"- **사유**: {book['completion_reason']}\n"
        md_content += f"- **마지막 완료 단계**: {book['last_completed_step']}\n"
        md_content += f"- **처리 가능 여부**: {'✅ 가능' if book['can_process'] else '❌ 불가능'}\n"
        
        if book['missing_steps']:
            md_content += f"- **누락된 단계**:\n"
            for step in book['missing_steps']:
                md_content += f"  - {step}\n"
        
        md_content += f"\n#### 데이터베이스 정보\n\n"
        md_content += f"- **DB 상태**: {book['status'] or '없음'}\n"
        md_content += f"- **DB 챕터 수**: {book['chapter_count_db']}개\n"
        md_content += f"- **페이지 요약 수**: {book['page_summary_count']}개\n"
        md_content += f"- **챕터 요약 수**: {book['chapter_summary_count']}개\n"
        md_content += f"- **생성 일시**: {book['created_at'] or '없음'}\n"
        md_content += f"- **수정 일시**: {book['updated_at'] or '없음'}\n"
        
        md_content += f"\n#### 파일 정보\n\n"
        md_content += f"- **구조 파일**: {book['structure_file'] or '없음'}\n"
        md_content += f"- **북 서머리 파일**: {book['book_summary_file'] or '없음'}\n"
        
        md_content += "\n---\n\n"
    
    # 처리 가능한 책 목록 (참고용)
    processable_books = [b for b in books_detail if b['can_process']]
    if processable_books:
        md_content += "## 처리 가능한 책 목록 (참고용)\n\n"
        md_content += "| Book ID | 제목 | 상태 | 누락된 단계 |\n"
        md_content += "|---------|------|------|------------|\n"
        for book in processable_books:
            title = (book['title'][:30] + ".." if book['title'] and len(book['title']) > 32 else book['title']) or book['pdf_file'][:30]
            missing = ", ".join(book['missing_steps'][:2]) + ("..." if len(book['missing_steps']) > 2 else "")
            book_id_str = str(book['book_id']) if book['book_id'] else "-"
            md_content += f"| {book_id_str} | {title} | {book['completion_status']} | {missing} |\n"
        md_content += "\n"
    
    # 파일 저장
    output_file = Path("docs/books_detailed_list.md")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(md_content, encoding="utf-8")
    
    total_time = (datetime.now() - start_time).total_seconds()
    print(f"[OK] 상세 마크다운 파일 생성 완료: {output_file}")
    print(f"\n[SUMMARY]")
    print(f"  - 총 소요 시간: {int(total_time)}초")
    print(f"  - 전체 도서: {len(books_detail)}권")
    print(f"  - 완료: {completed}권")
    print(f"  - 부분 완료: {partial}권")
    print(f"  - 에러: {error}권")
    print(f"  - 처리 제외: {excluded}권")
    print(f"  - 미처리: {not_started}권")
    print(f"  - 처리 가능: {len(processable_books)}권")
    
finally:
    db.close()

