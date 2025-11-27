"""
실제 캐시 데이터에서 Footer 요소 분석 스크립트

성공한 도서와 실패한 도서를 비교하여 Footer 추출 기준을 명확히 분석합니다.
E2E 테스트 및 메인 코드베이스와 동일한 플로우를 사용합니다.

핵심 분석 포인트:
1. Footer가 홀수/짝수 페이지 중 어디에서 뽑히는지
2. 모든 페이지에 Footer가 있는데 어떤 기준으로 선택되는지
3. category='footer'인 요소를 모두 추출하는지
"""
import json
import sys
from pathlib import Path
from typing import Dict, Any, List
from collections import defaultdict

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.parsers.pdf_parser import PDFParser
from backend.structure.content_boundary_detector import ContentBoundaryDetector
from backend.structure.chapter_detector import ChapterDetector
from backend.config.settings import settings

# 프로젝트 루트
CACHE_DIR = PROJECT_ROOT / "data" / "cache" / "upstage"

# 성공한 도서 (테스트 통과)
successful_books = [
    {
        "book": "1등의 통찰",
        "cache_hash": "8ba9b08c4d926326fbc09606888509ff",
        "expected_main_start": 37,
        "status": "success",
    },
    {
        "book": "90년대생이온다",
        "cache_hash": "44ecb40bcbdb9b0cfc87af6d481d9c6a",
        "expected_main_start": None,  # 확인 필요
        "status": "success",
    },
    {
        "book": "10년후세계사",
        "cache_hash": "859bb8e7e092b2045ccb10825dd1fb3f",
        "expected_main_start": None,  # 확인 필요
        "status": "success",
    },
    {
        "book": "4차산업혁명전문직의미래",
        "cache_hash": "802ff78cd3e53c2c87a3ca84f5e79a33",
        "expected_main_start": None,  # 확인 필요
        "status": "success",
    },
]

# 실패한 도서 (E2E 테스트 결과 기준)
failed_books = [
    {
        "book": "3D프린터의모든것",
        "cache_hash": "3e9a6eb72248208bb7718b029b27fa8a",
        "expected_main_start": 27,
        "expected_chapters": [27, 99, 151, 241],  # 챕터 시작 페이지
        "failure_type": "챕터 4번 미탐지 (예측=245, GT=241, 오차=4페이지)",
        "status": "failed",
    },
    {
        "book": "12가지인생의법칙",
        "cache_hash": "552429c3011c608bd0257c0f5beb5d7b",
        "expected_main_start": 35,
        "expected_chapters": [35, 170, 188, 243, 299, 330, 408, 463, 504, 555, 602, 641],  # 챕터 시작 페이지
        "failure_type": "본문 시작 페이지 오차",
        "status": "failed",
    },
    {
        "book": "30개도시로읽는세계사",
        "cache_hash": "fa0eb8b9e5d4b339c27b010e0cbebe10",
        "expected_main_start": 23,
        "expected_chapters": [23, 211, 383, 555],  # 챕터 시작 페이지
        "failure_type": "본문 시작 페이지 오차 (예측=159, GT=23, 오차=136페이지)",
        "status": "failed",
    },
    {
        "book": "99를위한경제",
        "cache_hash": "e3e5af347c6cfed38027923dff0c621d",
        "expected_main_start": 41,
        "expected_chapters": [41, 69, 125, 145, 177, 257, 321],  # 챕터 시작 페이지 (7번째 챕터=321)
        "failure_type": "챕터 시작 페이지 오차 (7번째 챕터 predicted=None, GT=321)",
        "status": "failed",
    },
]


def analyze_footer_statistics(pages: List[Dict], boundary_detector: ContentBoundaryDetector) -> Dict:
    """모든 페이지의 Footer 요소 통계 분석"""
    stats = {
        "total_pages": len(pages),
        "odd_pages": 0,
        "even_pages": 0,
        "pages_with_footer": 0,
        "pages_without_footer": 0,
        "odd_pages_with_footer": 0,
        "even_pages_with_footer": 0,
        "footer_by_category": defaultdict(int),  # category='footer'인 요소 개수
        "footer_by_y0": defaultdict(int),  # y0 > 0.9인 요소 개수
        "footer_elements_per_page": defaultdict(list),  # 페이지별 Footer 요소 개수
    }
    
    for page in pages:
        page_num = page.get("page_number", 0)
        is_odd = page_num % 2 == 1
        
        if is_odd:
            stats["odd_pages"] += 1
        else:
            stats["even_pages"] += 1
        
        # Footer 요소 추출 (실제 코드와 동일)
        footer_elements = boundary_detector._get_footer_elements(page)
        
        if footer_elements:
            stats["pages_with_footer"] += 1
            if is_odd:
                stats["odd_pages_with_footer"] += 1
            else:
                stats["even_pages_with_footer"] += 1
            
            # Footer 요소 분류 통계
            for elem in footer_elements:
                # category='footer'인 요소 확인
                if elem.get("category") == "footer":
                    stats["footer_by_category"][page_num] += 1
                
                # y0 > 0.9인 요소 확인
                bbox = elem.get("bbox", {})
                y0 = bbox.get("y0", 0.0)
                if y0 > 0.9:
                    stats["footer_by_y0"][page_num] += 1
            
            stats["footer_elements_per_page"][page_num] = len(footer_elements)
        else:
            stats["pages_without_footer"] += 1
    
    return stats


