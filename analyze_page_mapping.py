"""
원본 페이지 번호와 양면 분리 후 페이지 번호 매핑 분석

분석 목표:
1. 원본 페이지 번호 (JSON의 "page" 필드)와 분리 후 페이지 번호의 매핑 관계
2. 좌/우 분리 로직 확인 (x < 0.5: 좌, x >= 0.5: 우)
3. 좌에 컨텐츠가 없는 경우와 있는 경우의 페이지 넘버링 차이
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
from backend.config.settings import settings

# 프로젝트 루트
CACHE_DIR = PROJECT_ROOT / "data" / "cache" / "upstage"

# 분석 대상 도서
test_books = [
    {
        "book": "1등의 통찰",
        "cache_hash": "8ba9b08c4d926326fbc09606888509ff",
        "status": "success",
    },
    {
        "book": "10년후 이곳은 제2의 강남",
        "cache_hash": "a1fdb6515f0de8f3fd8f5346cb68a496",
        "status": "failed",
    },
    {
        "book": "99를 위한 경제",
        "cache_hash": "e3e5af347c6cfed38027923dff0c621d",
        "status": "failed",
    },
]


def analyze_page_mapping(cache_file: Path, book_info: Dict):
    """원본 페이지와 분리 후 페이지 번호 매핑 분석"""
    print("=" * 80)
    print(f"[도서] {book_info['book']} ({book_info['status']})")
    print(f"[캐시 파일] {cache_file.name}")
    print("=" * 80)
    print()

    # 1. 원본 JSON 로드
    with open(cache_file, "r", encoding="utf-8") as f:
        cache_data = json.load(f)

    if not cache_data.get("elements"):
        print("[ERROR] 캐시 파일에 elements가 없습니다.")
        return

    # 2. PDFParser 인스턴스 생성
    pdf_parser = PDFParser(api_key=settings.upstage_api_key, clean_output=False)

    # 3. _structure_elements() 호출
    print("[1단계] PDFParser._structure_elements() 호출 중...")
    structured_elements = pdf_parser._structure_elements(cache_data)
    print(f"  [OK] 구조화된 elements: {len(structured_elements)}개")
    print()

    # 4. 원본 페이지별로 그룹화 및 좌/우 분석
    print("[2단계] 원본 페이지별 좌/우 요소 분석...")
    CENTERLINE = 0.5
    original_pages_dict = defaultdict(list)
    
    for elem in structured_elements:
        original_page = elem.get("page", 1)
        original_pages_dict[original_page].append(elem)
    
    # 원본 페이지별 좌/우 요소 개수
    original_page_stats = {}
    for original_page in sorted(original_pages_dict.keys()):
        elements = original_pages_dict[original_page]
        left_elements = [e for e in elements if e.get("bbox", {}).get("x0", 0.5) < CENTERLINE]
        right_elements = [e for e in elements if e.get("bbox", {}).get("x0", 0.5) >= CENTERLINE]
        
        original_page_stats[original_page] = {
            "total": len(elements),
            "left": len(left_elements),
            "right": len(right_elements),
            "has_left": len(left_elements) > 0,
            "has_right": len(right_elements) > 0,
        }
    
    # 좌에 컨텐츠가 없는 원본 페이지 확인
    pages_without_left = [p for p, stats in original_page_stats.items() if not stats["has_left"]]
    pages_without_right = [p for p, stats in original_page_stats.items() if not stats["has_right"]]
    
    print(f"  원본 페이지 수: {len(original_page_stats)}개")
    print(f"  좌에 컨텐츠가 없는 원본 페이지: {len(pages_without_left)}개")
    if pages_without_left:
        print(f"    예시: {pages_without_left[:10]}")
    print(f"  우에 컨텐츠가 없는 원본 페이지: {len(pages_without_right)}개")
    if pages_without_right:
        print(f"    예시: {pages_without_right[:10]}")
    print()

    # 5. _split_pages_by_side() 호출
    print("[3단계] PDFParser._split_pages_by_side() 호출 중...")
    pages = pdf_parser._split_pages_by_side(structured_elements, force_split=True)
    print(f"  [OK] 분리된 페이지: {len(pages)}개")
    print()

    # 6. 매핑 테이블 생성
    print("[4단계] 원본 페이지 → 분리 후 페이지 번호 매핑 테이블 생성...")
    mapping_table = defaultdict(list)
    
    for page in pages:
        original_page = page.get("original_page")
        split_page_num = page.get("page_number")
        side = page.get("side", "unknown")
        
        if original_page:
            mapping_table[original_page].append({
                "split_page": split_page_num,
                "side": side,
            })
    
    # 매핑 테이블 출력 (처음 20개 원본 페이지)
    print("  매핑 테이블 (처음 20개 원본 페이지):")
    print("  원본 페이지 | 좌 요소 | 우 요소 | 분리 후 페이지 번호")
    print("  " + "-" * 70)
    
    for original_page in sorted(mapping_table.keys())[:20]:
        stats = original_page_stats[original_page]
        mappings = sorted(mapping_table[original_page], key=lambda x: x["split_page"])
        split_pages = [f"{m['split_page']}({m['side']})" for m in mappings]
        
        left_info = f"{stats['left']}개" if stats['has_left'] else "없음"
        right_info = f"{stats['right']}개" if stats['has_right'] else "없음"
        
        print(f"  {original_page:3d}        | {left_info:6s} | {right_info:6s} | {', '.join(split_pages)}")
    
    print()

    # 7. 좌에 컨텐츠가 없는 경우와 있는 경우 비교
    print("[5단계] 좌에 컨텐츠가 없는 경우와 있는 경우 비교...")
    
    # 첫 번째 원본 페이지 분석
    first_original_page = min(original_page_stats.keys())
    first_stats = original_page_stats[first_original_page]
    first_mappings = sorted(mapping_table[first_original_page], key=lambda x: x["split_page"])
    
    print(f"  첫 번째 원본 페이지 ({first_original_page}):")
    print(f"    좌 요소: {first_stats['left']}개 ({'있음' if first_stats['has_left'] else '없음'})")
    print(f"    우 요소: {first_stats['right']}개 ({'있음' if first_stats['has_right'] else '없음'})")
    print(f"    분리 후 페이지 번호: {[m['split_page'] for m in first_mappings]}")
    
    if first_stats['has_left']:
        print(f"    → 좌가 1페이지, 우가 2페이지가 됨")
    else:
        print(f"    → 좌 없음, 우가 1페이지가 됨")
    print()

    # 8. chapter_marker가 있는 원본 페이지 확인
    print("[6단계] chapter_marker가 있는 원본 페이지 확인...")
    boundary_detector = ContentBoundaryDetector()
    
    # 분리 후 페이지에서 chapter_marker 찾기
    chapter_marker_pages = []
    for page in pages:
        footer_elements = boundary_detector._get_footer_elements(page)
        for elem in footer_elements:
            if boundary_detector._classify_footer_element(elem) == "chapter_marker":
                original_page = page.get("original_page")
                split_page = page.get("page_number")
                side = page.get("side", "unknown")
                text = elem.get("text", "").strip()[:50]
                chapter_marker_pages.append({
                    "original_page": original_page,
                    "split_page": split_page,
                    "side": side,
                    "text": text,
                })
                break  # 한 페이지당 하나만
    
    if chapter_marker_pages:
        print(f"  chapter_marker가 있는 페이지: {len(chapter_marker_pages)}개")
        print("  원본 페이지 | 분리 후 페이지 | 좌/우 | 텍스트")
        print("  " + "-" * 70)
        for item in chapter_marker_pages[:10]:  # 처음 10개
            print(f"  {item['original_page']:3d}        | {item['split_page']:3d}           | {item['side']:4s} | {item['text']}")
    else:
        print("  chapter_marker가 있는 페이지 없음")
    print()

    # 9. 홀수/짝수 페이지 분석
    print("[7단계] 분리 후 페이지 번호의 홀수/짝수 분석...")
    odd_pages_with_marker = [p for p in chapter_marker_pages if p['split_page'] % 2 == 1]
    even_pages_with_marker = [p for p in chapter_marker_pages if p['split_page'] % 2 == 0]
    
    print(f"  chapter_marker가 있는 홀수 페이지: {len(odd_pages_with_marker)}개")
    print(f"  chapter_marker가 있는 짝수 페이지: {len(even_pages_with_marker)}개")
    
    if odd_pages_with_marker:
        print(f"    홀수 페이지 예시: {[p['split_page'] for p in odd_pages_with_marker[:5]]}")
    if even_pages_with_marker:
        print(f"    짝수 페이지 예시: {[p['split_page'] for p in even_pages_with_marker[:5]]}")
    print()

    print("-" * 80)
    print()


def main():
    """메인 함수"""
    output_file = PROJECT_ROOT / "data" / "output" / "page_mapping_analysis.txt"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
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
    
    with open(output_file, "w", encoding="utf-8") as f:
        original_stdout = sys.stdout
        sys.stdout = TeeOutput(original_stdout, f)
        
        try:
            print("=" * 80)
            print("원본 페이지 번호와 양면 분리 후 페이지 번호 매핑 분석")
            print("=" * 80)
            print()
            
            for book_info in test_books:
                cache_file = CACHE_DIR / f"{book_info['cache_hash']}.json"
                
                if not cache_file.exists():
                    print(f"[ERROR] 캐시 파일 없음: {book_info['book']} - {cache_file.name}")
                    print()
                    continue
                
                analyze_page_mapping(cache_file, book_info)
            
            print(f"\n[INFO] 분석 결과가 저장되었습니다: {output_file}")
        finally:
            sys.stdout = original_stdout


if __name__ == "__main__":
    main()

