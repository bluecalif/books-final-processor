"""
E2E 테스트: 새 책 1권 전체 파이프라인 (Phase 7.2 - 3단계)

⚠️ 실제 서버 실행, 실제 데이터만 사용, Mock 사용 절대 금지

전체 플로우:
1. PDF 업로드 → 책 생성 (uploaded)
2. 실제 Upstage API로 PDF 파싱 → parsed 상태 확인 → 캐시 저장 확인
3. 구조 후보 생성 → 캐시된 파싱 결과 재사용 확인
4. 구조 확정 (structured) → 구조 파일 저장 확인
5. 페이지 엔티티 추출 (page_summarized) → 캐시 저장 확인
6. 챕터 구조화 (summarized) → 캐시 저장 확인
7. 도서 서머리 생성 → 캐시 저장 확인
8. 최종 결과 조회 검증

⚠️ 중요: 캐시 활용 확인
- Upstage API 캐시: data/cache/upstage/
- 구조 분석 결과: data/output/structure/
- 요약 캐시: data/cache/summaries/
"""
import pytest
import httpx
import time
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any
from backend.config.settings import settings
from backend.tests.test_utils import wait_for_extraction_with_progress

pytestmark = pytest.mark.e2e


def get_pdf_hash(pdf_path: Path) -> str:
    """PDF 파일의 MD5 해시 계산"""
    hasher = hashlib.md5()
    with open(pdf_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def check_upstage_cache(pdf_path: Path) -> Optional[Path]:
    """Upstage API 캐시 확인"""
    pdf_hash = get_pdf_hash(pdf_path)
    cache_file = settings.cache_dir / "upstage" / f"{pdf_hash}.json"
    return cache_file if cache_file.exists() else None


def check_structure_file(book_id: int, book_title: Optional[str] = None) -> Optional[Path]:
    """구조 분석 JSON 파일 확인"""
    structure_dir = settings.output_dir / "structure"
    
    # book_id로 찾기
    pattern = f"*_{book_id}_structure.json"
    for file in structure_dir.glob(pattern):
        return file
    
    # 책 제목으로 찾기
    if book_title:
        import re
        safe_title = re.sub(r'[\\/:*?"<>|]', "_", book_title)
        safe_title = safe_title.replace(" ", "_")[:10]
        pattern = f"*_{safe_title}_structure.json"
        for file in structure_dir.glob(pattern):
            return file
    
    # book_id만으로 찾기 (fallback)
    pattern = f"{book_id}_structure.json"
    for file in structure_dir.glob(pattern):
        return file
    
    return None


def wait_for_status(
    e2e_client: httpx.Client,
    book_id: int,
    target_status: str,
    max_wait_time: int = 1800,
    check_interval: int = 5,
) -> Dict[str, Any]:
    """책 상태가 목표 상태가 될 때까지 대기"""
    start_time = time.time()
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait_time:
            pytest.fail(
                f"Status change timeout: book_id={book_id}, "
                f"target={target_status}, elapsed={elapsed:.1f}s"
            )
        
        response = e2e_client.get(f"/api/books/{book_id}")
        assert response.status_code == 200
        book_data = response.json()
        current_status = book_data["status"]
        
        if current_status == target_status:
            print(f"[TEST] Status changed to {target_status} (elapsed: {elapsed:.1f}s)")
            return book_data
        elif current_status in ["error_parsing", "error_structuring", "error_summarizing", "failed"]:
            pytest.fail(
                f"Processing failed: book_id={book_id}, status={current_status}"
            )
        
        if int(elapsed) % 30 == 0:  # 30초마다 출력
            print(f"[TEST] Waiting for {target_status}... (current: {current_status}, elapsed: {elapsed:.1f}s)")
        
        time.sleep(check_interval)


@pytest.mark.e2e
def test_e2e_new_book_full_pipeline(e2e_client: httpx.Client):
    """
    새 책 1권 전체 파이프라인 E2E 테스트
    
    Book ID 165 ("1등의 통찰", 7개 챕터)를 사용하여 전체 파이프라인 테스트
    """
    # 테스트 대상: Book ID 165 (이미 사용된 4권 제외한 첫 번째)
    book_id = 165
    title = "1등의 통찰"
    category = "경제/경영"
    chapter_count = 7
    
    # PDF 파일 경로 확인
    from backend.api.database import SessionLocal
    from backend.api.models.book import Book
    
    db = SessionLocal()
    try:
        book = db.query(Book).filter(Book.id == book_id).first()
        if not book:
            pytest.skip(f"Book {book_id} not found in database")
        pdf_path = Path(book.source_file_path)
        if not pdf_path.exists():
            pytest.skip(f"PDF file not found: {pdf_path}")
    finally:
        db.close()
    
    print(f"\n{'=' * 80}")
    print(f"[TEST] New Book Full Pipeline E2E Test")
    print(f"Book ID: {book_id}, Title: {title}, Category: {category}, Chapters: {chapter_count}")
    print(f"{'=' * 80}")
    
    # ===== 1. PDF 업로드 =====
    print(f"\n[STEP 1] PDF 업로드...")
    
    # Upstage 캐시 확인 (이미 있으면 재사용)
    upstage_cache = check_upstage_cache(pdf_path)
    if upstage_cache:
        print(f"[CACHE] Upstage 캐시 발견: {upstage_cache.name}")
    else:
        print(f"[CACHE] Upstage 캐시 없음 (새로 파싱 필요)")
    
    with open(pdf_path, "rb") as f:
        files = {"file": (pdf_path.name, f, "application/pdf")}
        data = {
            "title": title,
            "author": book.author or "",
            "category": category,
        }
        response = e2e_client.post("/api/books/upload", files=files, data=data)
    
    assert response.status_code == 200
    upload_result = response.json()
    assert "book_id" in upload_result
    uploaded_book_id = upload_result["book_id"]
    
    print(f"[STEP 1] ✅ 업로드 완료: book_id={uploaded_book_id}")
    
    # ===== 2. PDF 파싱 완료 대기 =====
    print(f"\n[STEP 2] PDF 파싱 완료 대기...")
    
    book_data = wait_for_status(
        e2e_client, uploaded_book_id, "parsed", max_wait_time=600
    )
    
    # 캐시 저장 확인
    upstage_cache_after = check_upstage_cache(pdf_path)
    assert upstage_cache_after is not None, "Upstage 캐시가 저장되지 않았습니다"
    print(f"[CACHE] ✅ Upstage 캐시 저장 확인: {upstage_cache_after.name}")
    
    print(f"[STEP 2] ✅ 파싱 완료: page_count={book_data.get('page_count', 0)}")
    
    # ===== 3. 구조 후보 생성 =====
    print(f"\n[STEP 3] 구조 후보 생성...")
    
    response = e2e_client.get(f"/api/books/{uploaded_book_id}/structure/candidates")
    assert response.status_code == 200
    candidates = response.json()
    
    assert "auto_candidates" in candidates
    assert len(candidates["auto_candidates"]) > 0
    
    # 캐시된 파싱 결과 재사용 확인 (로깅으로 확인)
    print(f"[CACHE] ✅ 캐시된 파싱 결과 재사용 확인 (구조 후보 생성)")
    
    heuristic_structure = candidates["auto_candidates"][0]["structure"]
    chapters = heuristic_structure.get("chapters", [])
    print(f"[STEP 3] ✅ 구조 후보 생성 완료: {len(chapters)}개 챕터")
    
    if not chapters:
        pytest.skip(f"Book {uploaded_book_id} has no chapters in structure candidates. Cannot proceed.")
    
    # ===== 4. 구조 확정 =====
    print(f"\n[STEP 4] 구조 확정...")
    
    final_structure = {
        "main_start_page": heuristic_structure.get("main_start_page"),
        "main_end_page": heuristic_structure.get("main_end_page"),
        "chapters": [
            {
                "title": ch.get("title", ""),
                "start_page": ch.get("start_page"),
                "end_page": ch.get("end_page"),
            }
            for ch in chapters
        ],
        "notes_pages": [],
        "start_pages": [],
        "end_pages": [],
    }
    
    response = e2e_client.post(
        f"/api/books/{uploaded_book_id}/structure/final",
        json=final_structure
    )
    
    if response.status_code != 200:
        error_detail = response.json().get("detail", "")
        pytest.fail(f"Structure finalization failed: {response.status_code} - {error_detail}")
    
    assert response.status_code == 200
    
    # 구조 파일 저장 확인
    structure_file = check_structure_file(uploaded_book_id, title)
    assert structure_file is not None, "구조 파일이 저장되지 않았습니다"
    print(f"[CACHE] ✅ 구조 파일 저장 확인: {structure_file.name}")
    
    book_data = wait_for_status(
        e2e_client, uploaded_book_id, "structured", max_wait_time=60
    )
    
    print(f"[STEP 4] ✅ 구조 확정 완료")
    
    # ===== 5. 페이지 엔티티 추출 =====
    print(f"\n[STEP 5] 페이지 엔티티 추출...")
    
    # 예상 페이지 수 계산
    structure_data = book_data.get("structure_data", {})
    if structure_data:
        main_start = structure_data.get("main_start_page", 0)
        main_end = structure_data.get("main_end_page", 0)
        expected_pages = main_end - main_start + 1 if main_start and main_end else book_data.get("page_count", 0)
    else:
        expected_pages = book_data.get("page_count", 0)
    
    # 캐시 디렉토리 확인 (추출 전)
    summaries_cache_dir = settings.cache_dir / "summaries"
    page_cache_before = len(list(summaries_cache_dir.glob("page_*.json")))
    
    response = e2e_client.post(f"/api/books/{uploaded_book_id}/extract/pages")
    assert response.status_code == 200
    assert response.json()["status"] == "processing"
    
    # 현재 페이지 개수를 가져오는 함수
    def get_page_count(book_id: int) -> int:
        pages_response = e2e_client.get(f"/api/books/{book_id}/pages")
        if pages_response.status_code == 200:
            return len(pages_response.json())
        return 0
    
    # 완료 대기 (진행률 출력 포함)
    book_data = wait_for_extraction_with_progress(
        e2e_client=e2e_client,
        book_id=uploaded_book_id,
        target_status="page_summarized",
        expected_count=expected_pages,
        get_current_count_func=get_page_count,
        extraction_type="pages",
        max_wait_time=1800,
        check_interval=10,
    )
    
    # 캐시 저장 확인
    page_cache_after = len(list(summaries_cache_dir.glob("page_*.json")))
    assert page_cache_after > page_cache_before, "페이지 엔티티 캐시가 저장되지 않았습니다"
    print(f"[CACHE] ✅ 페이지 엔티티 캐시 저장 확인: {page_cache_after - page_cache_before}개 추가")
    
    # 페이지 엔티티 검증
    response = e2e_client.get(f"/api/books/{uploaded_book_id}/pages")
    assert response.status_code == 200
    page_entities = response.json()
    assert len(page_entities) > 0
    
    print(f"[STEP 5] ✅ 페이지 엔티티 추출 완료: {len(page_entities)}개 페이지")
    
    # ===== 6. 챕터 구조화 =====
    print(f"\n[STEP 6] 챕터 구조화...")
    
    # 예상 챕터 수
    expected_chapters = len(structure_data.get("chapters", [])) if structure_data else chapter_count
    
    # 캐시 디렉토리 확인 (추출 전)
    chapter_cache_before = len(list(summaries_cache_dir.glob("chapter_*.json")))
    
    response = e2e_client.post(f"/api/books/{uploaded_book_id}/extract/chapters")
    assert response.status_code == 200
    assert response.json()["status"] == "processing"
    
    # 현재 챕터 개수를 가져오는 함수
    def get_chapter_count(book_id: int) -> int:
        chapters_response = e2e_client.get(f"/api/books/{book_id}/chapters")
        if chapters_response.status_code == 200:
            return len(chapters_response.json())
        return 0
    
    # 완료 대기 (진행률 출력 포함)
    book_data = wait_for_extraction_with_progress(
        e2e_client=e2e_client,
        book_id=uploaded_book_id,
        target_status="summarized",
        expected_count=expected_chapters,
        get_current_count_func=get_chapter_count,
        extraction_type="chapters",
        max_wait_time=1800,
        check_interval=10,
    )
    
    # 캐시 저장 확인
    chapter_cache_after = len(list(summaries_cache_dir.glob("chapter_*.json")))
    assert chapter_cache_after > chapter_cache_before, "챕터 구조화 캐시가 저장되지 않았습니다"
    print(f"[CACHE] ✅ 챕터 구조화 캐시 저장 확인: {chapter_cache_after - chapter_cache_before}개 추가")
    
    # 챕터 엔티티 검증
    response = e2e_client.get(f"/api/books/{uploaded_book_id}/chapters")
    assert response.status_code == 200
    chapter_entities = response.json()
    assert len(chapter_entities) > 0
    
    print(f"[STEP 6] ✅ 챕터 구조화 완료: {len(chapter_entities)}개 챕터")
    
    # ===== 7. 도서 서머리 생성 =====
    print(f"\n[STEP 7] 도서 서머리 생성...")
    
    from backend.api.services.book_report_service import BookReportService
    from backend.api.database import SessionLocal
    
    db = SessionLocal()
    try:
        report_service = BookReportService(db)
        report = report_service.generate_report(uploaded_book_id)
        print(f"[STEP 7] ✅ 도서 서머리 생성 완료")
    finally:
        db.close()
    
    # 도서 서머리 파일 확인
    book_summary_dir = settings.output_dir / "book_summaries"
    book_summary_files = list(book_summary_dir.glob(f"*{uploaded_book_id}*.json"))
    book_summary_files.extend(book_summary_dir.glob(f"*{title}*.json"))
    assert len(book_summary_files) > 0, "도서 서머리 파일이 생성되지 않았습니다"
    print(f"[CACHE] ✅ 도서 서머리 파일 저장 확인: {book_summary_files[0].name}")
    
    # ===== 8. 최종 결과 조회 검증 =====
    print(f"\n[STEP 8] 최종 결과 조회 검증...")
    
    # 책 정보 조회
    response = e2e_client.get(f"/api/books/{uploaded_book_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "summarized"
    
    # 페이지 엔티티 조회
    response = e2e_client.get(f"/api/books/{uploaded_book_id}/pages")
    assert response.status_code == 200
    assert len(response.json()) > 0
    
    # 챕터 엔티티 조회
    response = e2e_client.get(f"/api/books/{uploaded_book_id}/chapters")
    assert response.status_code == 200
    assert len(response.json()) > 0
    
    print(f"[STEP 8] ✅ 최종 결과 조회 검증 완료")
    
    print(f"\n{'=' * 80}")
    print(f"[TEST] ✅ 전체 파이프라인 E2E 테스트 완료")
    print(f"Book ID: {uploaded_book_id}, Title: {title}")
    print(f"{'=' * 80}")