def analyze_book_footer(cache_file: Path, book_info: Dict):
    """도서의 Footer 요소 분석 (실제 코드 플로우와 동일)"""
    print("=" * 80)
    print(f"[도서] {book_info['book']} ({book_info.get('status', 'unknown')})")
    print(f"[캐시 파일] {cache_file.name}")
    print(f"[실패 유형] {book_info.get('failure_type', 'unknown')}")
    if book_info.get("expected_main_start"):
        print(f"[예상 본문 시작] {book_info['expected_main_start']}페이지")
    if book_info.get("expected_chapters"):
        print(f"[예상 챕터 시작] {book_info['expected_chapters']}")
    print("=" * 80)
    print()

    # 1. 캐시 파일 로드 (Upstage API 응답 형식)
    with open(cache_file, "r", encoding="utf-8") as f:
        cache_data = json.load(f)

    if not cache_data.get("elements"):
        print("[ERROR] 캐시 파일에 elements가 없습니다.")
        return

    # 2. PDFParser 인스턴스 생성 (실제 코드와 동일)
    pdf_parser = PDFParser(api_key=settings.upstage_api_key, clean_output=False)

    # 3. PDFParser._structure_elements() 호출 (실제 코드와 동일)
    print("[1단계] PDFParser._structure_elements() 호출 중...")
    structured_elements = pdf_parser._structure_elements(cache_data)
    print(f"  [OK] 구조화된 elements: {len(structured_elements)}개")
    print()

    # 4. PDFParser._split_pages_by_side() 호출 (실제 코드와 동일)
    print("[2단계] PDFParser._split_pages_by_side() 호출 중...")
    pages = pdf_parser._split_pages_by_side(structured_elements, force_split=True)
    print(f"  [OK] 분리된 페이지: {len(pages)}개")
    print()

    # 5. parsed_data 구성 (실제 코드와 동일)
    parsed_data = {
        "pages": pages,
        "total_pages": len(pages),
        "total_elements": len(structured_elements),
    }

    # 6. ContentBoundaryDetector 인스턴스 생성 (실제 코드와 동일)
    boundary_detector = ContentBoundaryDetector()

    # 7. 전체 Footer 통계 분석
    print("[3단계] 전체 Footer 통계 분석...")
    stats = analyze_footer_statistics(pages, boundary_detector)
    
    print(f"  전체 페이지: {stats['total_pages']}개")
    print(f"  홀수 페이지: {stats['odd_pages']}개")
    print(f"  짝수 페이지: {stats['even_pages']}개")
    print(f"  Footer 있는 페이지: {stats['pages_with_footer']}개")
    print(f"  Footer 없는 페이지: {stats['pages_without_footer']}개")
    print(f"  홀수 페이지 중 Footer 있는 페이지: {stats['odd_pages_with_footer']}개")
    print(f"  짝수 페이지 중 Footer 있는 페이지: {stats['even_pages_with_footer']}개")
    print()
    
    # category='footer'인 요소 통계
    category_footer_pages = len(stats['footer_by_category'])
    print(f"  category='footer'인 요소가 있는 페이지: {category_footer_pages}개")
    if category_footer_pages > 0:
        print(f"  category='footer'인 요소 총 개수: {sum(stats['footer_by_category'].values())}개")
        # 처음 10개 페이지 예시
        sample_pages = sorted(stats['footer_by_category'].keys())[:10]
        print(f"  category='footer' 예시 페이지: {sample_pages}")
    print()
    
    # y0 > 0.9인 요소 통계
    y0_footer_pages = len(stats['footer_by_y0'])
    print(f"  y0 > 0.9인 요소가 있는 페이지: {y0_footer_pages}개")
    if y0_footer_pages > 0:
        print(f"  y0 > 0.9인 요소 총 개수: {sum(stats['footer_by_y0'].values())}개")
    print()

    # 8. 본문 시작 페이지 주변 상세 분석
    expected_start = book_info.get("expected_main_start")
    if expected_start:
        print(f"[4단계] 본문 시작 페이지 주변 상세 분석 (예상: {expected_start}페이지)...")
        analysis_range = range(
            max(1, expected_start - 10),
            min(len(pages) + 1, expected_start + 10),
        )
        
        print(f"  분석 범위: {min(analysis_range)}페이지 ~ {max(analysis_range)}페이지")
        print()
        
        for page_num in analysis_range:
            page = next((p for p in pages if p["page_number"] == page_num), None)
            if not page:
                continue
            
            is_odd = page_num % 2 == 1
            footer_elements = boundary_detector._get_footer_elements(page)
            
            # 홀수/짝수 구분 표시
            page_type = "홀수" if is_odd else "짝수"
            
            if footer_elements:
                # category='footer'인 요소 확인
                category_footer_count = sum(1 for e in footer_elements if e.get("category") == "footer")
                y0_footer_count = sum(1 for e in footer_elements if e.get("bbox", {}).get("y0", 0.0) > 0.9)
                
                # 본문 시작 페이지 주변만 상세 출력
                if expected_start - 5 <= page_num <= expected_start + 5:
                    print(f"  [Page {page_num}] ({page_type}) {'[TARGET]' if page_num == expected_start else ''}")
                    print(f"    Footer 요소 개수: {len(footer_elements)}")
                    print(f"      - category='footer': {category_footer_count}개")
                    print(f"      - y0 > 0.9: {y0_footer_count}개")
                    
                    # Footer 요소 분류
                    chapter_markers = []
                    page_numbers = []
                    others = []
                    
                    for elem in footer_elements:
                        classification = boundary_detector._classify_footer_element(elem)
                        if classification == "chapter_marker":
                            chapter_markers.append(elem)
                        elif classification == "page_number":
                            page_numbers.append(elem)
                        else:
                            others.append(elem)
                    
                    if chapter_markers:
                        print(f"    [OK] chapter_marker: {len(chapter_markers)}개")
                        for i, marker in enumerate(chapter_markers[:3]):  # 최대 3개
                            text = marker.get("text", "").strip()
                            category = marker.get("category", "unknown")
                            bbox = marker.get("bbox", {})
                            x0 = bbox.get("x0", 0.5)
                            y0 = bbox.get("y0", 0.0)
                            print(f"      [{i+1}] text='{text[:50]}', category={category}, x0={x0:.3f}, y0={y0:.3f}")
                    else:
                        print(f"    [FAIL] chapter_marker: 없음")
                        if others:
                            print(f"    [디버깅] other 요소 (최대 3개):")
                            for i, other in enumerate(others[:3]):
                                text = other.get("text", "").strip()
                                category = other.get("category", "unknown")
                                bbox = other.get("bbox", {})
                                x0 = bbox.get("x0", 0.5)
                                y0 = bbox.get("y0", 0.0)
                                print(f"      [{i+1}] text='{text[:50]}', category={category}, x0={x0:.3f}, y0={y0:.3f}")
                    
                    if page_numbers:
                        print(f"    - page_number: {len(page_numbers)}개")
                    
                    print()
            else:
                if expected_start - 2 <= page_num <= expected_start + 2:
                    print(f"  [Page {page_num}] ({page_type}) [FAIL] Footer 요소 없음")
                    print()
        
        print()

    # 9. ContentBoundaryDetector.detect_boundaries() 호출 (실제 코드와 동일)
    print("[5단계] ContentBoundaryDetector.detect_boundaries() 호출 중...")
    boundaries = boundary_detector.detect_boundaries(parsed_data)
    detected_main_start = boundaries["main"]["start"]
    print(f"  [OK] 탐지된 본문 시작: {detected_main_start}페이지")
    if expected_start:
        print(f"  [OK] 예상 본문 시작: {expected_start}페이지")
        error = abs(detected_main_start - expected_start)
        print(f"  [{'OK' if error <= 3 else 'FAIL'}] 오차: {error}페이지")
    print()
    
    # 9-1. ChapterDetector.detect_chapters() 호출 (실제 코드와 동일)
    print("[5-1단계] ChapterDetector.detect_chapters() 호출 중...")
    chapter_detector = ChapterDetector()
    main_pages = boundaries["main"]["pages"]
    chapters = chapter_detector.detect_chapters(parsed_data, main_pages)
    detected_chapter_starts = [ch["start_page"] for ch in chapters]
    print(f"  [OK] 탐지된 챕터 시작: {detected_chapter_starts}")
    if book_info.get("expected_chapters"):
        expected_chapters = book_info["expected_chapters"]
        print(f"  [OK] 예상 챕터 시작: {expected_chapters}")
        print(f"  [OK] 탐지된 챕터 개수: {len(detected_chapter_starts)}개")
        print(f"  [OK] 예상 챕터 개수: {len(expected_chapters)}개")
        
        # 각 챕터별 오차 확인
        print(f"  [챕터별 오차 분석]")
        for i, expected_start in enumerate(expected_chapters):
            if i < len(detected_chapter_starts):
                detected_start = detected_chapter_starts[i]
                error = abs(detected_start - expected_start)
                status = "OK" if error <= 3 else "FAIL"
                print(f"    챕터 {i+1}: 예상={expected_start}, 탐지={detected_start}, 오차={error}페이지 [{status}]")
            else:
                print(f"    챕터 {i+1}: 예상={expected_start}, 탐지=None [FAIL - 탐지 안 됨]")
    print()

    # 10. 페이지 선택 기준 분석
    print("[6단계] 페이지 선택 기준 분석...")
    print("  _detect_main_start_improved() 로직:")
    print("    1. 표지 제외 (1-2페이지)")
    print("    2. 홀수 페이지만 처리 (page_num % 2 == 0 제외)")
    print("    3. Footer 요소에서 chapter_marker 찾기")
    print("    4. 첫 번째 chapter_marker 발견 시 본문 시작으로 판단")
    print()
    
    # 실제로 어떤 페이지들이 검사되었는지 확인
    checked_pages = []
    for page in pages:
        page_num = page.get("page_number", 0)
        if page_num <= 2:
            continue
        if page_num % 2 == 0:
            continue
        checked_pages.append(page_num)
    
    print(f"  실제 검사된 페이지 (홀수, 3페이지 이상): {len(checked_pages)}개")
    print(f"  처음 20개: {checked_pages[:20]}")
    print()

    print("-" * 80)
    print()


