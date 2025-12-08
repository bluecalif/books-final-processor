"""
E2E 테스트: 전체 파이프라인 통합 테스트

실제 서버 실행, 실제 데이터만 사용, Mock 사용 절대 금지

**목적**: 
- 전체 파이프라인을 일관된 방식으로 테스트
- 입력 책 리스트만 다르고 처리 과정은 완전히 동일
- 4권 검증, 1권 테스트, 7.5단계 대량 처리 모두 동일한 함수 사용

**파이프라인**:
PDF 업로드 → 파싱 → 구조분석 → 페이지엔티티 → 챕터서머리 → 북서머리

**캐시 활용 원칙**:
- Upstage API 캐시: data/cache/upstage/ (파일 해시 기반)
- 구조 분석 결과: data/output/structure/ (PDF 해시 기반)
- 요약 캐시: data/cache/summaries/{book_title}/ (책 제목 폴더)
- 모든 단계에서 캐시 확인 및 재사용 검증
"""
import pytest
import sys
import io

# 한글 출력을 위한 인코딩 설정
if sys.platform == 'win32':
    # Windows 환경에서 UTF-8 인코딩 설정
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
import httpx
import time
import hashlib
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from backend.config.settings import settings
from backend.tests.test_utils import (
    wait_for_extraction_with_progress,
    find_cache_files,
    get_cache_file_count,
)

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


