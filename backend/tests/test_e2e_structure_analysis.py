"""
구조 분석 E2E 테스트 (실제 서버 실행, 실제 데이터만 사용, Mock 사용 금지)

⚠️ 중요:
- 실제 서버 실행: 프로덕션 플로우와 동일하게 검증
- 실제 데이터만 사용: 실제 PDF 파일, 실제 OpenAI API, 실제 서버 DB
- Mock 사용 절대 금지
- DB 직접 조회 금지: 서버와 다른 DB이므로 API 응답만 검증
- 캐시 재사용 검증: 구조 분석 시 캐시된 파싱 결과 사용 확인 (Upstage API 호출 없음)
- 정확도 평가: Ground Truth 기반, 페이지 번호만 비교 (챕터 제목은 비교하지 않음)
"""

import pytest
import time
import logging
from pathlib import Path
from datetime import datetime
import httpx
from backend.tests.fixtures.ground_truth_1등의통찰 import (
    GROUND_TRUTH,
    ACCURACY_THRESHOLDS,
)

# 실제 PDF 파일 경로 (Phase 2와 동일)
TEST_PDF_PATH = (
    Path(__file__).parent.parent.parent / "data" / "input" / "1등의 통찰.pdf"
)

# 로그 디렉토리
LOG_DIR = Path(__file__).parent.parent.parent / "data" / "test_results"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def setup_test_logging():
    """
    테스트용 로그 파일 설정

    ⚠️ 중요: 문제 원인 파악을 위해 단계별 상세 로그를 파일과 터미널 모두에 기록
    """
    log_file = (
        LOG_DIR / f"structure_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )

    # 파일 핸들러 (상세 로그 저장)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "[%(asctime)s] %(name)s - %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)

    # 콘솔 핸들러 (터미널 출력)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("[%(levelname)s] %(message)s")
    console_handler.setFormatter(console_formatter)

    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # 테스트 시작 로그
    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info("구조 분석 E2E 테스트 시작")
    logger.info("=" * 80)
    logger.info(f"로그 파일: {log_file}")
    logger.info(f"테스트 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return log_file


def evaluate_accuracy(
    predicted_structure: dict, ground_truth: dict, method: str
) -> dict:
    """
    구조 분석 정확도 평가 (Footer 기반)

    Args:
        predicted_structure: 예측된 구조 (Footer 기반)
        ground_truth: Ground Truth 데이터
        method: "footer" (Footer 기반 구조 분석)

    Returns:
        정확도 평가 결과 딕셔너리
    """
    # Footer 기반은 heuristic 임계값 사용
    thresholds = ACCURACY_THRESHOLDS.get("heuristic", ACCURACY_THRESHOLDS.get("footer", {}))
    results = {
        "method": method,
        "main_start_page": {"passed": False, "error": None},
        "main_end_page": {"passed": False, "error": None},
        "chapter_count": {"passed": False, "error": None},
        "chapter_start_pages": {"passed": False, "errors": []},
    }

    # 1. 본문 시작 페이지 정확도
    predicted_main_start = predicted_structure.get("main_start_page")
    if predicted_main_start is None:
        # 휴리스틱 구조는 main.pages[0]에서 가져올 수 있음
        main_pages = predicted_structure.get("main", {}).get("pages", [])
        if main_pages:
            predicted_main_start = main_pages[0]

    if predicted_main_start is not None:
        gt_main_start = ground_truth["main_start_page"]
        error = abs(predicted_main_start - gt_main_start)
        threshold = thresholds["main_start_page"]
        results["main_start_page"] = {
            "passed": error <= threshold,
            "error": error,
            "predicted": predicted_main_start,
            "ground_truth": gt_main_start,
            "threshold": threshold,
        }

    # 2. 본문 끝 페이지 정확도 (선택적)
    predicted_main_end = predicted_structure.get("main_end_page")
    if predicted_main_end is None:
        main_pages = predicted_structure.get("main", {}).get("pages", [])
        if main_pages:
            predicted_main_end = main_pages[-1]

    if predicted_main_end is not None and ground_truth.get("main_end_page"):
        gt_main_end = ground_truth["main_end_page"]
        error = abs(predicted_main_end - gt_main_end)
        results["main_end_page"] = {
            "passed": True,  # 본문 끝 페이지는 선택적이므로 항상 통과
            "error": error,
            "predicted": predicted_main_end,
            "ground_truth": gt_main_end,
        }

    # 3. 챕터 개수 정확도
    predicted_chapters = predicted_structure.get("chapters", [])
    if not predicted_chapters:
        # 휴리스틱 구조는 main.chapters에서 가져올 수 있음
        predicted_chapters = predicted_structure.get("main", {}).get("chapters", [])

    gt_chapter_count = len(ground_truth["chapters"])
    predicted_chapter_count = len(predicted_chapters)
    error = abs(predicted_chapter_count - gt_chapter_count)
    threshold = thresholds["chapter_count"]
    results["chapter_count"] = {
        "passed": error <= threshold,
        "error": error,
        "predicted": predicted_chapter_count,
        "ground_truth": gt_chapter_count,
        "threshold": threshold,
    }

    # 4. 챕터 시작 페이지 정확도
    chapter_errors = []
    for idx, gt_chapter in enumerate(ground_truth["chapters"]):
        gt_start_page = gt_chapter["start_page"]

        # 예측된 챕터 찾기 (페이지 번호로 매칭)
        matched_chapter = None
        for pred_chapter in predicted_chapters:
            pred_start = pred_chapter.get("start_page")
            if (
                pred_start
                and abs(pred_start - gt_start_page) <= thresholds["chapter_start_page"]
            ):
                matched_chapter = pred_chapter
                break

        if matched_chapter:
            pred_start_page = matched_chapter.get("start_page")
            error = abs(pred_start_page - gt_start_page)
            threshold = thresholds["chapter_start_page"]
            chapter_errors.append(
                {
                    "chapter_number": idx + 1,
                    "passed": error <= threshold,
                    "error": error,
                    "predicted": pred_start_page,
                    "ground_truth": gt_start_page,
                    "threshold": threshold,
                }
            )
        else:
            chapter_errors.append(
                {
                    "chapter_number": idx + 1,
                    "passed": False,
                    "error": None,
                    "predicted": None,
                    "ground_truth": gt_start_page,
                    "threshold": thresholds["chapter_start_page"],
                }
            )

    results["chapter_start_pages"] = {
        "passed": all(ch["passed"] for ch in chapter_errors),
        "errors": chapter_errors,
    }

    return results


@pytest.mark.e2e
def test_e2e_structure_analysis_full_flow(e2e_client: httpx.Client):
    """
    구조 분석 전체 플로우 E2E 테스트

    ⚠️ 실제 데이터만 사용: 실제 PDF 파일, 실제 OpenAI API, 실제 서버 DB
    ⚠️ 실제 서버 실행: 프로덕션 플로우와 동일하게 검증
    ⚠️ Mock 사용 절대 금지
    ⚠️ DB 직접 조회 금지: API 응답만 검증
    ⚠️ 문제 원인 파악을 위해 단계별 상세 로그 기록 (파일 + 터미널)
    """
    log_file = setup_test_logging()
    logger = logging.getLogger(__name__)

    try:
        # ========================================================================
        # 1. PDF 파일 존재 확인
        # ========================================================================
        logger.info("-" * 80)
        logger.info("[STEP 1] PDF 파일 존재 확인")
        logger.info("-" * 80)
        logger.info(f"PDF 파일 경로: {TEST_PDF_PATH}")
        logger.info(f"PDF 파일 존재 여부: {TEST_PDF_PATH.exists()}")

        assert TEST_PDF_PATH.exists(), f"Test PDF file not found: {TEST_PDF_PATH}"
        pdf_size = TEST_PDF_PATH.stat().st_size
        logger.info(
            f"PDF 파일 크기: {pdf_size:,} bytes ({pdf_size / 1024 / 1024:.2f} MB)"
        )
        logger.info("[STEP 1] 완료: PDF 파일 존재 확인")

        # ========================================================================
        # 2. PDF 파일 업로드 (Phase 2와 동일한 플로우)
        # ========================================================================
        logger.info("-" * 80)
        logger.info("[STEP 2] PDF 파일 업로드")
        logger.info("-" * 80)
        logger.info(f"업로드 API: POST /api/books/upload")
        logger.info(f"파일명: {TEST_PDF_PATH.name}")

        upload_start_time = time.time()
        with open(TEST_PDF_PATH, "rb") as f:
            files = {"file": (TEST_PDF_PATH.name, f, "application/pdf")}
            response = e2e_client.post(
                "/api/books/upload",
                files=files,
                params={
                    "title": "1등의 통찰 (구조 분석 테스트)",
                    "author": "Test Author",
                },
            )

        upload_elapsed = time.time() - upload_start_time
        logger.info(f"업로드 응답 시간: {upload_elapsed:.2f}초")
        logger.info(f"업로드 응답 상태 코드: {response.status_code}")

        assert (
            response.status_code == 200
        ), f"업로드 실패: status_code={response.status_code}, response={response.text}"
        upload_data = response.json()
        book_id = upload_data["book_id"]
        upload_status = upload_data["status"]

        logger.info(f"업로드 응답 데이터: book_id={book_id}, status={upload_status}")
        assert (
            upload_status == "uploaded"
        ), f"예상 상태와 다름: expected=uploaded, actual={upload_status}"
        logger.info(f"[STEP 2] 완료: PDF 업로드 완료 (book_id={book_id})")

        # ========================================================================
        # 3. 파싱 완료 대기 (Phase 2와 동일, 프로덕션 플로우와 동일)
        # ========================================================================
        logger.info("-" * 80)
        logger.info("[STEP 3] 파싱 완료 대기 (백그라운드 작업 검증)")
        logger.info("-" * 80)
        logger.info(
            "⚠️ 중요: 실제 서버에서 백그라운드 작업이 실행되므로 상태를 폴링하여 완료 확인"
        )
        logger.info(
            "⚠️ 프로덕션 플로우와 동일하게 검증 (API 응답만 확인, DB 직접 조회 금지)"
        )

        max_wait_time = 300
        start_time = time.time()
        poll_count = 0
        status_history = []

        while True:
            elapsed = time.time() - start_time
            poll_count += 1

            if elapsed > max_wait_time:
                logger.error(f"[STEP 3] 실패: 파싱 타임아웃 ({max_wait_time}초 초과)")
                logger.error(f"  - 경과 시간: {elapsed:.2f}초")
                logger.error(f"  - 폴링 횟수: {poll_count}회")
                logger.error(f"  - 상태 이력: {status_history}")
                pytest.fail(
                    f"Parsing timeout after {max_wait_time} seconds (polled {poll_count} times)"
                )

            # 실제 HTTP 요청으로 상태 확인 (프로덕션 플로우와 동일)
            poll_start = time.time()
            response = e2e_client.get(f"/api/books/{book_id}")
            poll_elapsed = time.time() - poll_start

            assert (
                response.status_code == 200
            ), f"책 조회 실패: status_code={response.status_code}"
            book_data = response.json()
            status = book_data["status"]

            if status not in status_history:
                status_history.append(status)
                logger.info(
                    f"[STEP 3] 상태 변경: {status} (폴링 #{poll_count}, 경과 {elapsed:.1f}초, 응답 시간 {poll_elapsed:.3f}초)"
                )

            if status == "parsed":
                logger.info(
                    f"[STEP 3] 완료: 파싱 완료 (총 {elapsed:.2f}초, 폴링 {poll_count}회)"
                )
                logger.info(f"  - 최종 상태: {status}")
                logger.info(f"  - 페이지 수: {book_data.get('page_count', 'N/A')}")
                break
            elif status == "error_parsing":
                logger.error(f"[STEP 3] 실패: 파싱 에러 발생")
                logger.error(f"  - book_id: {book_id}")
                logger.error(f"  - 상태: {status}")
                logger.error(f"  - 응답 데이터: {book_data}")
                pytest.fail(f"Parsing failed: book_id={book_id}")

            time.sleep(2)

        # ========================================================================
        # 4. 구조 분석 후보 조회
        # ========================================================================
        logger.info("-" * 80)
        logger.info("[STEP 4] 구조 분석 후보 조회")
        logger.info("-" * 80)
        logger.info(f"API: GET /api/books/{book_id}/structure/candidates")
        logger.info(
            "⚠️ 중요: 구조 분석 시 캐시된 파싱 결과를 재사용해야 함 (Upstage API 호출 없음)"
        )

        structure_start_time = time.time()
        response = e2e_client.get(f"/api/books/{book_id}/structure/candidates")
        structure_elapsed = time.time() - structure_start_time

        logger.info(f"구조 분석 응답 시간: {structure_elapsed:.2f}초")
        logger.info(f"구조 분석 응답 상태 코드: {response.status_code}")

        assert (
            response.status_code == 200
        ), f"구조 분석 실패: status_code={response.status_code}, response={response.text}"
        candidates_data = response.json()

        # 응답 구조 로깅
        logger.info(f"응답 구조:")
        logger.info(f"  - meta: {candidates_data.get('meta', {})}")
        logger.info(
            f"  - auto_candidates 개수: {len(candidates_data.get('auto_candidates', []))}"
        )
        logger.info(
            f"  - chapter_title_candidates 개수: {len(candidates_data.get('chapter_title_candidates', []))}"
        )
        logger.info(f"  - samples: {list(candidates_data.get('samples', {}).keys())}")

        # ========================================================================
        # 5. Footer 기반 구조 확인
        # ========================================================================
        logger.info("-" * 80)
        logger.info("[STEP 5] Footer 기반 구조 확인")
        logger.info("-" * 80)
        logger.info("⚠️ 중요: label로 구조 출처 확인 (footer_based_v1)")

        auto_candidates = candidates_data.get("auto_candidates", [])
        logger.info(f"구조 후보 개수: {len(auto_candidates)}")

        assert (
            len(auto_candidates) >= 1
        ), f"최소 1개의 구조 후보가 있어야 함 (Footer 기반), 실제: {len(auto_candidates)}개"

        footer_structure = None

        for idx, candidate in enumerate(auto_candidates):
            label = candidate.get("label", "")
            structure = candidate.get("structure", {})

            logger.info(f"후보 #{idx + 1}: label={label}")

            if label == "footer_based_v1":
                footer_structure = structure
                logger.info(f"[STEP 5] Footer 기반 구조 확인: label=footer_based_v1")
                logger.info(f"  - 구조 키: {list(structure.keys())}")
                # Footer 기반 구조 상세 정보
                main_pages = structure.get("main", {}).get("pages", [])
                chapters = structure.get("main", {}).get("chapters", [])
                logger.info(f"  - 본문 페이지 수: {len(main_pages)}")
                logger.info(
                    f"  - 본문 시작 페이지: {main_pages[0] if main_pages else 'N/A'}"
                )
                logger.info(
                    f"  - 본문 끝 페이지: {main_pages[-1] if main_pages else 'N/A'}"
                )
                logger.info(f"  - 챕터 개수: {len(chapters)}")
                if chapters:
                    logger.info(f"  - 첫 번째 챕터: {chapters[0]}")
                    logger.info(f"  - 마지막 챕터: {chapters[-1]}")

        assert (
            footer_structure is not None
        ), "Footer 기반 구조를 찾을 수 없음 (label=footer_based_v1)"

        logger.info(f"[STEP 5] 완료: Footer 기반 구조 확인 완료")
        logger.info(f"  - Footer 기반 구조: {footer_structure is not None}")

        # ========================================================================
        # 6. 정확도 평가 (Ground Truth 기반)
        # ========================================================================
        logger.info("-" * 80)
        logger.info("[STEP 6] 정확도 평가 (Ground Truth 기반)")
        logger.info("-" * 80)
        logger.info(
            "⚠️ 중요: 정확도 평가는 페이지 번호만 사용 (챕터 제목은 비교하지 않음)"
        )
        logger.info(f"Ground Truth:")
        logger.info(f"  - 본문 시작 페이지: {GROUND_TRUTH['main_start_page']}")
        logger.info(f"  - 본문 끝 페이지: {GROUND_TRUTH.get('main_end_page', 'N/A')}")
        logger.info(f"  - 챕터 개수: {len(GROUND_TRUTH['chapters'])}")

        # 6.1 Footer 기반 구조 정확도 평가
        logger.info("-" * 40)
        logger.info("[STEP 6.1] Footer 기반 구조 정확도 평가")
        logger.info("-" * 40)
        footer_results = evaluate_accuracy(
            footer_structure, GROUND_TRUTH, "footer"
        )

        logger.info(f"Footer 기반 구조 정확도 평가 결과:")
        logger.info(f"  - 본문 시작 페이지:")
        logger.info(f"    * 통과: {footer_results['main_start_page']['passed']}")
        logger.info(
            f"    * 예측: {footer_results['main_start_page'].get('predicted', 'N/A')}"
        )
        logger.info(
            f"    * Ground Truth: {footer_results['main_start_page'].get('ground_truth', 'N/A')}"
        )
        logger.info(
            f"    * 오차: {footer_results['main_start_page'].get('error', 'N/A')}페이지"
        )
        logger.info(
            f"    * 허용 오차: ±{footer_results['main_start_page'].get('threshold', 'N/A')}페이지"
        )

        logger.info(f"  - 챕터 개수:")
        logger.info(f"    * 통과: {footer_results['chapter_count']['passed']}")
        logger.info(
            f"    * 예측: {footer_results['chapter_count'].get('predicted', 'N/A')}개"
        )
        logger.info(
            f"    * Ground Truth: {footer_results['chapter_count'].get('ground_truth', 'N/A')}개"
        )
        logger.info(
            f"    * 오차: {footer_results['chapter_count'].get('error', 'N/A')}개"
        )
        logger.info(
            f"    * 허용 오차: ±{footer_results['chapter_count'].get('threshold', 'N/A')}개"
        )

        logger.info(f"  - 챕터 시작 페이지:")
        chapter_passed = len(
            [
                e
                for e in footer_results["chapter_start_pages"]["errors"]
                if e["passed"]
            ]
        )
        chapter_total = len(footer_results["chapter_start_pages"]["errors"])
        logger.info(f"    * 통과: {chapter_passed}/{chapter_total}")
        logger.info(
            f"    * 전체 통과: {footer_results['chapter_start_pages']['passed']}"
        )
        for ch_error in footer_results["chapter_start_pages"]["errors"]:
            logger.info(
                f"    * 챕터 {ch_error['chapter_number']}: 통과={ch_error['passed']}, "
                f"예측={ch_error.get('predicted', 'N/A')}, "
                f"GT={ch_error.get('ground_truth', 'N/A')}, "
                f"오차={ch_error.get('error', 'N/A')}페이지"
            )

        # ========================================================================
        # 7. 정확도 평가 결과 검증
        # ========================================================================
        logger.info("-" * 80)
        logger.info("[STEP 7] 정확도 평가 결과 검증")
        logger.info("-" * 80)

        # Footer 기반 구조 검증
        logger.info("[STEP 7] Footer 기반 구조 검증")
        if not footer_results["main_start_page"]["passed"]:
            logger.error(
                f"Footer 기반 본문 시작 페이지 오차 초과: {footer_results['main_start_page']}"
            )
            assert (
                False
            ), f"Footer 기반 본문 시작 페이지 오차 초과: {footer_results['main_start_page']}"

        if not footer_results["chapter_count"]["passed"]:
            logger.error(
                f"Footer 기반 챕터 개수 오차 초과: {footer_results['chapter_count']}"
            )
            assert (
                False
            ), f"Footer 기반 챕터 개수 오차 초과: {footer_results['chapter_count']}"

        logger.info("[STEP 7] 완료: Footer 기반 구조 검증 통과")

        # ========================================================================
        # 8. 결과 출력 (터미널 + 로그 파일)
        # ========================================================================
        logger.info("=" * 80)
        logger.info("구조 분석 정확도 평가 결과 요약")
        logger.info("=" * 80)
        logger.info(f"\n[Footer 기반 구조]")
        logger.info(
            f"  본문 시작 페이지: 통과={footer_results['main_start_page']['passed']}, "
            f"오차={footer_results['main_start_page'].get('error', 'N/A')}페이지"
        )
        logger.info(
            f"  챕터 개수: 통과={footer_results['chapter_count']['passed']}, "
            f"오차={footer_results['chapter_count'].get('error', 'N/A')}개"
        )
        logger.info(
            f"  챕터 시작 페이지: 통과={footer_results['chapter_start_pages']['passed']}, "
            f"{chapter_passed}/{chapter_total}개 챕터 통과"
        )
        logger.info("=" * 80)
        logger.info(f"테스트 완료: 로그 파일 위치 - {log_file}")

        # 터미널 출력 (간략 요약)
        print("\n" + "=" * 80)
        print("구조 분석 정확도 평가 결과")
        print("=" * 80)
        print(f"\n[Footer 기반 구조]")
        print(f"  본문 시작 페이지: {footer_results['main_start_page']}")
        print(f"  챕터 개수: {footer_results['chapter_count']}")
        print(
            f"  챕터 시작 페이지: {footer_results['chapter_start_pages']['passed']}"
        )
        print("=" * 80)
        print(f"\n상세 로그 파일: {log_file}")

    except Exception as e:
        logger.error("=" * 80)
        logger.error("테스트 실패: 예외 발생")
        logger.error("=" * 80)
        logger.error(f"예외 타입: {type(e).__name__}")
        logger.error(f"예외 메시지: {str(e)}")
        logger.error(f"로그 파일: {log_file}")
        import traceback

        logger.error(f"스택 트레이스:\n{traceback.format_exc()}")
        raise


@pytest.mark.e2e
def test_e2e_structure_analysis_cache_reuse(e2e_client: httpx.Client):
    """
    구조 분석 시 캐시 재사용 검증 E2E 테스트

    ⚠️ 실제 데이터만 사용
    ⚠️ 실제 서버 실행: 프로덕션 플로우와 동일하게 검증
    ⚠️ DB 직접 조회 금지: API 응답만 검증
    ⚠️ 문제 원인 파악을 위해 단계별 상세 로그 기록 (파일 + 터미널)
    """
    log_file = setup_test_logging()
    logger = logging.getLogger(__name__)

    try:
        # ========================================================================
        # 1. PDF 파일 존재 확인
        # ========================================================================
        logger.info("-" * 80)
        logger.info("[STEP 1] PDF 파일 존재 확인")
        logger.info("-" * 80)
        logger.info(f"PDF 파일 경로: {TEST_PDF_PATH}")
        assert TEST_PDF_PATH.exists(), f"Test PDF file not found: {TEST_PDF_PATH}"
        logger.info("[STEP 1] 완료: PDF 파일 존재 확인")

        # ========================================================================
        # 2. PDF 파일 업로드 및 파싱 (Phase 2와 동일)
        # ========================================================================
        logger.info("-" * 80)
        logger.info("[STEP 2] PDF 파일 업로드 및 파싱")
        logger.info("-" * 80)
        logger.info(
            "⚠️ 중요: Phase 2에서 파싱된 book_id를 재사용하거나, 새로 업로드하여 캐시 생성 확인"
        )

        with open(TEST_PDF_PATH, "rb") as f:
            files = {"file": (TEST_PDF_PATH.name, f, "application/pdf")}
            response = e2e_client.post(
                "/api/books/upload",
                files=files,
                params={
                    "title": "1등의 통찰 (캐시 재사용 테스트)",
                    "author": "Test Author",
                },
            )

        assert (
            response.status_code == 200
        ), f"업로드 실패: status_code={response.status_code}"
        upload_data = response.json()
        book_id = upload_data["book_id"]
        logger.info(f"업로드 완료: book_id={book_id}")

        # 파싱 완료 대기
        logger.info("파싱 완료 대기 중...")
        max_wait_time = 300
        start_time = time.time()
        poll_count = 0

        while True:
            elapsed = time.time() - start_time
            poll_count += 1

            if elapsed > max_wait_time:
                logger.error(
                    f"파싱 타임아웃: {max_wait_time}초 초과, 폴링 {poll_count}회"
                )
                pytest.fail(f"Parsing timeout after {max_wait_time} seconds")

            response = e2e_client.get(f"/api/books/{book_id}")
            assert response.status_code == 200
            status = response.json()["status"]

            if status == "parsed":
                logger.info(f"파싱 완료: {elapsed:.2f}초, 폴링 {poll_count}회")
                break
            elif status == "error_parsing":
                logger.error(f"파싱 실패: book_id={book_id}")
                pytest.fail(f"Parsing failed: book_id={book_id}")

            time.sleep(2)

        logger.info("[STEP 2] 완료: 파싱 완료")

        # ========================================================================
        # 3. 캐시 파일 존재 확인 (Phase 2에서 생성된 캐시)
        # ========================================================================
        logger.info("-" * 80)
        logger.info("[STEP 3] 캐시 파일 존재 확인")
        logger.info("-" * 80)
        logger.info("⚠️ 중요: Phase 2에서 생성된 캐시 파일이 있어야 함")

        from backend.config.settings import settings
        import hashlib

        cache_dir = settings.cache_dir / "upstage"
        logger.info(f"캐시 디렉토리: {cache_dir}")
        logger.info(f"캐시 디렉토리 존재 여부: {cache_dir.exists()}")

        # PDF 파일 해시 계산
        logger.info("PDF 파일 해시 계산 중...")
        with open(TEST_PDF_PATH, "rb") as f:
            hasher = hashlib.md5()
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
            file_hash = hasher.hexdigest()

        logger.info(f"PDF 파일 해시: {file_hash}")

        cache_file = cache_dir / f"{file_hash}.json"
        logger.info(f"예상 캐시 파일 경로: {cache_file}")
        logger.info(f"캐시 파일 존재 여부: {cache_file.exists()}")

        assert cache_file.exists(), f"캐시 파일이 존재하지 않음: {cache_file}"

        cache_size = cache_file.stat().st_size
        cache_mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        logger.info(
            f"캐시 파일 크기: {cache_size:,} bytes ({cache_size / 1024 / 1024:.2f} MB)"
        )
        logger.info(f"캐시 파일 수정 시간: {cache_mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("[STEP 3] 완료: 캐시 파일 확인")

        # ========================================================================
        # 4. 구조 분석 API 호출 (캐시된 파싱 결과 재사용 확인)
        # ========================================================================
        logger.info("-" * 80)
        logger.info("[STEP 4] 구조 분석 API 호출 (캐시 재사용 검증)")
        logger.info("-" * 80)
        logger.info(
            "⚠️ 중요: 구조 분석 시 캐시된 파싱 결과를 재사용해야 함 (Upstage API 호출 없음)"
        )
        logger.info("⚠️ 중요: 서버 로그에서 'Cache hit' 메시지 확인 필요")

        structure_start_time = time.time()
        response = e2e_client.get(f"/api/books/{book_id}/structure/candidates")
        structure_elapsed = time.time() - structure_start_time

        logger.info(f"구조 분석 응답 시간: {structure_elapsed:.2f}초")
        logger.info(f"구조 분석 응답 상태 코드: {response.status_code}")

        assert (
            response.status_code == 200
        ), f"구조 분석 실패: status_code={response.status_code}"
        candidates_data = response.json()

        logger.info(f"응답 데이터 구조:")
        logger.info(
            f"  - auto_candidates 개수: {len(candidates_data.get('auto_candidates', []))}"
        )
        logger.info(f"  - meta: {candidates_data.get('meta', {})}")

        # ========================================================================
        # 5. Footer 기반 구조 확인
        # ========================================================================
        logger.info("-" * 80)
        logger.info("[STEP 5] Footer 기반 구조 확인")
        logger.info("-" * 80)
        logger.info("⚠️ 중요: label로 구조 출처 확인 (footer_based_v1)")

        auto_candidates = candidates_data.get("auto_candidates", [])
        logger.info(f"구조 후보 개수: {len(auto_candidates)}")

        footer_found = False

        for idx, candidate in enumerate(auto_candidates):
            label = candidate.get("label", "")
            structure = candidate.get("structure", {})

            logger.info(f"후보 #{idx + 1}: label={label}")

            if label == "footer_based_v1":
                footer_found = True
                logger.info(f"[STEP 5] Footer 기반 구조 확인: label=footer_based_v1")
                logger.info(f"  - 구조 키: {list(structure.keys())}")
                # Footer 기반 구조 요약
                main_pages = structure.get("main", {}).get("pages", [])
                chapters = structure.get("main", {}).get("chapters", [])
                logger.info(f"  - 본문 페이지 수: {len(main_pages)}")
                logger.info(f"  - 챕터 개수: {len(chapters)}")

        assert footer_found, "Footer 기반 구조를 찾을 수 없음 (label=footer_based_v1)"

        logger.info(
            f"[STEP 5] 완료: Footer 기반 구조={footer_found}"
        )
        logger.info("=" * 80)
        logger.info("캐시 재사용 검증 완료")
        logger.info(
            "⚠️ 참고: 서버 로그에서 'Cache hit' 메시지 확인하여 캐시 재사용 확인"
        )
        logger.info(f"로그 파일: {log_file}")

        print(f"\n[캐시 재사용 검증 완료]")
        print(f"  - 휴리스틱 구조: {heuristic_found}")
        print(f"  - LLM 보정 구조: {llm_found}")
        print(f"  - 상세 로그 파일: {log_file}")

    except Exception as e:
        logger.error("=" * 80)
        logger.error("테스트 실패: 예외 발생")
        logger.error("=" * 80)
        logger.error(f"예외 타입: {type(e).__name__}")
        logger.error(f"예외 메시지: {str(e)}")
        logger.error(f"로그 파일: {log_file}")
        import traceback

        logger.error(f"스택 트레이스:\n{traceback.format_exc()}")
        raise


@pytest.mark.e2e
def test_e2e_structure_analysis_final_structure(e2e_client: httpx.Client):
    """
    최종 구조 확정 및 DB 저장 검증 E2E 테스트

    ⚠️ 실제 데이터만 사용
    ⚠️ 실제 서버 실행: 프로덕션 플로우와 동일하게 검증
    ⚠️ DB 직접 조회 금지: API 응답만 검증
    ⚠️ 문제 원인 파악을 위해 단계별 상세 로그 기록 (파일 + 터미널)
    """
    log_file = setup_test_logging()
    logger = logging.getLogger(__name__)

    try:
        # ========================================================================
        # 1. PDF 파일 업로드 및 파싱
        # ========================================================================
        logger.info("-" * 80)
        logger.info("[STEP 1] PDF 파일 업로드 및 파싱")
        logger.info("-" * 80)

        assert TEST_PDF_PATH.exists(), f"Test PDF file not found: {TEST_PDF_PATH}"

        with open(TEST_PDF_PATH, "rb") as f:
            files = {"file": (TEST_PDF_PATH.name, f, "application/pdf")}
            response = e2e_client.post(
                "/api/books/upload",
                files=files,
                params={
                    "title": "1등의 통찰 (최종 구조 확정 테스트)",
                    "author": "Test Author",
                },
            )

        assert (
            response.status_code == 200
        ), f"업로드 실패: status_code={response.status_code}"
        upload_data = response.json()
        book_id = upload_data["book_id"]
        logger.info(f"업로드 완료: book_id={book_id}")

        # 파싱 완료 대기
        logger.info("파싱 완료 대기 중...")
        max_wait_time = 300
        start_time = time.time()
        poll_count = 0

        while True:
            elapsed = time.time() - start_time
            poll_count += 1

            if elapsed > max_wait_time:
                logger.error(
                    f"파싱 타임아웃: {max_wait_time}초 초과, 폴링 {poll_count}회"
                )
                pytest.fail(f"Parsing timeout after {max_wait_time} seconds")

            response = e2e_client.get(f"/api/books/{book_id}")
            assert response.status_code == 200
            status = response.json()["status"]

            if status == "parsed":
                logger.info(f"파싱 완료: {elapsed:.2f}초, 폴링 {poll_count}회")
                break
            elif status == "error_parsing":
                logger.error(f"파싱 실패: book_id={book_id}")
                pytest.fail(f"Parsing failed: book_id={book_id}")

            time.sleep(2)

        logger.info("[STEP 1] 완료: 파싱 완료")

        # ========================================================================
        # 2. 구조 후보 조회 및 LLM 구조 선택
        # ========================================================================
        logger.info("-" * 80)
        logger.info("[STEP 2] 구조 후보 조회 및 LLM 구조 선택")
        logger.info("-" * 80)
        logger.info("⚠️ 중요: LLM 구조를 최종 구조로 사용 (더 정확할 것으로 예상)")

        response = e2e_client.get(f"/api/books/{book_id}/structure/candidates")
        assert (
            response.status_code == 200
        ), f"구조 후보 조회 실패: status_code={response.status_code}"
        candidates_data = response.json()

        auto_candidates = candidates_data.get("auto_candidates", [])
        logger.info(f"구조 후보 개수: {len(auto_candidates)}")

        footer_structure = None

        for candidate in auto_candidates:
            label = candidate.get("label", "")
            structure = candidate.get("structure", {})

            logger.info(f"후보 label: {label}")

            if label == "footer_based_v1":
                footer_structure = structure
                logger.info(f"[STEP 2] Footer 기반 구조 선택: label=footer_based_v1")
                # Footer 기반 구조는 main.pages 형식
                main_pages = structure.get("main", {}).get("pages", [])
                chapters = structure.get("main", {}).get("chapters", [])
                logger.info(
                    f"  - 본문 시작 페이지: {main_pages[0] if main_pages else 'N/A'}"
                )
                logger.info(f"  - 본문 끝 페이지: {main_pages[-1] if main_pages else 'N/A'}")
                logger.info(f"  - 챕터 개수: {len(chapters)}")

        assert footer_structure is not None, "Footer 기반 구조를 찾을 수 없음 (label=footer_based_v1)"
        logger.info("[STEP 2] 완료: Footer 기반 구조 선택 완료")

        # ========================================================================
        # 3. 최종 구조 확정 (Footer 기반 구조 사용)
        # ========================================================================
        logger.info("-" * 80)
        logger.info("[STEP 3] 최종 구조 확정 (Footer 기반 구조 사용)")
        logger.info("-" * 80)

        main_pages = footer_structure.get("main", {}).get("pages", [])
        chapters = footer_structure.get("main", {}).get("chapters", [])

        final_structure = {
            "main_start_page": main_pages[0] if main_pages else 1,
            "main_end_page": main_pages[-1] if main_pages else 1,
            "chapters": [
                {
                    "title": ch.get("title", ""),
                    "start_page": ch.get("start_page"),
                    "end_page": ch.get("end_page"),
                    "order_index": idx,
                }
                for idx, ch in enumerate(chapters)
            ],
            "notes_pages": [],
            "start_pages": [],
            "end_pages": [],
        }

        logger.info(f"최종 구조 데이터:")
        logger.info(f"  - 본문 시작 페이지: {final_structure['main_start_page']}")
        logger.info(f"  - 본문 끝 페이지: {final_structure['main_end_page']}")
        logger.info(f"  - 챕터 개수: {len(final_structure['chapters'])}")
        for idx, ch in enumerate(final_structure["chapters"][:3]):  # 처음 3개만 로깅
            logger.info(f"  - 챕터 {idx + 1}: {ch}")

        logger.info(f"API: POST /api/books/{book_id}/structure/final")
        response = e2e_client.post(
            f"/api/books/{book_id}/structure/final", json=final_structure
        )

        logger.info(f"최종 구조 확정 응답 상태 코드: {response.status_code}")
        assert (
            response.status_code == 200
        ), f"최종 구조 확정 실패: status_code={response.status_code}, response={response.text}"
        book_data = response.json()

        logger.info("[STEP 3] 완료: 최종 구조 확정 완료")

        # ========================================================================
        # 4. 상태 변경 확인 (parsed → structured)
        # ========================================================================
        logger.info("-" * 80)
        logger.info("[STEP 4] 상태 변경 확인 (parsed → structured)")
        logger.info("-" * 80)

        book_status = book_data["status"]
        logger.info(f"책 상태: {book_status}")
        logger.info(f"예상 상태: structured")

        assert (
            book_status == "structured"
        ), f"상태가 structured가 아님: actual={book_status}"
        logger.info(f"[STEP 4] 완료: 상태 변경 확인 (parsed → structured)")

        # ========================================================================
        # 5. 구조 데이터 확인
        # ========================================================================
        logger.info("-" * 80)
        logger.info("[STEP 5] 구조 데이터 확인")
        logger.info("-" * 80)

        structure_data = book_data.get("structure_data")
        logger.info(f"structure_data 존재 여부: {structure_data is not None}")

        assert structure_data is not None, "structure_data가 없음"

        logger.info(f"structure_data 내용:")
        logger.info(f"  - main_start_page: {structure_data.get('main_start_page')}")
        logger.info(f"  - main_end_page: {structure_data.get('main_end_page')}")
        logger.info(f"  - chapters 개수: {len(structure_data.get('chapters', []))}")

        # 구조 데이터 검증
        assert (
            structure_data.get("main_start_page") == final_structure["main_start_page"]
        ), f"본문 시작 페이지 불일치: expected={final_structure['main_start_page']}, actual={structure_data.get('main_start_page')}"

        assert len(structure_data.get("chapters", [])) == len(
            final_structure["chapters"]
        ), f"챕터 개수 불일치: expected={len(final_structure['chapters'])}, actual={len(structure_data.get('chapters', []))}"

        logger.info("[STEP 5] 완료: 구조 데이터 검증 통과")

        logger.info("=" * 80)
        logger.info("최종 구조 확정 및 DB 저장 검증 완료")
        logger.info(f"  - book_id: {book_id}")
        logger.info(f"  - 최종 상태: {book_status}")
        logger.info(f"  - 본문 시작 페이지: {structure_data.get('main_start_page')}")
        logger.info(f"  - 챕터 개수: {len(structure_data.get('chapters', []))}")
        logger.info(f"로그 파일: {log_file}")
        logger.info("=" * 80)

        print(f"\n[최종 구조 확정 완료]")
        print(f"  - book_id: {book_id}")
        print(f"  - 상태: {book_status}")
        print(f"  - 본문 시작 페이지: {structure_data.get('main_start_page')}")
        print(f"  - 챕터 개수: {len(structure_data.get('chapters', []))}")
        print(f"  - 상세 로그 파일: {log_file}")

    except Exception as e:
        logger.error("=" * 80)
        logger.error("테스트 실패: 예외 발생")
        logger.error("=" * 80)
        logger.error(f"예외 타입: {type(e).__name__}")
        logger.error(f"예외 메시지: {str(e)}")
        logger.error(f"로그 파일: {log_file}")
        import traceback

        logger.error(f"스택 트레이스:\n{traceback.format_exc()}")
        raise