def analyze_chapter_7_99경제(cache_file: Path, book_info: Dict):
    """99를위한경제의 7번째 챕터(321페이지) 주변 상세 분석"""
    print("=" * 80)
    print(f"[도서] {book_info['book']} - 7번째 챕터(321페이지) 주변 분석")
    print(f"[캐시 파일] {cache_file.name}")
    print("=" * 80)
    print()

    # 1. 캐시 파일 로드 및 구조화 (기존과 동일)
    with open(cache_file, "r", encoding="utf-8") as f:
        cache_data = json.load(f)

    if not cache_data.get("elements"):
        print("[ERROR] 캐시 파일에 elements가 없습니다.")
        return

    pdf_parser = PDFParser(api_key=settings.upstage_api_key, clean_output=False)
    structured_elements = pdf_parser._structure_elements(cache_data)
    pages = pdf_parser._split_pages_by_side(structured_elements, force_split=True)
    
    parsed_data = {
        "pages": pages,
        "total_pages": len(pages),
        "total_elements": len(structured_elements),
    }

    # 2. 316~326페이지 Footer 요소 상세 출력
    target_page = 321
    analysis_range = range(max(1, target_page - 5), min(len(pages) + 1, target_page + 6))
    
    print(f"[분석 범위] {min(analysis_range)}페이지 ~ {max(analysis_range)}페이지 (321페이지 주변)")
    print()
    
    boundary_detector = ContentBoundaryDetector()
    chapter_detector = ChapterDetector()
    
    # 3. 각 페이지에서 Footer 요소 및 분류 결과 출력
    for page_num in analysis_range:
        page = next((p for p in pages if p["page_number"] == page_num), None)
        if not page:
            continue
        
        is_odd = page_num % 2 == 1
        page_type = "홀수" if is_odd else "짝수"
        footer_elements = boundary_detector._get_footer_elements(page)
        
        print(f"[Page {page_num}] ({page_type}) {'[TARGET]' if page_num == target_page else ''}")
        
        if footer_elements:
            print(f"  Footer 요소 개수: {len(footer_elements)}")
            
            # 각 Footer 요소 상세 출력
            for idx, elem in enumerate(footer_elements):
                text = elem.get("text", "").strip()
                category = elem.get("category", "unknown")
                bbox = elem.get("bbox", {})
                x0 = bbox.get("x0", 0.5)
                y0 = bbox.get("y0", 0.0)
                classification = boundary_detector._classify_footer_element(elem)
                
                print(f"    요소 #{idx+1}:")
                print(f"      text='{text[:80]}'")
                print(f"      category={category}, x0={x0:.3f}, y0={y0:.3f}")
                print(f"      분류 결과: {classification}")
                
                # chapter_marker인 경우 챕터 번호 추출 시도
                if classification == "chapter_marker":
                    chapter_number = chapter_detector._extract_chapter_number_from_pattern(text)
                    print(f"      추출된 챕터 번호: {chapter_number}")
        else:
            print(f"  [FAIL] Footer 요소 없음")
        
        print()
    
    # 4. 챕터 번호 추출 결과 (필터링 전/후)
    print("[챕터 번호 추출 분석]")
    boundaries = boundary_detector.detect_boundaries(parsed_data)
    main_pages = boundaries["main"]["pages"]
    main_odd_pages = [p for p in pages if p["page_number"] in main_pages and p["page_number"] % 2 == 1]
    
    # 필터링 전
    page_chapter_numbers = chapter_detector._extract_chapter_numbers_improved(main_odd_pages)
    pages_near_321 = [p for p in range(316, 327) if p in page_chapter_numbers]
    print(f"  필터링 전 (316~326페이지):")
    for page_num in pages_near_321:
        chapter_num = page_chapter_numbers.get(page_num)
        print(f"    Page {page_num}: chapter_number={chapter_num}")
    
    # 필터링 후
    filtered_numbers = chapter_detector._filter_valid_chapter_numbers(page_chapter_numbers)
    print(f"  필터링 후 (316~326페이지):")
    for page_num in pages_near_321:
        chapter_num = filtered_numbers.get(page_num)
        print(f"    Page {page_num}: chapter_number={chapter_num}")
    
    # 5. 연속성 필터링 로직 실행 결과
    print()
    print("[연속성 필터링 상세]")
    all_numbers = [n for n in page_chapter_numbers.values() if n is not None]
    if all_numbers:
        print(f"  필터링 전 챕터 번호: {sorted(set(all_numbers))}")
        valid_numbers = chapter_detector._find_continuous_sequence(all_numbers)
        print(f"  필터링 후 유효한 챕터 번호: {sorted(valid_numbers)}")
        excluded = set(all_numbers) - valid_numbers
        if excluded:
            print(f"  제외된 챕터 번호: {sorted(excluded)}")
            if 7 in excluded:
                print(f"  [문제 발견] 챕터 7번이 연속성 필터링으로 제외됨!")
    else:
        print(f"  추출된 챕터 번호 없음")
    
    # 6. 본문 끝 페이지 범위 확인
    print()
    print("[본문 끝 페이지 범위 확인]")
    main_end = boundaries["main"]["end"]
    print(f"  본문 끝 페이지: {main_end}")
    print(f"  321페이지가 본문 범위 내: {321 <= main_end}")
    if 321 > main_end:
        print(f"  [문제 발견] 321페이지가 본문 범위 밖으로 판단됨!")
    
    print()
    print("-" * 80)
    print()


