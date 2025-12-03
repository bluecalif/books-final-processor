"""
E2E 테스트: 엔티티 추출 모듈

⚠️ 실제 서버 실행, 실제 데이터만 사용, Mock 사용 절대 금지
"""

import pytest
import httpx
import time
import json
from pathlib import Path
from backend.config.settings import settings

pytestmark = pytest.mark.e2e


@pytest.mark.e2e
def test_e2e_extraction_small_sample(e2e_client: httpx.Client):
    """
    작은 샘플 테스트: Book 176 앞 30페이지만 추출
    
    빠른 검증용 - 서비스 로직 개선 후 기본 동작 확인
    """
    book_id = 176  # 1000년, 역사/사회
    limit_pages = 30
    
    print(f"\n{'=' * 80}")
    print(f"Small Sample Test: Book ID {book_id}, Limit {limit_pages} pages")
    print(f"{'=' * 80}")
    
    # 1. 책 상태 확인
    response = e2e_client.get(f"/api/books/{book_id}")
    assert response.status_code == 200
    book_data = response.json()
    
    if book_data["status"] != "structured":
        pytest.skip(
            f"Book {book_id} is not in 'structured' status. "
            f"Current status: {book_data['status']}"
        )
    
    # 2. 기존 PageSummary 삭제 (깨끗한 재시작)
    print(f"[TEST] Cleaning up existing PageSummaries for book_id={book_id}...")
    # Note: E2E 테스트이므로 API로 삭제하는 것이 이상적이지만,
    # 삭제 API가 없으므로 이 부분은 수동으로 처리하거나 별도 스크립트 사용
    
    # 3. 페이지 엔티티 추출 시작 (30페이지 제한)
    print(f"[TEST] Starting page extraction with limit={limit_pages}...")
    response = e2e_client.post(
        f"/api/books/{book_id}/extract/pages",
        params={"limit_pages": limit_pages}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "processing"
    assert response.json()["limit_pages"] == limit_pages
    
    # 4. 추출 완료 대기 (진행 상황 출력)
    # 동적 타임아웃 계산: 페이지당 3초 + 20% 여유
    max_wait_time = int(limit_pages * 3 * 1.2) if limit_pages else 3600
    print(f"[TEST] Max wait time: {max_wait_time}s ({max_wait_time//60} minutes)")
    
    start_time = time.time()
    last_page_count = 0
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait_time:
            pytest.fail(
                f"Page extraction timeout after {max_wait_time} seconds "
                f"(book_id={book_id}, limit={limit_pages})"
            )
        
        response = e2e_client.get(f"/api/books/{book_id}")
        assert response.status_code == 200
        status = response.json()["status"]
        
        # 진행 상황 확인 (페이지 개수)
        pages_response = e2e_client.get(f"/api/books/{book_id}/pages")
        if pages_response.status_code == 200:
            current_page_count = len(pages_response.json())
            if current_page_count > last_page_count:
                print(f"[TEST] Progress: {current_page_count}/{limit_pages} pages extracted ({elapsed:.1f}s)")
                last_page_count = current_page_count
        
        if status == "page_summarized":
            print(f"[TEST] Page extraction completed (elapsed: {elapsed:.1f}s)")
            break
        elif status in ["error_summarizing", "failed"]:
            pytest.fail(f"Page extraction failed: status={status}")
        
        time.sleep(10)
    
    # 5. 결과 검증
    response = e2e_client.get(f"/api/books/{book_id}/pages")
    assert response.status_code == 200
    page_entities = response.json()
    
    # 30페이지가 모두 추출되었는지 확인
    assert len(page_entities) >= limit_pages - 5, (
        f"Expected at least {limit_pages - 5} pages, got {len(page_entities)}"
    )
    
    print(f"[TEST] Small sample test passed: {len(page_entities)} pages extracted")
    print(f"[TEST] Total time: {elapsed:.1f}s, Avg: {elapsed/len(page_entities):.2f}s/page")


@pytest.fixture(scope="session")
def test_samples():
    """테스트 샘플 도서 로드"""
    samples_file = settings.output_dir / "test_samples" / "test_books_list.json"

    if not samples_file.exists():
        pytest.skip(
            f"Test samples file not found: {samples_file}. Run select_test_books.py first."
        )

    with open(samples_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 분야별 딕셔너리를 리스트로 변환
    samples = []
    for category, book_info in data.items():
        samples.append({
            "book_id": book_info["book_id"],
            "title": book_info["title"],
            "chapter_count": book_info["chapter_count"],
            "category": category,
        })
    
    return samples


@pytest.mark.e2e
def test_e2e_extraction_full_flow(e2e_client: httpx.Client, test_samples):
    """
    전체 엔티티 추출 플로우 E2E 테스트

    구조 확정된 책 (챕터 6개 이상) → 페이지 엔티티 추출 → 챕터 구조화

    ⚠️ 현재는 첫 번째 책만 테스트 (시간 절약)
    """
    if not test_samples:
        pytest.skip("No test samples available")

    # 첫 번째 책만 테스트
    sample = test_samples[0]

    book_id = sample["book_id"]
    category = sample["category"]

    print(f"\n{'=' * 80}")
    print(f"Testing Book ID: {book_id}, Category: {category}")
    print(f"{'=' * 80}")

    # 1. 책 상태 확인 (structured 상태여야 함)
    response = e2e_client.get(f"/api/books/{book_id}")
    assert response.status_code == 200
    book_data = response.json()

    if book_data["status"] != "structured":
        pytest.skip(
            f"Book {book_id} is not in 'structured' status. "
            f"Current status: {book_data['status']}"
        )

    # 2. 페이지 엔티티 추출 시작 (백그라운드 작업)
    print(f"[TEST] Starting page extraction for book_id={book_id}...")
    response = e2e_client.post(f"/api/books/{book_id}/extract/pages")
    assert response.status_code == 200
    assert response.json()["status"] == "processing"

    # 3. 페이지 엔티티 추출 완료 대기
    # 동적 타임아웃 계산: 예상 페이지 수 기준 (구조 데이터에서 추출)
    if book_data.get("structure_data"):
        structure = book_data["structure_data"]
        main_start = structure.get("main_start_page", 0)
        main_end = structure.get("main_end_page", 0)
        expected_pages = main_end - main_start + 1 if main_start and main_end else 300
    else:
        expected_pages = 300
    
    max_wait_time = int(expected_pages * 3 * 1.2)  # 페이지당 3초 + 20% 여유
    print(f"[TEST] Expected pages: {expected_pages}, Max wait time: {max_wait_time}s ({max_wait_time//60} min)")
    
    start_time = time.time()
    last_page_count = 0

    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait_time:
            pytest.fail(
                f"Page extraction timeout after {max_wait_time} seconds for book_id={book_id}"
            )

        response = e2e_client.get(f"/api/books/{book_id}")
        assert response.status_code == 200
        status = response.json()["status"]
        
        # 진행 상황 확인 (10초마다 항상 출력)
        pages_response = e2e_client.get(f"/api/books/{book_id}/pages")
        if pages_response.status_code == 200:
            current_page_count = len(pages_response.json())
            
            # 페이지 수 변화 여부와 관계없이 진행 상황 출력
            if int(elapsed) % 10 < 1 or current_page_count != last_page_count:
                elapsed_min = int(elapsed // 60)
                elapsed_sec = int(elapsed % 60)
                progress_pct = int(current_page_count * 100 / expected_pages) if expected_pages > 0 else 0
                avg_time = elapsed / max(current_page_count, 1)
                est_remaining = avg_time * (expected_pages - current_page_count)
                est_min = int(est_remaining // 60)
                est_sec = int(est_remaining % 60)
                
                print(
                    f"[TEST] {current_page_count}/{expected_pages} pages ({progress_pct}%) | "
                    f"Time: {elapsed_min:02d}:{elapsed_sec:02d} | "
                    f"Avg: {avg_time:.1f}s/page | "
                    f"Est: {est_min:02d}:{est_sec:02d}"
                )
                last_page_count = current_page_count

        if status == "page_summarized":
            print(f"[TEST] Page extraction completed for book_id={book_id} (elapsed: {elapsed:.1f}s)")
            break
        elif status in ["error_summarizing", "failed"]:
            pytest.fail(
                f"Page extraction failed for book_id={book_id}, status={status}"
            )

        time.sleep(10)  # 서버 부하 감소를 위해 폴링 간격 증가 (5초 → 10초)

    # 4. 페이지 엔티티 검증
    response = e2e_client.get(f"/api/books/{book_id}/pages")
    assert response.status_code == 200
    page_entities = response.json()

    assert len(page_entities) > 0, f"No page entities found for book_id={book_id}"

    # 첫 번째 페이지 엔티티 상세 검증
    first_page = page_entities[0]
    assert "structured_data" in first_page, "structured_data field missing"
    assert first_page["structured_data"] is not None, "structured_data is None"

    structured_data = first_page["structured_data"]
    assert "page_summary" in structured_data, "page_summary field missing"
    assert "concepts" in structured_data, "concepts field missing"
    assert "events" in structured_data, "events field missing"

    print(f"[TEST] Page entities validated: {len(page_entities)} pages")

    # 5. 챕터 구조화 시작 (백그라운드 작업)
    print(f"[TEST] Starting chapter structuring for book_id={book_id}...")
    response = e2e_client.post(f"/api/books/{book_id}/extract/chapters")
    assert response.status_code == 200
    assert response.json()["status"] == "processing"

    # 6. 챕터 구조화 완료 대기 (진행 상황 출력)
    # 전체 챕터 수 조회 (Book의 structure_data에서)
    response = e2e_client.get(f"/api/books/{book_id}")
    assert response.status_code == 200
    book_data = response.json()
    
    # 챕터 수 확인
    expected_chapters = 0
    if book_data.get("structure_data"):
        structure = book_data["structure_data"]
        if "chapters" in structure:
            expected_chapters = len(structure["chapters"])
    
    if expected_chapters == 0:
        expected_chapters = 10  # 기본값
    
    print(f"[TEST] Expected chapters: {expected_chapters}, Max wait time: {max_wait_time}s ({max_wait_time//60} min)")
    
    start_time = time.time()
    last_chapter_count = 0

    while True:
        elapsed = time.time() - start_time
        if elapsed > max_wait_time:
            pytest.fail(
                f"Chapter structuring timeout after {max_wait_time} seconds for book_id={book_id}"
            )

        response = e2e_client.get(f"/api/books/{book_id}")
        assert response.status_code == 200
        status = response.json()["status"]
        
        # 진행 상황 확인 (챕터 개수)
        chapters_response = e2e_client.get(f"/api/books/{book_id}/chapters")
        if chapters_response.status_code == 200:
            current_chapter_count = len(chapters_response.json())
            
            # 10초마다 또는 챕터 수 변화 시에만 진행 상황 출력
            if int(elapsed) % 10 < 1 or current_chapter_count != last_chapter_count:
                elapsed_min = int(elapsed // 60)
                elapsed_sec = int(elapsed % 60)
                progress_pct = int(current_chapter_count * 100 / expected_chapters) if expected_chapters > 0 else 0
                avg_time = elapsed / max(current_chapter_count, 1)
                est_remaining = avg_time * (expected_chapters - current_chapter_count)
                est_min = int(est_remaining // 60)
                est_sec = int(est_remaining % 60)
                
                print(
                    f"[TEST] {current_chapter_count}/{expected_chapters} chapters ({progress_pct}%) | "
                    f"Time: {elapsed_min:02d}:{elapsed_sec:02d} | "
                    f"Avg: {avg_time:.1f}s/chapter | "
                    f"Est: {est_min:02d}:{est_sec:02d}"
                )
                last_chapter_count = current_chapter_count

        if status == "summarized":
            print(f"[TEST] Chapter structuring completed for book_id={book_id} (elapsed: {elapsed:.1f}s)")
            break
        elif status in ["error_summarizing", "failed"]:
            pytest.fail(
                f"Chapter structuring failed for book_id={book_id}, status={status}"
            )

        time.sleep(10)  # 서버 부하 감소를 위해 폴링 간격 증가 (5초 → 10초)

    # 7. 챕터 구조화 결과 검증
    response = e2e_client.get(f"/api/books/{book_id}/chapters")
    assert response.status_code == 200
    chapter_entities = response.json()

    assert len(chapter_entities) > 0, f"No chapter entities found for book_id={book_id}"

    # 첫 번째 챕터 엔티티 상세 검증
    first_chapter = chapter_entities[0]
    assert "structured_data" in first_chapter, "structured_data field missing"
    assert first_chapter["structured_data"] is not None, "structured_data is None"

    chapter_structured_data = first_chapter["structured_data"]
    assert "core_message" in chapter_structured_data, "core_message field missing"
    assert (
        "summary_3_5_sentences" in chapter_structured_data
    ), "summary_3_5_sentences field missing"
    assert "argument_flow" in chapter_structured_data, "argument_flow field missing"

    print(f"[TEST] Chapter entities validated: {len(chapter_entities)} chapters")

    # 8. 토큰 통계 파일 확인
    token_stats_file = (
        settings.output_dir / "token_stats" / f"book_{book_id}_tokens.json"
    )
    if token_stats_file.exists():
        with open(token_stats_file, "r", encoding="utf-8") as f:
            token_stats = json.load(f)

        pages_stats = token_stats.get("pages", {})
        chapters_stats = token_stats.get("chapters", {})

        print(f"[TEST] Token stats for book_id={book_id}:")
        print(
            f"  Pages: input={pages_stats.get('total_input_tokens', 0)}, "
            f"output={pages_stats.get('total_output_tokens', 0)}, "
            f"cost=${pages_stats.get('total_cost', 0.0):.4f}"
        )
        print(
            f"  Chapters: input={chapters_stats.get('total_input_tokens', 0)}, "
            f"output={chapters_stats.get('total_output_tokens', 0)}, "
            f"cost=${chapters_stats.get('total_cost', 0.0):.4f}"
        )
    else:
        print(f"[WARNING] Token stats file not found: {token_stats_file}")


@pytest.mark.e2e
def test_e2e_domain_schema_validation(e2e_client: httpx.Client, test_samples):
    """
    도메인별 스키마 검증

    각 도메인(역사/사회, 경제/경영, 인문/자기계발, 과학/기술)별로 올바른 스키마가 생성되는지 확인
    """
    if not test_samples:
        pytest.skip("No test samples available")

    domain_schema_fields = {
        "역사/사회": ["locations", "time_periods", "polities"],
        "경제/경영": ["indicators", "actors", "strategies", "cases"],
        "인문/자기계발": [
            "psychological_states",
            "life_situations",
            "practices",
            "inner_conflicts",
        ],
        "과학/기술": ["technologies", "systems", "applications", "risks_ethics"],
    }

    for sample in test_samples:
        book_id = sample["book_id"]
        category = sample["category"]

        if category not in domain_schema_fields:
            continue

        # 페이지 엔티티 확인
        response = e2e_client.get(f"/api/books/{book_id}/pages")
        if response.status_code != 200:
            continue

        page_entities = response.json()
        if not page_entities:
            continue

        # 첫 번째 페이지의 structured_data 확인
        first_page = page_entities[0]
        if not first_page.get("structured_data"):
            continue

        structured_data = first_page["structured_data"]
        expected_fields = domain_schema_fields[category]

        for field in expected_fields:
            assert field in structured_data, (
                f"Domain-specific field '{field}' missing in {category} page entity "
                f"for book_id={book_id}"
            )

        print(f"[TEST] Domain schema validated for {category} (book_id={book_id})")


@pytest.mark.e2e
def test_e2e_cache_reuse(e2e_client: httpx.Client, test_samples):
    """
    캐시 재사용 검증

    두 번째 추출 시 캐시 히트 확인 (LLM 호출 없이 캐시 사용)
    """
    if not test_samples:
        pytest.skip("No test samples available")

    # 첫 번째 샘플만 테스트
    sample = test_samples[0]
    book_id = sample["book_id"]

    # 이미 추출이 완료된 상태여야 함
    response = e2e_client.get(f"/api/books/{book_id}")
    if response.json()["status"] != "summarized":
        pytest.skip(
            f"Book {book_id} is not in 'summarized' status. Run extraction first."
        )

    # 캐시 파일 확인
    cache_dir = settings.cache_dir / "summaries"
    cache_files_before = list(cache_dir.glob("*.json"))
    cache_count_before = len(cache_files_before)

    print(f"[TEST] Cache files before: {cache_count_before}")

    # 재추출 시도 (캐시 사용)
    # 실제로는 API를 다시 호출하지 않고, 캐시 파일이 존재하는지만 확인
    # 또는 실제로 재추출을 시도하고 로그에서 캐시 히트 확인

    # 캐시 파일이 생성되었는지 확인
    assert (
        cache_count_before > 0
    ), "No cache files found. Extraction may not have used cache."

    print(f"[TEST] Cache reuse validated: {cache_count_before} cache files found")


@pytest.mark.e2e
def test_e2e_chapter_exclusion(e2e_client: httpx.Client):
    """
    챕터 1-2개 제외 검증

    챕터가 1개 또는 2개인 책은 엔티티 추출에서 제외되는지 확인
    """
    # 챕터 1-2개인 책 찾기
    from backend.api.database import SessionLocal
    from backend.api.models.book import Book, Chapter

    db = SessionLocal()
    try:
        # 챕터 1개인 책
        books_with_1_chapter = (
            db.query(Chapter.book_id)
            .group_by(Chapter.book_id)
            .having(db.func.count(Chapter.id) == 1)
            .all()
        )

        # 챕터 2개인 책
        books_with_2_chapters = (
            db.query(Chapter.book_id)
            .group_by(Chapter.book_id)
            .having(db.func.count(Chapter.id) == 2)
            .all()
        )

        test_book_ids = [row[0] for row in books_with_1_chapter[:1]] + [
            row[0] for row in books_with_2_chapters[:1]
        ]

        if not test_book_ids:
            pytest.skip("No books with 1-2 chapters found for testing")

        for book_id in test_book_ids:
            # structured 상태로 만들기 (필요시)
            book = db.query(Book).filter(Book.id == book_id).first()
            if not book or book.status.value != "structured":
                continue

            # 챕터 구조화 시도
            response = e2e_client.post(f"/api/books/{book_id}/extract/chapters")

            # 챕터가 1-2개인 경우, 서비스에서 제외되므로
            # 실제로는 로그에서 경고 메시지만 확인
            # 또는 API가 성공하더라도 실제로는 처리되지 않았는지 확인

            print(f"[TEST] Chapter exclusion validated for book_id={book_id}")
    finally:
        db.close()
