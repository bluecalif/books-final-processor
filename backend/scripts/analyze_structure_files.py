"""
구조 파일 분석 스크립트

data/output/structure/ 디렉토리의 모든 구조 파일을 분석하여:
- 중복된 order_index
- 중복된 챕터 제목
- 소량 페이지 챕터 (2-3페이지 이하)
- 페이지 범위 겹침
- 기타 문제 사례

를 찾아보고 보고서를 생성합니다.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def analyze_structure_file(structure_file: Path) -> Optional[Dict[str, Any]]:
    """
    구조 파일 하나를 분석
    
    Returns:
        분석 결과 딕셔너리 또는 None (파일 읽기 실패 시)
    """
    try:
        with open(structure_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        book_id = data.get("book_id")
        book_title = data.get("book_title", "Unknown")
        structure = data.get("structure", {})
        chapters = structure.get("chapters", [])
        
        if not chapters:
            return None
        
        # 분석 결과
        analysis = {
            "book_id": book_id,
            "book_title": book_title,
            "file_path": str(structure_file),
            "total_chapters": len(chapters),
            "issues": {
                "duplicate_order_index": [],
                "duplicate_titles": [],
                "small_chapters": [],  # 2-3페이지 이하
                "overlapping_pages": [],
                "invalid_order_sequence": False,
            },
            "chapter_details": [],
        }
        
        # 챕터 상세 정보 수집
        order_indices = []
        titles = []
        chapter_list = []
        
        for ch in chapters:
            order_idx = ch.get("order_index")
            title = ch.get("title", "")
            start_page = ch.get("start_page")
            end_page = ch.get("end_page")
            page_count = end_page - start_page + 1 if start_page and end_page else 0
            
            order_indices.append(order_idx)
            titles.append(title)
            chapter_list.append({
                "order_index": order_idx,
                "title": title,
                "start_page": start_page,
                "end_page": end_page,
                "page_count": page_count,
            })
        
        analysis["chapter_details"] = chapter_list
        
        # 1. 중복된 order_index 확인
        order_index_count = defaultdict(list)
        for idx, ch in enumerate(chapters):
            order_idx = ch.get("order_index")
            order_index_count[order_idx].append(idx)
        
        for order_idx, indices in order_index_count.items():
            if len(indices) > 1:
                duplicate_chapters = [chapters[i] for i in indices]
                analysis["issues"]["duplicate_order_index"].append({
                    "order_index": order_idx,
                    "count": len(indices),
                    "chapters": [
                        {
                            "title": ch.get("title", ""),
                            "start_page": ch.get("start_page"),
                            "end_page": ch.get("end_page"),
                            "page_count": ch.get("end_page", 0) - ch.get("start_page", 0) + 1,
                        }
                        for ch in duplicate_chapters
                    ]
                })
        
        # 2. 중복된 제목 확인 (같은 제목이 여러 번 나타남)
        title_count = defaultdict(list)
        for idx, ch in enumerate(chapters):
            title = ch.get("title", "").strip()
            if title:  # 빈 제목은 제외
                title_count[title].append(idx)
        
        for title, indices in title_count.items():
            if len(indices) > 1:
                duplicate_chapters = [chapters[i] for i in indices]
                analysis["issues"]["duplicate_titles"].append({
                    "title": title,
                    "count": len(indices),
                    "chapters": [
                        {
                            "order_index": ch.get("order_index"),
                            "start_page": ch.get("start_page"),
                            "end_page": ch.get("end_page"),
                            "page_count": ch.get("end_page", 0) - ch.get("start_page", 0) + 1,
                        }
                        for ch in duplicate_chapters
                    ]
                })
        
        # 3. 소량 페이지 챕터 확인 (2-3페이지 이하)
        for ch in chapters:
            start_page = ch.get("start_page")
            end_page = ch.get("end_page")
            if start_page and end_page:
                page_count = end_page - start_page + 1
                if page_count <= 3:
                    analysis["issues"]["small_chapters"].append({
                        "order_index": ch.get("order_index"),
                        "title": ch.get("title", ""),
                        "start_page": start_page,
                        "end_page": end_page,
                        "page_count": page_count,
                    })
        
        # 4. 페이지 범위 겹침 확인
        for i, ch1 in enumerate(chapters):
            start1 = ch1.get("start_page")
            end1 = ch1.get("end_page")
            if not start1 or not end1:
                continue
            
            for j, ch2 in enumerate(chapters):
                if i >= j:
                    continue
                
                start2 = ch2.get("start_page")
                end2 = ch2.get("end_page")
                if not start2 or not end2:
                    continue
                
                # 페이지 범위 겹침 확인
                if not (end1 < start2 or end2 < start1):
                    # 겹침 발생
                    overlap_start = max(start1, start2)
                    overlap_end = min(end1, end2)
                    overlap_pages = overlap_end - overlap_start + 1
                    
                    analysis["issues"]["overlapping_pages"].append({
                        "chapter1": {
                            "order_index": ch1.get("order_index"),
                            "title": ch1.get("title", ""),
                            "start_page": start1,
                            "end_page": end1,
                        },
                        "chapter2": {
                            "order_index": ch2.get("order_index"),
                            "title": ch2.get("title", ""),
                            "start_page": start2,
                            "end_page": end2,
                        },
                        "overlap_pages": overlap_pages,
                        "overlap_range": f"{overlap_start}~{overlap_end}",
                    })
        
        # 5. order_index 순서 문제 확인 (비연속적이거나 순서가 맞지 않는 경우)
        sorted_order_indices = sorted([ch.get("order_index") for ch in chapters])
        expected_sequence = list(range(len(chapters)))
        if sorted_order_indices != expected_sequence:
            analysis["issues"]["invalid_order_sequence"] = True
            analysis["issues"]["order_sequence"] = sorted_order_indices
            analysis["issues"]["expected_sequence"] = expected_sequence
        
        return analysis
        
    except Exception as e:
        logger.error(f"[ERROR] Failed to analyze {structure_file.name}: {e}")
        return None


def analyze_all_structure_files(structure_dir: Path) -> Dict[str, Any]:
    """모든 구조 파일 분석"""
    logger.info(f"[INFO] Analyzing structure files in: {structure_dir}")
    
    structure_files = list(structure_dir.glob("*_structure.json"))
    logger.info(f"[INFO] Found {len(structure_files)} structure files")
    
    results = {
        "analysis_date": datetime.now().isoformat(),
        "total_files": len(structure_files),
        "successful_analyses": 0,
        "failed_analyses": 0,
        "books_with_issues": [],
        "summary": {
            "duplicate_order_index_count": 0,
            "duplicate_title_count": 0,
            "small_chapter_count": 0,
            "overlapping_pages_count": 0,
            "invalid_order_sequence_count": 0,
        },
        "detailed_results": [],
    }
    
    for structure_file in structure_files:
        analysis = analyze_structure_file(structure_file)
        if analysis:
            results["successful_analyses"] += 1
            results["detailed_results"].append(analysis)
            
            # 문제가 있는 책인지 확인
            issues = analysis["issues"]
            has_issues = (
                len(issues["duplicate_order_index"]) > 0 or
                len(issues["duplicate_titles"]) > 0 or
                len(issues["small_chapters"]) > 0 or
                len(issues["overlapping_pages"]) > 0 or
                issues["invalid_order_sequence"]
            )
            
            if has_issues:
                results["books_with_issues"].append({
                    "book_id": analysis["book_id"],
                    "book_title": analysis["book_title"],
                    "file_path": analysis["file_path"],
                    "issue_types": [
                        ("duplicate_order_index", len(issues["duplicate_order_index"])),
                        ("duplicate_titles", len(issues["duplicate_titles"])),
                        ("small_chapters", len(issues["small_chapters"])),
                        ("overlapping_pages", len(issues["overlapping_pages"])),
                        ("invalid_order_sequence", 1 if issues["invalid_order_sequence"] else 0),
                    ],
                })
                
                # 통계 업데이트
                results["summary"]["duplicate_order_index_count"] += len(issues["duplicate_order_index"])
                results["summary"]["duplicate_title_count"] += len(issues["duplicate_titles"])
                results["summary"]["small_chapter_count"] += len(issues["small_chapters"])
                results["summary"]["overlapping_pages_count"] += len(issues["overlapping_pages"])
                if issues["invalid_order_sequence"]:
                    results["summary"]["invalid_order_sequence_count"] += 1
        else:
            results["failed_analyses"] += 1
    
    logger.info(f"[INFO] Analysis complete: {results['successful_analyses']} successful, {results['failed_analyses']} failed")
    logger.info(f"[INFO] Books with issues: {len(results['books_with_issues'])}")
    
    return results


def generate_report(results: Dict[str, Any], output_file: Path) -> None:
    """분석 결과를 마크다운 보고서로 생성"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# 구조 파일 분석 보고서\n\n")
        f.write(f"**분석 일시**: {results['analysis_date']}\n\n")
        f.write(f"**분석 대상**: {results['total_files']}개 구조 파일\n\n")
        f.write(f"**분석 성공**: {results['successful_analyses']}개\n\n")
        f.write(f"**분석 실패**: {results['failed_analyses']}개\n\n")
        
        f.write("## 요약 통계\n\n")
        summary = results["summary"]
        f.write(f"- 중복된 order_index: {summary['duplicate_order_index_count']}건\n")
        f.write(f"- 중복된 챕터 제목: {summary['duplicate_title_count']}건\n")
        f.write(f"- 소량 페이지 챕터 (2-3페이지 이하): {summary['small_chapter_count']}개\n")
        f.write(f"- 페이지 범위 겹침: {summary['overlapping_pages_count']}건\n")
        f.write(f"- order_index 순서 문제: {summary['invalid_order_sequence_count']}건\n\n")
        
        f.write(f"## 문제가 있는 책 ({len(results['books_with_issues'])}권)\n\n")
        
        for book_info in results["books_with_issues"]:
            f.write(f"### Book ID {book_info['book_id']}: {book_info['book_title']}\n\n")
            f.write(f"**파일**: `{Path(book_info['file_path']).name}`\n\n")
            
            # 해당 책의 상세 분석 결과 찾기
            detailed = next(
                (r for r in results["detailed_results"] if r["book_id"] == book_info["book_id"]),
                None
            )
            
            if detailed:
                issues = detailed["issues"]
                
                # 중복된 order_index
                if issues["duplicate_order_index"]:
                    f.write("#### 중복된 order_index\n\n")
                    for dup in issues["duplicate_order_index"]:
                        f.write(f"- `order_index: {dup['order_index']}` (중복 {dup['count']}회)\n")
                        for ch in dup["chapters"]:
                            f.write(f"  - `{ch['title']}`: {ch['start_page']}~{ch['end_page']} ({ch['page_count']}페이지)\n")
                    f.write("\n")
                
                # 중복된 제목
                if issues["duplicate_titles"]:
                    f.write("#### 중복된 챕터 제목\n\n")
                    for dup in issues["duplicate_titles"]:
                        f.write(f"- `{dup['title']}` (중복 {dup['count']}회)\n")
                        for ch in dup["chapters"]:
                            f.write(f"  - order_index: {ch['order_index']}, {ch['start_page']}~{ch['end_page']} ({ch['page_count']}페이지)\n")
                    f.write("\n")
                
                # 소량 페이지 챕터
                if issues["small_chapters"]:
                    f.write("#### 소량 페이지 챕터 (2-3페이지 이하)\n\n")
                    for small in issues["small_chapters"]:
                        f.write(f"- `order_index: {small['order_index']}`, `{small['title']}`: {small['start_page']}~{small['end_page']} ({small['page_count']}페이지)\n")
                    f.write("\n")
                
                # 페이지 범위 겹침
                if issues["overlapping_pages"]:
                    f.write("#### 페이지 범위 겹침\n\n")
                    for overlap in issues["overlapping_pages"]:
                        ch1 = overlap["chapter1"]
                        ch2 = overlap["chapter2"]
                        f.write(f"- `{ch1['title']}` (order_index: {ch1['order_index']}, {ch1['start_page']}~{ch1['end_page']}) ")
                        f.write(f"vs `{ch2['title']}` (order_index: {ch2['order_index']}, {ch2['start_page']}~{ch2['end_page']})\n")
                        f.write(f"  - 겹침 범위: {overlap['overlap_range']} ({overlap['overlap_pages']}페이지)\n")
                    f.write("\n")
                
                # order_index 순서 문제
                if issues["invalid_order_sequence"]:
                    f.write("#### order_index 순서 문제\n\n")
                    f.write(f"- 실제 순서: {issues['order_sequence']}\n")
                    f.write(f"- 예상 순서: {issues['expected_sequence']}\n\n")
            
            f.write("---\n\n")
        
        # AI지도책 사례 상세
        ai_book = next(
            (r for r in results["detailed_results"] if "AI지도책" in r.get("book_title", "")),
            None
        )
        if ai_book:
            f.write("## 참고: AI지도책 상세 사례\n\n")
            f.write(f"Book ID: {ai_book['book_id']}\n\n")
            f.write("이 책은 중복된 소량 페이지 챕터로 인해 이후 처리가 어려워진 대표 사례입니다.\n\n")
            f.write("### 챕터 구조\n\n")
            for ch in ai_book["chapter_details"]:
                f.write(f"- order_index: {ch['order_index']}, `{ch['title']}`: {ch['start_page']}~{ch['end_page']} ({ch['page_count']}페이지)\n")
            f.write("\n")
            f.write("### 문제점\n\n")
            issues = ai_book["issues"]
            if issues["duplicate_order_index"]:
                f.write("1. **중복된 order_index**:\n")
                for dup in issues["duplicate_order_index"]:
                    f.write(f"   - `order_index: {dup['order_index']}`가 {dup['count']}번 나타남\n")
                f.write("\n")
            if issues["small_chapters"]:
                f.write("2. **소량 페이지 챕터**:\n")
                for small in issues["small_chapters"]:
                    f.write(f"   - `{small['title']}`: {small['page_count']}페이지 (order_index: {small['order_index']})\n")
                f.write("\n")
            if issues["overlapping_pages"]:
                f.write("3. **페이지 범위 겹침**:\n")
                for overlap in issues["overlapping_pages"]:
                    f.write(f"   - {overlap['overlap_range']} 범위에서 겹침 발생\n")
                f.write("\n")
            f.write("### 영향\n\n")
            f.write("- 이후 페이지 엔티티 추출 시 챕터 매핑이 혼란스러울 수 있음\n")
            f.write("- 챕터 서머리 생성 시 중복 데이터 처리 문제 발생 가능\n")
            f.write("- 현재는 2페이지 이하 챕터 스킵 로직으로 일부 완화됨\n\n")
    
    logger.info(f"[INFO] Report saved to: {output_file}")