def analyze_3d_printer_chapter_4(cache_file: Path, book_info: Dict):
    """3D프린터의모든것의 챕터 4번(241페이지) 미탐지 원인 분석"""
    print("=" * 80)
    print(f"[도서] {book_info['book']} - 챕터 4번(241페이지) 미탐지 원인 분석")
    print(f"[캐시 파일] {cache_file.name}")
    print("=" * 80)
    print()

    # 1. 캐시 파일 로드 및 구조화
    with open(cache_file, "r", encoding="utf-8") as f:
        cache_data = json.load(f)

    if not cache_data.get("elements"):
        print("[ERROR] 캐시 파일에 elements가 없습니다.")
        return

    pdf_parser = PDFParser(api_key=settings.upstage_api_key, clean_output=False)
    structured_elements = pdf_parser._structure_elements(cache_data)
    pages = pdf_parser._split_pages_by_side(structured_elements, force_split=True)
    
    parsed_data = {
        "pages": pages,
        "total_pages": len(pages),
        "total_elements": len(structured_elements),
    }
    
    boundary_detector = ContentBoundaryDetector()
    chapter_detector = ChapterDetector()
    
    # 2. 본문 범위 확인
    boundaries = boundary_detector.detect_boundaries(parsed_data)
    main_pages = boundaries["main"]["pages"]
    print(f"[본문 범위] {main_pages[0]}페이지 ~ {main_pages[-1]}페이지")
    print()
    
    # 3. 235~250페이지 주변 Footer 요소 상세 분석
    target_page = 241
    analysis_range = range(max(1, target_page - 6), min(len(pages) + 1, target_page + 11))
    
    print(f"[235~250페이지 주변 Footer 요소 분석]")
    print(f"  목표: 챕터 4번 시작 페이지 (GT: {target_page}페이지)")
    print()
    
    for page_num in analysis_range:
        page = next((p for p in pages if p["page_number"] == page_num), None)
        if not page:
            continue
        
        is_odd = page_num % 2 == 1
        page_type = "홀수" if is_odd else "짝수"
        
        # 홀수 페이지만 처리 (로직과 동일)
        if not is_odd:
            continue
        
        footer_elements = boundary_detector._get_footer_elements(page)
        
        print(f"[Page {page_num}] ({page_type}) {'[TARGET]' if page_num == target_page else ''}")
        
        if footer_elements:
            print(f"  Footer 요소 개수: {len(footer_elements)}")
            
            # 각 Footer 요소 상세 출력
            for idx, elem in enumerate(footer_elements):
                text = elem.get("text", "").strip()
                category = elem.get("category", "unknown")
                bbox = elem.get("bbox", {})
                x0 = bbox.get("x0", 0.5)
                y0 = bbox.get("y0", 0.0)
                classification = boundary_detector._classify_footer_element(elem)
                
                print(f"    요소 #{idx+1}:")
                print(f"      text='{text[:80]}'")
                print(f"      category={category}, x0={x0:.3f}, y0={y0:.3f}")
                print(f"      분류 결과: {classification}")
                
                # chapter_marker인 경우 챕터 번호 추출 시도
                if classification == "chapter_marker":
                    chapter_number = chapter_detector._extract_chapter_number_from_pattern(text)
                    print(f"      추출된 챕터 번호: {chapter_number}")
        else:
            print(f"  [FAIL] Footer 요소 없음")
        
        print()
    
    # 4. 챕터 번호 추출 결과 (필터링 전/후)
    print("[챕터 번호 추출 분석]")
    main_odd_pages = [p for p in pages if p["page_number"] in main_pages and p["page_number"] % 2 == 1]
    
    # 필터링 전
    page_chapter_numbers = chapter_detector._extract_chapter_numbers_improved(main_odd_pages)
    pages_near_241 = [p for p in range(235, 251) if p in page_chapter_numbers]
    print(f"  필터링 전 (235~250페이지):")
    for page_num in pages_near_241:
        chapter_num = page_chapter_numbers.get(page_num)
        print(f"    Page {page_num}: chapter_number={chapter_num}")
    
    # 필터링 후
    filtered_numbers = chapter_detector._filter_valid_chapter_numbers(page_chapter_numbers)
    print(f"  필터링 후 (235~250페이지):")
    for page_num in pages_near_241:
        chapter_num = filtered_numbers.get(page_num)
        print(f"    Page {page_num}: chapter_number={chapter_num}")
    
    # 5. 연속성 필터링 로직 실행 결과
    print()
    print("[연속성 필터링 상세]")
    all_numbers = [n for n in page_chapter_numbers.values() if n is not None]
    if all_numbers:
        print(f"  필터링 전 챕터 번호: {sorted(set(all_numbers))}")
        valid_numbers = chapter_detector._find_continuous_sequence(all_numbers)
        print(f"  필터링 후 유효한 챕터 번호: {sorted(valid_numbers)}")
        excluded = set(all_numbers) - valid_numbers
        if excluded:
            print(f"  제외된 챕터 번호: {sorted(excluded)}")
            if 4 in excluded:
                print(f"  [문제 발견] 챕터 4번이 연속성 필터링으로 제외됨!")
    else:
        print(f"  추출된 챕터 번호 없음")
    
    # 6. 챕터 경계 탐지 결과
    print()
    print("[챕터 경계 탐지 결과]")
    chapters = chapter_detector.detect_chapters(parsed_data, main_pages)
    detected_chapter_starts = [ch["start_page"] for ch in chapters]
    print(f"  탐지된 챕터 시작: {detected_chapter_starts}")
    print(f"  예상 챕터 시작: {book_info['expected_chapters']}")
    
    # 챕터 4번 확인
    chapter_4 = next((ch for ch in chapters if ch["number"] == 4), None)
    if chapter_4:
        print(f"  챕터 4번: start_page={chapter_4['start_page']}, GT=241, 오차={abs(chapter_4['start_page'] - 241)}페이지")
        if abs(chapter_4['start_page'] - 241) > 3:
            print(f"  [문제 발견] 챕터 4번 시작 페이지 오차 초과 (threshold=3페이지)")
    else:
        print(f"  [문제 발견] 챕터 4번이 탐지되지 않음!")
    
    print()
    print("-" * 80)
    print()