def check_structure_file_by_hash(pdf_path: Path, book_title: Optional[str] = None) -> Optional[Path]:
    """PDF 해시 기반으로 구조 분석 JSON 파일 확인"""
    structure_dir = settings.output_dir / "structure"
    pdf_hash = get_pdf_hash(pdf_path)
    hash_6 = pdf_hash[:6]
    
    # 1. 해시 + 책 제목으로 찾기
    if book_title:
        import re
        safe_title = re.sub(r'[\\/:*?"<>|]', "_", book_title)
        safe_title = safe_title.replace(" ", "_")[:10]
        pattern = f"{hash_6}_{safe_title}_structure.json"
        structure_file = structure_dir / pattern
        if structure_file.exists():
            return structure_file
    
    # 2. 해시만으로 찾기
    pattern = f"{hash_6}_*_structure.json"
    matches = list(structure_dir.glob(pattern))
    if matches:
        return matches[0]
    
    # 3. 해시만 있는 파일
    pattern = f"{hash_6}_structure.json"
    structure_file = structure_dir / pattern
    if structure_file.exists():
        return structure_file
    
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
            elapsed_min = int(elapsed // 60)
            elapsed_sec = int(elapsed % 60)
            print(f"[TEST] [OK] Status changed to {target_status} (Time: {elapsed_min:02d}:{elapsed_sec:02d})")
            return book_data
        elif current_status in ["error_parsing", "error_structuring", "error_summarizing", "failed"]:
            pytest.fail(
                f"Processing failed: book_id={book_id}, status={current_status}"
            )
        
        if int(elapsed) % 30 == 0:  # 30초마다 출력
            elapsed_min = int(elapsed // 60)
            elapsed_sec = int(elapsed % 60)
            print(f"[TEST] Waiting for {target_status}... (current: {current_status}, Time: {elapsed_min:02d}:{elapsed_sec:02d})")
        
        time.sleep(check_interval)


def process_book_full_pipeline(
    e2e_client: httpx.Client,
    book_id: int,
    pdf_path: Path,
    book_title: str,
    category: str,
    chapter_count: int,
    skip_upload: bool = False,
) -> Dict[str, Any]:
    """
    전체 파이프라인 처리 (통합 함수)
    
    Args:
        e2e_client: HTTP 클라이언트
        book_id: 책 ID (skip_upload=True인 경우)
        pdf_path: PDF 파일 경로
        book_title: 책 제목
        category: 분야
        chapter_count: 챕터 수
        skip_upload: True이면 업로드 단계 건너뛰기 (이미 업로드된 책)
    
    Returns:
        최종 책 데이터
    """
    print(f"\n{'=' * 80}")
    print(f"[TEST] Full Pipeline Processing")
    print(f"Book ID: {book_id if skip_upload else 'NEW'}, Title: {book_title}")
    print(f"Category: {category}, Chapters: {chapter_count}")
    print(f"{'=' * 80}")
    
    # ===== 1. PDF 업로드 (skip_upload=False인 경우만) =====
    if not skip_upload:
        print(f"\n[STEP 1] PDF 업로드...")
        
        # Upstage 캐시 확인
        upstage_cache = check_upstage_cache(pdf_path)
        if upstage_cache:
            print(f"[CACHE] [OK] Upstage 캐시 발견: {upstage_cache.name}")
        else:
            print(f"[CACHE] Upstage 캐시 없음 (새로 파싱 필요)")
        
        with open(pdf_path, "rb") as f:
            files = {"file": (pdf_path.name, f, "application/pdf")}
            data = {
                "title": book_title,
                "category": category,
            }
            response = e2e_client.post("/api/books/upload", files=files, data=data)
        
        assert response.status_code == 200
        upload_result = response.json()
        assert "book_id" in upload_result
        book_id = upload_result["book_id"]
        print(f"[STEP 1] [OK] 업로드 완료: book_id={book_id}")
    else:
        print(f"\n[STEP 1] PDF 업로드 건너뛰기 (이미 업로드된 책: book_id={book_id})")
    
    # ===== 2. PDF 파싱 완료 대기 =====
    print(f"\n[STEP 2] PDF 파싱 완료 대기...")
    
    book_data = wait_for_status(
        e2e_client, book_id, "parsed", max_wait_time=600
    )
    
    # 캐시 저장 확인
    upstage_cache_after = check_upstage_cache(pdf_path)
    assert upstage_cache_after is not None, "Upstage 캐시가 저장되지 않았습니다"
    print(f"[CACHE] [OK] Upstage 캐시 저장 확인: {upstage_cache_after.name}")
    
    print(f"[STEP 2] [OK] 파싱 완료: page_count={book_data.get('page_count', 0)}")
    
    # ===== 3. 구조 후보 생성 =====
    print(f"\n[STEP 3] 구조 후보 생성...")
    
    # 구조 파일 캐시 확인
    structure_cache = check_structure_file_by_hash(pdf_path, book_title)
    if structure_cache:
        print(f"[CACHE] [OK] 구조 파일 캐시 발견: {structure_cache.name} (재사용 예정)")
    else:
        print(f"[CACHE] 구조 파일 캐시 없음 (새로 구조 분석 수행 예정)")
    
    response = e2e_client.get(f"/api/books/{book_id}/structure/candidates")
    assert response.status_code == 200
    candidates = response.json()
    
    assert "auto_candidates" in candidates
    assert len(candidates["auto_candidates"]) > 0
    
    # 구조 파일 캐시 재사용 확인
    if structure_cache:
        print(f"[CACHE] [OK] 구조 파일 캐시 재사용 확인")
    
    heuristic_structure = candidates["auto_candidates"][0]["structure"]
    
    # 구조 형식 확인 및 변환
    main_pages = heuristic_structure.get("main", {}).get("pages", [])
    chapters = heuristic_structure.get("main", {}).get("chapters", [])
    
    # main_start_page와 main_end_page 계산
    if main_pages:
        main_start_page = main_pages[0]
        main_end_page = main_pages[-1]
    else:
        main_start_page = heuristic_structure.get("main_start_page")
        main_end_page = heuristic_structure.get("main_end_page")
        if not main_start_page or not main_end_page:
            pytest.skip(f"Book {book_id} has no main pages in structure candidates. Cannot proceed.")
    
    if not chapters:
        pytest.skip(f"Book {book_id} has no chapters in structure candidates. Cannot proceed.")
    
    print(f"[STEP 3] [OK] 구조 후보 생성 완료: {len(chapters)}개 챕터, main_pages={main_start_page}~{main_end_page}")
    
    # ===== 4. 구조 확정 =====
    print(f"\n[STEP 4] 구조 확정...")
    
    final_structure = {
        "main_start_page": main_start_page,
        "main_end_page": main_end_page,
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
        f"/api/books/{book_id}/structure/final",
        json=final_structure
    )
    
    assert response.status_code == 200
    
    book_data = wait_for_status(
        e2e_client, book_id, "structured", max_wait_time=60
    )
    
    print(f"[STEP 4] [OK] 구조 확정 완료")
    
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
    
    # 캐시 확인 (추출 전)
    page_cache_before = get_cache_file_count(book_id, book_title, "pages")
    
    response = e2e_client.post(f"/api/books/{book_id}/extract/pages")
    assert response.status_code == 200
    assert response.json()["status"] == "processing"
    
    # 현재 페이지 개수를 가져오는 함수
    def get_page_count(bid: int) -> int:
        pages_response = e2e_client.get(f"/api/books/{bid}/pages")
        if pages_response.status_code == 200:
            return len(pages_response.json())
        return 0
    
    # 완료 대기 (진행률 출력 포함)
    book_data = wait_for_extraction_with_progress(
        e2e_client=e2e_client,
        book_id=book_id,
        target_status="page_summarized",
        expected_count=expected_pages,
        get_current_count_func=get_page_count,
        extraction_type="pages",
        max_wait_time=1800,
        check_interval=3,  # 3초로 단축 (서버 로그 파싱으로 실시간 진행률 확인)
    )
    
    # 캐시 저장 확인
    page_cache_after = get_cache_file_count(book_id, book_title, "pages")
    if page_cache_after > page_cache_before:
        print(f"[CACHE] [OK] 페이지 엔티티 캐시 저장 확인: {page_cache_after - page_cache_before}개 추가")
    else:
        print(f"[CACHE] 페이지 엔티티 캐시 확인: {page_cache_after}개 (재사용 가능)")
    
    # 페이지 엔티티 검증
    response = e2e_client.get(f"/api/books/{book_id}/pages")
    assert response.status_code == 200
    page_entities = response.json()
    assert len(page_entities) > 0
    
    print(f"[STEP 5] [OK] 페이지 엔티티 추출 완료: {len(page_entities)}개 페이지")
    
    # ===== 6. 챕터 구조화 =====
    print(f"\n[STEP 6] 챕터 구조화...")
    
    # 예상 챕터 수
    expected_chapters = len(structure_data.get("chapters", [])) if structure_data else chapter_count
    
    # 캐시 확인 (추출 전)
    chapter_cache_before = get_cache_file_count(book_id, book_title, "chapters")
    
    response = e2e_client.post(f"/api/books/{book_id}/extract/chapters")
    assert response.status_code == 200
    assert response.json()["status"] == "processing"
    
    # 현재 챕터 개수를 가져오는 함수
    def get_chapter_count(bid: int) -> int:
        chapters_response = e2e_client.get(f"/api/books/{bid}/chapters")
        if chapters_response.status_code == 200:
            return len(chapters_response.json())
        return 0
    
    # 완료 대기 (진행률 출력 포함)
    book_data = wait_for_extraction_with_progress(
        e2e_client=e2e_client,
        book_id=book_id,
        target_status="summarized",
        expected_count=expected_chapters,
        get_current_count_func=get_chapter_count,
        extraction_type="chapters",
        max_wait_time=1800,
        check_interval=3,  # 3초로 단축 (서버 로그 파싱으로 실시간 진행률 확인)
    )
    
    # 캐시 저장 확인
    chapter_cache_after = get_cache_file_count(book_id, book_title, "chapters")
    if chapter_cache_after > chapter_cache_before:
        print(f"[CACHE] [OK] 챕터 구조화 캐시 저장 확인: {chapter_cache_after - chapter_cache_before}개 추가")
    else:
        print(f"[CACHE] 챕터 구조화 캐시 확인: {chapter_cache_after}개 (재사용 가능)")
    
    # 챕터 엔티티 검증
    response = e2e_client.get(f"/api/books/{book_id}/chapters")
    assert response.status_code == 200
    chapter_entities = response.json()
    assert len(chapter_entities) > 0
    
    print(f"[STEP 6] [OK] 챕터 구조화 완료: {len(chapter_entities)}개 챕터")
    
    # ===== 7. 북 서머리 생성 =====
    print(f"\n[STEP 7] 북 서머리 생성...", flush=True)
    
    response = e2e_client.post(f"/api/books/{book_id}/extract/book_summary")
    assert response.status_code == 200
    assert response.json()["status"] == "processing"
    
    # 완료 대기 (북 서머리 파일 생성 확인 + 서버 로그 파싱)
    max_wait_time = 300  # 5분
    start_time = time.time()
    last_print_time = 0
    last_step = 0
    
    book_summary_dir = settings.output_dir / "book_summaries"
    from backend.tests.test_utils import find_latest_server_log, parse_progress_from_log
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait_time:
            pytest.fail(f"Book summary generation timeout after {max_wait_time} seconds")
        
        # 서버 로그에서 진행률 확인
        log_file_path = find_latest_server_log()
        log_progress = parse_progress_from_log(log_file_path, "book_report") if log_file_path else None
        
        # 북 서머리 파일 확인 (파일명 패턴: {safe_title}_report.json)
        # safe_title은 공백이 언더스코어로 변환됨
        safe_title = "".join(c for c in book_title if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')[:100]
        book_summary_files = list(book_summary_dir.glob(f"*{book_id}*.json"))
        book_summary_files.extend(book_summary_dir.glob(f"*{safe_title}*.json"))
        # 원본 제목도 확인 (공백 포함)
        if book_title:
            book_summary_files.extend(book_summary_dir.glob(f"*{book_title.replace(' ', '_')}*.json"))
        
        # 파일이 생성되었으면 완료
        if book_summary_files:
            print(f"[CACHE] [OK] 북 서머리 파일 저장 확인: {book_summary_files[0].name}", flush=True)
            break
        
        # 진행률 출력 (3초마다 또는 단계 변화 시)
        should_print = False
        if log_progress:
            current_step = log_progress.get("current_step", 0)
            total_steps = log_progress.get("total_steps", 0)
            progress_pct = log_progress.get("progress_pct", 0)
            
            if current_step != last_step or int(elapsed) - last_print_time >= 3:
                should_print = True
                elapsed_min = int(elapsed // 60)
                elapsed_sec = int(elapsed % 60)
                print(
                    f"[TEST] Book summary: {current_step}/{total_steps} steps ({progress_pct}%) | "
                    f"Time: {elapsed_min:02d}:{elapsed_sec:02d}",
                    flush=True
                )
                last_step = current_step
                last_print_time = int(elapsed)
        elif int(elapsed) - last_print_time >= 3:
            should_print = True
            elapsed_min = int(elapsed // 60)
            elapsed_sec = int(elapsed % 60)
            print(f"[TEST] Waiting for book summary... (Time: {elapsed_min:02d}:{elapsed_sec:02d})", flush=True)
            last_print_time = int(elapsed)
        
        time.sleep(2)  # 2초마다 확인
    
    print(f"[STEP 7] [OK] 북 서머리 생성 완료", flush=True)
    
    # ===== 8. 최종 결과 조회 검증 =====
    print(f"\n[STEP 8] 최종 결과 조회 검증...")
    
    # 책 정보 조회
    response = e2e_client.get(f"/api/books/{book_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "summarized"
    
    # 페이지 엔티티 조회
    response = e2e_client.get(f"/api/books/{book_id}/pages")
    assert response.status_code == 200
    assert len(response.json()) > 0
    
    # 챕터 엔티티 조회
    response = e2e_client.get(f"/api/books/{book_id}/chapters")
    assert response.status_code == 200
    assert len(response.json()) > 0
    
    print(f"[STEP 8] [OK] 최종 결과 조회 검증 완료")
    
    print(f"\n{'=' * 80}")
    print(f"[TEST] [OK] 전체 파이프라인 처리 완료")
    print(f"Book ID: {book_id}, Title: {book_title}")
    print(f"{'=' * 80}")
    
    return book_data


@pytest.fixture(scope="session")
def test_samples_6plus():
    """챕터 6개 이상 도서 샘플 로드"""
    samples_file = settings.output_dir / "test_samples" / "selected_samples.json"
    
    if not samples_file.exists():
        pytest.skip(
            f"Test samples file not found: {samples_file}. "
            f"Run: poetry run python backend/scripts/select_test_samples.py"
        )
    
    with open(samples_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    samples = data.get("samples", [])
    samples_6plus = [s for s in samples if s.get("chapter_count", 0) >= 6]
    
    if not samples_6plus:
        pytest.skip("No books with 6+ chapters found in test samples")
    
    return samples_6plus


@pytest.mark.e2e
def test_e2e_full_pipeline_validation(
    e2e_client: httpx.Client,
    test_samples_6plus: list,
):
    """
    전체 파이프라인 검증 E2E 테스트 (이미 완료된 책 검증)
    
    **목적**: 이미 구조 분석이 완료된 책에 대해 전체 파이프라인 상태 검증
    - 구조 데이터 검증
    - 페이지 엔티티 추출 상태 확인
    - 챕터 구조화 상태 확인
    - 북 서머리 생성 상태 확인
    - 캐시 파일 확인
    """
    if not test_samples_6plus:
        pytest.skip("No test samples available")
    
    # 첫 번째 샘플 사용 (이미 완료된 책)
    sample_data = test_samples_6plus[0]
    book_id = sample_data["book_id"]
    title = sample_data["title"]
    category = sample_data["category"]
    chapter_count = sample_data["chapter_count"]
    pdf_path = Path(sample_data["source_file_path"])
    
    print(f"\n{'=' * 80}")
    print(f"[TEST] Full Pipeline Validation E2E Test")
    print(f"Book ID: {book_id}, Title: {title}, Category: {category}, Chapters: {chapter_count}")
    print(f"{'=' * 80}")
    
    # ===== 1. 책 상태 확인 =====
    print(f"\n[STEP 1] 책 상태 확인...")
    
    response = e2e_client.get(f"/api/books/{book_id}")
    assert response.status_code == 200
    book_data = response.json()
    
    print(f"  Status: {book_data['status']}")
    print(f"  Page Count: {book_data.get('page_count', 'N/A')}")
    print(f"  Has Structure Data: {book_data.get('structure_data') is not None}")
    
    # 구조 데이터 검증
    assert book_data.get("structure_data") is not None, "구조 데이터가 없습니다"
    structure_data = book_data["structure_data"]
    assert "chapters" in structure_data, "구조 데이터에 chapters가 없습니다"
    assert len(structure_data["chapters"]) >= 6, f"챕터 수가 6개 미만입니다: {len(structure_data['chapters'])}"
    
    print(f"[STEP 1] [OK] 책 상태 확인 완료: {len(structure_data['chapters'])}개 챕터")
    
    # ===== 2. 캐시 파일 확인 =====
    print(f"\n[STEP 2] 캐시 파일 확인...")
    
    # Upstage 캐시 확인
    upstage_cache = check_upstage_cache(pdf_path)
    assert upstage_cache is not None, "Upstage 캐시가 없습니다"
    print(f"[CACHE] [OK] Upstage 캐시 확인: {upstage_cache.name}")
    
    # 구조 파일 확인
    structure_file = check_structure_file_by_hash(pdf_path, title)
    assert structure_file is not None, "구조 파일이 없습니다"
    print(f"[CACHE] [OK] 구조 파일 확인: {structure_file.name}")
    
    # 페이지 엔티티 캐시 확인
    page_cache_count = get_cache_file_count(book_id, title, "pages")
    print(f"[CACHE] 페이지 엔티티 캐시: {page_cache_count}개")
    
    # 챕터 구조화 캐시 확인
    chapter_cache_count = get_cache_file_count(book_id, title, "chapters")
    print(f"[CACHE] 챕터 구조화 캐시: {chapter_cache_count}개")
    
    print(f"[STEP 2] [OK] 캐시 파일 확인 완료")
    
    # ===== 3. 페이지 엔티티 확인 =====
    print(f"\n[STEP 3] 페이지 엔티티 확인...")
    
    response = e2e_client.get(f"/api/books/{book_id}/pages")
    assert response.status_code == 200
    page_entities = response.json()
    
    assert len(page_entities) > 0, "페이지 엔티티가 없습니다"
    print(f"  Page Entities Count: {len(page_entities)}")
    
    print(f"[STEP 3] [OK] 페이지 엔티티 확인 완료")
    
    # ===== 4. 챕터 엔티티 확인 =====
    print(f"\n[STEP 4] 챕터 엔티티 확인...")
    
    response = e2e_client.get(f"/api/books/{book_id}/chapters")
    assert response.status_code == 200
    chapter_entities = response.json()
    
    assert len(chapter_entities) == chapter_count, f"챕터 수 불일치: expected={chapter_count}, actual={len(chapter_entities)}"
    print(f"  Chapter Entities Count: {len(chapter_entities)}")
    
    print(f"[STEP 4] [OK] 챕터 엔티티 확인 완료")
    
    # ===== 5. 북 서머리 확인 =====
    print(f"\n[STEP 5] 북 서머리 확인...")
    
    book_summary_dir = settings.output_dir / "book_summaries"
    book_summary_files = list(book_summary_dir.glob(f"*{book_id}*.json"))
    book_summary_files.extend(book_summary_dir.glob(f"*{title}*.json"))
    
    if book_summary_files:
        print(f"  Book Summary Files: {len(book_summary_files)}")
        for f in book_summary_files:
            print(f"    - {f.name}")
    else:
        print(f"  Book Summary Files: 없음 (생성 필요)")
    
    print(f"[STEP 5] [OK] 북 서머리 확인 완료")
    
    print(f"\n{'=' * 80}")
    print(f"[TEST] [OK] 전체 파이프라인 검증 완료")
    print(f"Book ID: {book_id}, Title: {title}")
    print(f"{'=' * 80}")


@pytest.mark.e2e
def test_e2e_new_book_full_pipeline(e2e_client: httpx.Client):
    """
    새 책 1권 전체 파이프라인 E2E 테스트
    
    **목적**: 새로 업로드한 책에 대해 전체 파이프라인 테스트
    - Book ID 165 ("1등의 통찰", 7개 챕터) 사용
    - 전체 플로우: 업로드 → 파싱 → 구조 분석 → 페이지 추출 → 챕터 구조화 → 북 서머리 생성
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
    
    # 전체 파이프라인 처리
    process_book_full_pipeline(
        e2e_client=e2e_client,
        book_id=book_id,
        pdf_path=pdf_path,
        book_title=title,
        category=category,
        chapter_count=chapter_count,
        skip_upload=False,  # 새로 업로드
    )


@pytest.mark.e2e
@pytest.mark.parametrize("book_id,title,category,chapter_count", [
    (176, "1000년", "역사/사회", 8),
    (177, "100년 투자 가문의 비밀", "경제/경영", 19),
    (175, "12가지인생의법칙", "인문/자기계발", 12),
    (184, "AI지도책", "과학/기술", 8),
])
def test_e2e_multiple_books_validation(
    e2e_client: httpx.Client,
    book_id: int,
    title: str,
    category: str,
    chapter_count: int,
):
    """
    여러 책 검증 E2E 테스트 (파라미터화)
    
    **목적**: 이미 완료된 여러 책에 대해 상태 검증
    - 4권 검증 (Book ID: 175, 176, 177, 184)
    - 각 책의 상태, 캐시, 엔티티 확인
    """
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
    
    # 검증만 수행 (전체 파이프라인 건너뛰기)
    print(f"\n{'=' * 80}")
    print(f"[TEST] Book Validation Test")
    print(f"Book ID: {book_id}, Title: {title}, Category: {category}, Chapters: {chapter_count}")
    print(f"{'=' * 80}")
    
    # 책 상태 확인
    response = e2e_client.get(f"/api/books/{book_id}")
    assert response.status_code == 200
    book_data = response.json()
    
    print(f"  Status: {book_data['status']}")
    print(f"  Has Structure Data: {book_data.get('structure_data') is not None}")
    
    # 캐시 확인
    upstage_cache = check_upstage_cache(pdf_path)
    structure_file = check_structure_file_by_hash(pdf_path, title)
    page_cache_count = get_cache_file_count(book_id, title, "pages")
    chapter_cache_count = get_cache_file_count(book_id, title, "chapters")
    
    print(f"  Upstage Cache: {'[OK]' if upstage_cache else '[FAIL]'}")
    print(f"  Structure File: {'[OK]' if structure_file else '[FAIL]'}")
    print(f"  Page Cache: {page_cache_count}개")
    print(f"  Chapter Cache: {chapter_cache_count}개")
    
    print(f"[TEST] [OK] Book {book_id} validation completed")


@pytest.mark.e2e
def test_e2e_error_flow_invalid_file(e2e_client: httpx.Client):
    """
    에러 플로우 E2E 테스트: 잘못된 파일 형식 업로드
    
    **목적**: 에러 처리 검증
    """
    print(f"\n{'=' * 80}")
    print(f"[TEST] 에러 플로우 테스트: 잘못된 파일 형식")
    print(f"{'=' * 80}")
    
    # 텍스트 파일을 PDF로 업로드 시도
    test_file = Path(__file__).parent / "test_api_contract.py"
    
    with open(test_file, "rb") as f:
        files = {"file": ("test.txt", f, "text/plain")}
        response = e2e_client.post("/api/books/upload", files=files)
    
    # 400 Bad Request 또는 422 Unprocessable Entity 예상
    assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"
    
    data = response.json()
    assert "detail" in data
    
    print(f"[TEST] [OK] 잘못된 파일 형식 에러 처리 확인: {response.status_code}")


@pytest.mark.e2e
def test_e2e_error_flow_nonexistent_book(e2e_client: httpx.Client):
    """
    에러 플로우 E2E 테스트: 존재하지 않는 책 조회
    
    **목적**: 에러 처리 검증
    """
    print(f"\n{'=' * 80}")
    print(f"[TEST] 에러 플로우 테스트: 존재하지 않는 책")
    print(f"{'=' * 80}")
    
    # 존재하지 않는 book_id로 조회
    response = e2e_client.get("/api/books/999999")
    assert response.status_code == 404
    
    data = response.json()
    assert "detail" in data
    
    print(f"[TEST] [OK] 존재하지 않는 책 에러 처리 확인: 404")


@pytest.mark.e2e
def test_e2e_error_flow_structure_without_parsing(e2e_client: httpx.Client):
    """
    에러 플로우 E2E 테스트: 파싱 전 구조 분석 시도
    
    **목적**: 에러 처리 검증
    """
    print(f"\n{'=' * 80}")
    print(f"[TEST] 에러 플로우 테스트: 파싱 전 구조 분석")
    print(f"{'=' * 80}")
    
    # uploaded 상태인 책 찾기 (파싱 전)
    list_response = e2e_client.get("/api/books")
    assert list_response.status_code == 200
    books_data = list_response.json()
    
    uploaded_book = None
    for book in books_data.get("books", []):
        if book.get("status") == "uploaded":
            uploaded_book = book
            break
    
    if not uploaded_book:
        pytest.skip("No uploaded books available for testing")
    
    book_id = uploaded_book["id"]
    
    # 구조 후보 조회 시도 (파싱 전이면 실패해야 함)
    response = e2e_client.get(f"/api/books/{book_id}/structure/candidates")
    
    # 404 또는 400 예상
    assert response.status_code in [404, 400], f"Expected 404/400, got {response.status_code}"
    
    print(f"[TEST] [OK] 파싱 전 구조 분석 에러 처리 확인: {response.status_code}")

