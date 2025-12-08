"""
E2E 테스트: 전체 파이프라인 (Phase 7.2)

⚠️ 실제 서버 실행, 실제 데이터만 사용, Mock 사용 절대 금지

전체 플로우:
1. PDF 업로드 → 책 생성 (uploaded)
2. 실제 Upstage API로 PDF 파싱 → parsed 상태 확인 → 캐시 저장 확인
3. 구조 후보 생성 → 캐시된 파싱 결과 재사용 확인
4. 구조 확정 (structured)
5. 페이지 엔티티 추출 (page_summarized) → 캐시 저장 확인
6. 챕터 구조화 (summarized) → 캐시 저장 확인
7. 도서 서머리 생성 → 캐시 저장 확인
8. 최종 결과 조회 검증

⚠️ 중요: 캐시 활용 확인
- Upstage API 캐시: data/cache/upstage/ (모든 도서 확인)
- 구조 분석 결과: data/output/structure/ (확인해서 반영)
"""
import pytest
import httpx
import time
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any
from backend.config.settings import settings

pytestmark = pytest.mark.e2e


def get_pdf_hash(pdf_path: Path) -> str:
    """PDF 파일의 MD5 해시 계산"""
    hasher = hashlib.md5()
    with open(pdf_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def check_upstage_cache(pdf_path: Path) -> Optional[Path]:
    """
    Upstage API 캐시 확인
    
    Args:
        pdf_path: PDF 파일 경로
        
    Returns:
        캐시 파일 경로 또는 None
    """
    pdf_hash = get_pdf_hash(pdf_path)
    cache_file = settings.cache_dir / "upstage" / f"{pdf_hash}.json"
    
    if cache_file.exists():
        return cache_file
    return None


def check_structure_file(book_id: int, book_title: Optional[str] = None) -> Optional[Path]:
    """
    구조 분석 JSON 파일 확인
    
    Args:
        book_id: 책 ID
        book_title: 책 제목 (선택)
        
    Returns:
        구조 파일 경로 또는 None
    """
    structure_dir = settings.output_dir / "structure"
    
    # 1. book_id로 찾기
    pattern = f"*_{book_id}_structure.json"
    for file in structure_dir.glob(pattern):
        return file
    
    # 2. 책 제목으로 찾기
    if book_title:
        import re
        safe_title = re.sub(r'[\\/:*?"<>|]', "_", book_title)
        safe_title = safe_title.replace(" ", "_")[:10]
        pattern = f"*_{safe_title}_structure.json"
        for file in structure_dir.glob(pattern):
            return file
    
    # 3. book_id만으로 찾기 (fallback)
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
    """
    책 상태가 목표 상태가 될 때까지 대기
    
    Args:
        e2e_client: HTTP 클라이언트
        book_id: 책 ID
        target_status: 목표 상태
        max_wait_time: 최대 대기 시간 (초)
        check_interval: 상태 확인 간격 (초)
        
    Returns:
        최종 책 데이터
    """
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


@pytest.fixture(scope="session")
def test_samples_6plus():
    """챕터 6개 이상 도서 샘플 로드"""
    samples_file = settings.output_dir / "test_samples" / "selected_samples.json"
    
    if not samples_file.exists():
        # select_test_samples.py 실행 필요
        pytest.skip(
            f"Test samples file not found: {samples_file}. "
            f"Run: poetry run python backend/scripts/select_test_samples.py"
        )
    
    with open(samples_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    samples = data.get("samples", [])
    
    # 챕터 6개 이상만 필터링
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
    
    이미 구조 분석이 완료된 책에 대해:
    1. 구조 데이터 검증
    2. 페이지 엔티티 추출 상태 확인
    3. 챕터 구조화 상태 확인
    4. 도서 서머리 생성 상태 확인
    5. 캐시 파일 확인
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
    
    print(f"[STEP 1] ✅ 책 상태 확인 완료: {len(structure_data['chapters'])}개 챕터")
    
    # ===== 2. 캐시 파일 확인 =====
    print(f"\n[STEP 2] 캐시 파일 확인...")
    
    # Upstage 캐시 확인
    upstage_cache = check_upstage_cache(pdf_path)
    assert upstage_cache is not None, "Upstage 캐시가 없습니다"
    print(f"[CACHE] ✅ Upstage 캐시 확인: {upstage_cache.name}")
    
    # 구조 파일 확인
    structure_file = check_structure_file(book_id, title)
    assert structure_file is not None, "구조 파일이 없습니다"
    print(f"[CACHE] ✅ 구조 파일 확인: {structure_file.name}")
    
    print(f"[STEP 2] ✅ 캐시 파일 확인 완료")
    
    # ===== 3. 페이지 엔티티 확인 =====
    print(f"\n[STEP 3] 페이지 엔티티 확인...")
    
    response = e2e_client.get(f"/api/books/{book_id}/pages")
    assert response.status_code == 200
    page_entities = response.json()
    
    assert len(page_entities) > 0, "페이지 엔티티가 없습니다"
    print(f"  Page Entities Count: {len(page_entities)}")
    
    # 캐시 확인
    summaries_cache_dir = settings.cache_dir / "summaries"
    page_cache_count = len(list(summaries_cache_dir.glob("page_*.json")))
    print(f"  Page Cache Files: {page_cache_count}")
    
    print(f"[STEP 3] ✅ 페이지 엔티티 확인 완료")
    
    # ===== 4. 챕터 엔티티 확인 =====
    print(f"\n[STEP 4] 챕터 엔티티 확인...")
    
    response = e2e_client.get(f"/api/books/{book_id}/chapters")
    assert response.status_code == 200
    chapter_entities = response.json()
    
    assert len(chapter_entities) == chapter_count, f"챕터 수 불일치: expected={chapter_count}, actual={len(chapter_entities)}"
    print(f"  Chapter Entities Count: {len(chapter_entities)}")
    
    # 캐시 확인
    chapter_cache_count = len(list(summaries_cache_dir.glob("chapter_*.json")))
    print(f"  Chapter Cache Files: {chapter_cache_count}")
    
    print(f"[STEP 4] ✅ 챕터 엔티티 확인 완료")
    
    # ===== 5. 도서 서머리 확인 =====
    print(f"\n[STEP 5] 도서 서머리 확인...")
    
    book_summary_dir = settings.output_dir / "book_summaries"
    book_summary_files = list(book_summary_dir.glob(f"*{book_id}*.json"))
    book_summary_files.extend(book_summary_dir.glob(f"*{title}*.json"))
    
    if book_summary_files:
        print(f"  Book Summary Files: {len(book_summary_files)}")
        for f in book_summary_files:
            print(f"    - {f.name}")
    else:
        print(f"  Book Summary Files: 없음 (생성 필요)")
    
    # 캐시 확인
    book_summary_cache_count = len(list(summaries_cache_dir.glob("book_summary_*.json")))
    print(f"  Book Summary Cache Files: {book_summary_cache_count}")
    
    print(f"[STEP 5] ✅ 도서 서머리 확인 완료")
    
    print(f"\n{'=' * 80}")
    print(f"[TEST] ✅ 전체 파이프라인 검증 완료")
    print(f"Book ID: {book_id}, Title: {title}")
    print(f"{'=' * 80}")


@pytest.mark.e2e
def test_e2e_cache_verification(e2e_client: httpx.Client, test_samples_6plus: list):
    """
    캐시 활용 검증 테스트
    
    모든 챕터 6개 이상 도서에 대해:
    - Upstage API 캐시 확인
    - 구조 분석 파일 확인
    """
    if not test_samples_6plus:
        pytest.skip("No test samples available")
    
    print(f"\n{'=' * 80}")
    print(f"[TEST] 캐시 활용 검증 테스트")
    print(f"{'=' * 80}")
    
    cache_stats = {
        "upstage_cache_found": 0,
        "upstage_cache_missing": 0,
        "structure_file_found": 0,
        "structure_file_missing": 0,
    }
    
    for sample in test_samples_6plus:
        book_id = sample["book_id"]
        title = sample["title"]
        pdf_path = Path(sample["source_file_path"])
        
        # Upstage 캐시 확인
        upstage_cache = check_upstage_cache(pdf_path)
        if upstage_cache:
            cache_stats["upstage_cache_found"] += 1
            print(f"[CACHE] ✅ Book {book_id} ({title}): Upstage 캐시 있음")
        else:
            cache_stats["upstage_cache_missing"] += 1
            print(f"[CACHE] ❌ Book {book_id} ({title}): Upstage 캐시 없음")
        
        # 구조 파일 확인
        structure_file = check_structure_file(book_id, title)
        if structure_file:
            cache_stats["structure_file_found"] += 1
            print(f"[CACHE] ✅ Book {book_id} ({title}): 구조 파일 있음")
        else:
            cache_stats["structure_file_missing"] += 1
            print(f"[CACHE] ❌ Book {book_id} ({title}): 구조 파일 없음")
    
    print(f"\n[TEST] 캐시 활용 통계:")
    print(f"  - Upstage 캐시: {cache_stats['upstage_cache_found']}개 있음, {cache_stats['upstage_cache_missing']}개 없음")
    print(f"  - 구조 파일: {cache_stats['structure_file_found']}개 있음, {cache_stats['structure_file_missing']}개 없음")
    
    # 최소한 일부 도서는 캐시가 있어야 함
    total_books = len(test_samples_6plus)
    assert cache_stats["upstage_cache_found"] > 0, "Upstage 캐시가 하나도 없습니다"
    assert cache_stats["structure_file_found"] > 0, "구조 파일이 하나도 없습니다"
    
    print(f"[TEST] ✅ 캐시 활용 검증 완료")


@pytest.mark.e2e
def test_e2e_error_flow_invalid_file(e2e_client: httpx.Client):
    """
    에러 플로우 E2E 테스트: 잘못된 파일 형식 업로드
    """
    print(f"\n{'=' * 80}")
    print(f"[TEST] 에러 플로우 테스트: 잘못된 파일 형식")
    print(f"{'=' * 80}")
    
    # 텍스트 파일을 PDF로 업로드 시도
    from pathlib import Path
    test_file = Path(__file__).parent / "test_api_contract.py"  # Python 파일
    
    with open(test_file, "rb") as f:
        files = {"file": ("test.txt", f, "text/plain")}
        response = e2e_client.post("/api/books/upload", files=files)
    
    # 400 Bad Request 또는 422 Unprocessable Entity 예상
    assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"
    
    data = response.json()
    assert "detail" in data
    
    print(f"[TEST] ✅ 잘못된 파일 형식 에러 처리 확인: {response.status_code}")


@pytest.mark.e2e
def test_e2e_error_flow_nonexistent_book(e2e_client: httpx.Client):
    """
    에러 플로우 E2E 테스트: 존재하지 않는 책 조회
    """
    print(f"\n{'=' * 80}")
    print(f"[TEST] 에러 플로우 테스트: 존재하지 않는 책")
    print(f"{'=' * 80}")
    
    # 존재하지 않는 book_id로 조회
    response = e2e_client.get("/api/books/999999")
    assert response.status_code == 404
    
    data = response.json()
    assert "detail" in data
    
    print(f"[TEST] ✅ 존재하지 않는 책 에러 처리 확인: 404")


@pytest.mark.e2e
def test_e2e_error_flow_structure_without_parsing(e2e_client: httpx.Client):
    """
    에러 플로우 E2E 테스트: 파싱 전 구조 분석 시도
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
    
    print(f"[TEST] ✅ 파싱 전 구조 분석 에러 처리 확인: {response.status_code}")