def analyze_3d_printer_pattern(cache_file: Path, book_info: Dict):
    """3D프린터의모든것의 27페이지 Footer 패턴 매칭 분석"""
    print("=" * 80)
    print(f"[도서] {book_info['book']} - 27페이지 Footer 패턴 매칭 분석")
    print(f"[캐시 파일] {cache_file.name}")
    print("=" * 80)
    print()

    # 1. 캐시 파일 로드 및 구조화
    with open(cache_file, "r", encoding="utf-8") as f:
        cache_data = json.load(f)

    if not cache_data.get("elements"):
        print("[ERROR] 캐시 파일에 elements가 없습니다.")
        return

    pdf_parser = PDFParser(api_key=settings.upstage_api_key, clean_output=False)
    structured_elements = pdf_parser._structure_elements(cache_data)
    pages = pdf_parser._split_pages_by_side(structured_elements, force_split=True)
    
    # 2. 27페이지 Footer 요소 확인
    target_page = 27
    page = next((p for p in pages if p["page_number"] == target_page), None)
    if not page:
        print(f"[ERROR] {target_page}페이지를 찾을 수 없습니다.")
        return
    
    boundary_detector = ContentBoundaryDetector()
    footer_elements = boundary_detector._get_footer_elements(page)
    
    print(f"[Page {target_page}] Footer 요소 분석")
    print(f"  Footer 요소 개수: {len(footer_elements)}")
    print()
    
    # 3. 실제 Footer 텍스트 출력
    print("[실제 Footer 텍스트]")
    for idx, elem in enumerate(footer_elements):
        text = elem.get("text", "").strip()
        category = elem.get("category", "unknown")
        bbox = elem.get("bbox", {})
        x0 = bbox.get("x0", 0.5)
        y0 = bbox.get("y0", 0.0)
        
        print(f"  요소 #{idx+1}:")
        print(f"    text='{text}'")
        print(f"    category={category}, x0={x0:.3f}, y0={y0:.3f}")
        print(f"    text 길이: {len(text)}")
        print(f"    text 인코딩 확인: {text.encode('utf-8')[:50]}")
        print()
    
    # 4. 패턴 매칭 테스트
    print("[패턴 매칭 테스트]")
    import re
    
    # 현재 패턴들
    patterns = [
        (r"제\s*\d+\s*[장강부]", "제1장 형식"),
        (r"^\d+\s*[장강부]", "1장 형식"),
        (r"^\d+\.\s*[가-힣]", "1. 제목 형식"),
        (r"^\d+[_\-\s]+[가-힣]", "1_제목, 1-제목, 1 제목 형식 (추가된 패턴)"),
        (r"^0?\d+[_\-\s]+[가-힣]", "01 바빌론 형식 (추가된 패턴)"),
    ]
    
    for elem in footer_elements:
        text = elem.get("text", "").strip()
        print(f"  텍스트: '{text}'")
        
        for pattern_str, pattern_desc in patterns:
            pattern = re.compile(pattern_str)
            match_result = pattern.search(text)
            if match_result:
                print(f"    [매칭] {pattern_desc}: {pattern_str}")
                print(f"      매칭 결과: {match_result.group()}")
            else:
                print(f"    [미매칭] {pattern_desc}: {pattern_str}")
        
        # _classify_footer_element() 결과
        classification = boundary_detector._classify_footer_element(elem)
        print(f"    _classify_footer_element() 결과: {classification}")
        print()
    
    # 5. 패턴 수정 제안
    print("[패턴 수정 제안]")
    for elem in footer_elements:
        text = elem.get("text", "").strip()
        if "1_3D" in text or "1_ 3D" in text:
            print(f"  실제 텍스트: '{text}'")
            print(f"  문제점: 패턴이 매칭되지 않음")
            print(f"  가능한 원인:")
            print(f"    1. 공백 처리 문제: '1_3D' vs '1_ 3D'")
            print(f"    2. 특수문자 문제: 언더스코어 뒤에 숫자/영문이 오는 경우")
            print(f"  제안 패턴:")
            print(f"    - r'^\\d+_[가-힣]' (언더스코어 뒤 한글 필수)")
            print(f"    - r'^\\d+_\\s*[가-힣]' (언더스코어 뒤 공백 허용)")
            print(f"    - r'^\\d+_\\s*[가-힣A-Z]' (언더스코어 뒤 한글/영문 허용)")
    
    print()
    print("-" * 80)
    print()