def main():
    """메인 함수"""
    from backend.config.settings import settings
    
    structure_dir = settings.output_dir / "structure"
    if not structure_dir.exists():
        logger.error(f"[ERROR] Structure directory not found: {structure_dir}")
        return
    
    # 분석 실행
    results = analyze_all_structure_files(structure_dir)
    
    # JSON 결과 저장
    output_dir = settings.output_dir / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    json_output = output_dir / f"structure_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info(f"[INFO] JSON results saved to: {json_output}")
    
    # 마크다운 보고서 생성
    report_output = output_dir / f"structure_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    generate_report(results, report_output)
    
    # 콘솔 출력
    print("\n" + "=" * 80)
    print("구조 파일 분석 완료")
    print("=" * 80)
    print(f"\n총 분석 파일: {results['total_files']}개")
    print(f"분석 성공: {results['successful_analyses']}개")
    print(f"문제가 있는 책: {len(results['books_with_issues'])}권\n")
    
    print("요약 통계:")
    summary = results["summary"]
    print(f"  - 중복된 order_index: {summary['duplicate_order_index_count']}건")
    print(f"  - 중복된 챕터 제목: {summary['duplicate_title_count']}건")
    print(f"  - 소량 페이지 챕터: {summary['small_chapter_count']}개")
    print(f"  - 페이지 범위 겹침: {summary['overlapping_pages_count']}건")
    print(f"  - order_index 순서 문제: {summary['invalid_order_sequence_count']}건\n")
    
    if results["books_with_issues"]:
        print("문제가 있는 책 목록:")
        for book_info in results["books_with_issues"]:
            issue_types_str = ", ".join([f"{name}({count})" for name, count in book_info["issue_types"] if count > 0])
            print(f"  - Book ID {book_info['book_id']}: {book_info['book_title']} [{issue_types_str}]")
    
    print(f"\n상세 보고서: {report_output}")
    print(f"JSON 결과: {json_output}")
    print("=" * 80)


if __name__ == "__main__":
    main()