def analyze_main_end_99경제(cache_file: Path, book_info: Dict):
    """99를위한경제의 본문 끝(278페이지) 판단 원인 분석"""
    print("=" * 80)
    print(f"[도서] {book_info['book']} - 본문 끝 판단 원인 분석")
    print(f"[캐시 파일] {cache_file.name}")
    print("=" * 80)
    print()

    # 1. 캐시 파일 로드 및 구조화
    with open(cache_file, "r", encoding="utf-8") as f:
        cache_data = json.load(f)

    if not cache_data.get("elements"):
        print("[ERROR] 캐시 파일에 elements가 없습니다.")
        return

    pdf_parser = PDFParser(api_key=settings.upstage_api_key, clean_output=False)
    structured_elements = pdf_parser._structure_elements(cache_data)
    pages = pdf_parser._split_pages_by_side(structured_elements, force_split=True)
    
    parsed_data = {
        "pages": pages,
        "total_pages": len(pages),
        "total_elements": len(structured_elements),
    }

    boundary_detector = ContentBoundaryDetector()
    
    # 2. 본문 시작 페이지 확인
    main_start = boundary_detector._detect_main_start_improved(pages)
    print(f"[본문 시작 페이지] {main_start}페이지")
    print()
    
    # 3. _detect_notes_start_improved() 로직 재현
    print("[본문 끝 탐지 로직 분석]")
    print("  _detect_notes_start_improved() 로직:")
    print("    1. 본문 후반부만 검사 (전체의 50% 이후)")
    print("    2. 홀수 페이지만 처리")
    print("    3. Footer 요소에서 종문 키워드 확인 (END_KEYWORDS)")
    print("    4. 종문 키워드 발견 시 그 페이지를 종문 시작으로 판단")
    print()
    
    # 본문 후반부 계산
    search_start_idx = max(main_start, int(len(pages) * 0.5))
    print(f"  전체 페이지 수: {len(pages)}개")
    print(f"  본문 시작 페이지: {main_start}페이지")
    print(f"  검사 시작 인덱스: {search_start_idx} (전체의 50% 또는 본문 시작 중 큰 값)")
    print(f"  검사 시작 페이지: {pages[search_start_idx].get('page_number') if search_start_idx < len(pages) else 'N/A'}페이지")
    print()
    
    # 4. 270~290페이지 주변 Footer 요소 상세 분석
    analysis_range = range(max(1, 270), min(len(pages) + 1, 291))
    print(f"[270~290페이지 주변 Footer 요소 분석]")
    print()
    
    from backend.config.constants import END_KEYWORDS
    
    for page_num in analysis_range:
        page = next((p for p in pages if p["page_number"] == page_num), None)
        if not page:
            continue
        
        is_odd = page_num % 2 == 1
        page_type = "홀수" if is_odd else "짝수"
        
        # 홀수 페이지만 처리 (로직과 동일)
        if not is_odd:
            continue
        
        footer_elements = boundary_detector._get_footer_elements(page)
        footer_text = " ".join([
            elem.get("text", "").strip()
            for elem in footer_elements
            if elem.get("text", "").strip()
        ])
        
        # 종문 키워드 확인
        matched_keywords = [
            keyword
            for keyword in END_KEYWORDS
            if keyword.lower() in footer_text.lower()
        ]
        
        print(f"[Page {page_num}] ({page_type}) {'[TARGET]' if page_num == 279 else ''}")
        print(f"  Footer 요소 개수: {len(footer_elements)}")
        
        if footer_elements:
            for idx, elem in enumerate(footer_elements):
                text = elem.get("text", "").strip()
                category = elem.get("category", "unknown")
                bbox = elem.get("bbox", {})
                x0 = bbox.get("x0", 0.5)
                y0 = bbox.get("y0", 0.0)
                classification = boundary_detector._classify_footer_element(elem)
                
                print(f"    요소 #{idx+1}:")
                print(f"      text='{text[:80]}'")
                print(f"      category={category}, x0={x0:.3f}, y0={y0:.3f}")
                print(f"      분류 결과: {classification}")
        
        print(f"  Footer 텍스트 전체: '{footer_text[:100]}'")
        
        if matched_keywords:
            print(f"  [종문 키워드 발견] {matched_keywords}")
            print(f"  → 이 페이지({page_num})가 종문 시작으로 판단됨")
            print(f"  → 본문 끝 페이지: {page_num - 1}페이지")
            
            # 키워드 매칭 위치 상세 확인
            for keyword in matched_keywords:
                keyword_lower = keyword.lower()
                footer_lower = footer_text.lower()
                if keyword_lower in footer_lower:
                    start_idx = footer_lower.find(keyword_lower)
                    context_start = max(0, start_idx - 20)
                    context_end = min(len(footer_text), start_idx + len(keyword) + 20)
                    context = footer_text[context_start:context_end]
                    print(f"    - 키워드 '{keyword}' 매칭 위치: '{context}'")
        else:
            print(f"  [종문 키워드 없음]")
        
        print()
    
    # 5. 실제 _detect_notes_start_improved() 호출 결과 확인
    print("[실제 탐지 결과 확인]")
    boundaries = boundary_detector.detect_boundaries(parsed_data)
    detected_end_start = boundaries["end"]["start"]
    detected_main_end = boundaries["main"]["end"]
    
    print(f"  탐지된 종문 시작: {detected_end_start}페이지")
    print(f"  탐지된 본문 끝: {detected_main_end}페이지")
    print()
    
    if detected_end_start:
        print(f"  [결론] {detected_end_start}페이지(홀수)에서 종문 키워드 발견")
        print(f"  → 본문 끝: {detected_main_end}페이지")
        print(f"  → 321페이지(챕터 7)는 본문 범위 밖으로 판단됨")
    else:
        print(f"  [결론] 종문 키워드 미발견 → 본문 끝: 전체 마지막 페이지")
    
    print()
    print("-" * 80)
    print()


def main():
    """메인 함수"""
    # 출력 파일 설정
    output_file = PROJECT_ROOT / "data" / "output" / "footer_analysis_detailed.txt"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 출력을 파일과 콘솔 모두로 리다이렉트
    import sys
    
    class TeeOutput:
        def __init__(self, *files):
            self.files = files
        def write(self, obj):
            for f in self.files:
                f.write(obj)
                f.flush()
        def flush(self):
            for f in self.files:
                f.flush()
    
    with open(output_file, "w", encoding="utf-8-sig") as f:
        original_stdout = sys.stdout
        sys.stdout = TeeOutput(original_stdout, f)
        
        try:
            print("=" * 80)
            print("Footer 요소 상세 분석 (성공/실패 도서 비교)")
            print("=" * 80)
            print()
            
            # 실패한 도서 분석만 수행
            print("=" * 80)
            print("실패한 도서 분석")
            print("=" * 80)
            print()
            
            for book_info in failed_books:
                cache_file = CACHE_DIR / f"{book_info['cache_hash']}.json"
                
                if not cache_file.exists():
                    print(f"[ERROR] 캐시 파일 없음: {book_info['book']} - {cache_file.name}")
                    print()
                    continue
                
                # 특정 도서는 전용 분석 함수 사용
                if book_info['book'] == "99를위한경제":
                    analyze_chapter_7_99경제(cache_file, book_info)
                    analyze_main_end_99경제(cache_file, book_info)
                elif book_info['book'] == "3D프린터의모든것":
                    analyze_3d_printer_chapter_4(cache_file, book_info)
                else:
                    # 기존 분석
                    analyze_book_footer(cache_file, book_info)
            
            print(f"\n[INFO] 분석 결과가 저장되었습니다: {output_file}")
        finally:
            sys.stdout = original_stdout


if __name__ == "__main__":
    main()

