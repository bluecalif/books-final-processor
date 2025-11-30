"""
Extraction 토큰 통계 수집 및 리포트 생성 스크립트

Extraction Service 실행 후 생성된 토큰 통계 파일들을 수집하여 리포트를 생성합니다.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List
from collections import defaultdict
from backend.config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_token_stats() -> List[Dict[str, Any]]:
    """
    토큰 통계 파일들을 로드

    Returns:
        토큰 통계 리스트
    """
    stats_dir = settings.output_dir / "token_stats"
    if not stats_dir.exists():
        logger.warning(f"[WARNING] Token stats directory not found: {stats_dir}")
        return []

    stats_files = list(stats_dir.glob("book_*_tokens.json"))
    logger.info(f"[INFO] Found {len(stats_files)} token stats files")

    stats_list = []
    for stats_file in stats_files:
        try:
            with open(stats_file, "r", encoding="utf-8") as f:
                stats = json.load(f)
                stats_list.append(stats)
        except Exception as e:
            logger.warning(f"[WARNING] Failed to load {stats_file}: {e}")

    return stats_list


def calculate_summary_stats(stats_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    전체 통계 계산

    Args:
        stats_list: 토큰 통계 리스트

    Returns:
        전체 통계 딕셔너리
    """
    total_pages_input = 0
    total_pages_output = 0
    total_pages_cost = 0.0
    total_pages_count = 0

    total_chapters_input = 0
    total_chapters_output = 0
    total_chapters_cost = 0.0
    total_chapters_count = 0

    category_stats = defaultdict(
        lambda: {
            "pages": {"input": 0, "output": 0, "cost": 0.0, "count": 0},
            "chapters": {"input": 0, "output": 0, "cost": 0.0, "count": 0},
            "book_count": 0,
        }
    )

    for stats in stats_list:
        book_id = stats.get("book_id")
        pages_stats = stats.get("pages", {})
        chapters_stats = stats.get("chapters", {})

        # 전체 통계 누적
        total_pages_input += pages_stats.get("total_input_tokens", 0)
        total_pages_output += pages_stats.get("total_output_tokens", 0)
        total_pages_cost += pages_stats.get("total_cost", 0.0)
        total_pages_count += pages_stats.get("page_count", 0)

        total_chapters_input += chapters_stats.get("total_input_tokens", 0)
        total_chapters_output += chapters_stats.get("total_output_tokens", 0)
        total_chapters_cost += chapters_stats.get("total_cost", 0.0)
        total_chapters_count += chapters_stats.get("chapter_count", 0)

        # 분야별 통계 (book_id로 DB 조회 필요하지만, 여기서는 간단히 처리)
        # 실제로는 DB에서 category를 가져와야 함

    return {
        "total": {
            "pages": {
                "input_tokens": total_pages_input,
                "output_tokens": total_pages_output,
                "cost_usd": total_pages_cost,
                "page_count": total_pages_count,
                "avg_input_per_page": (
                    total_pages_input / total_pages_count if total_pages_count > 0 else 0
                ),
                "avg_output_per_page": (
                    total_pages_output / total_pages_count if total_pages_count > 0 else 0
                ),
                "avg_cost_per_page": (
                    total_pages_cost / total_pages_count if total_pages_count > 0 else 0.0
                ),
            },
            "chapters": {
                "input_tokens": total_chapters_input,
                "output_tokens": total_chapters_output,
                "cost_usd": total_chapters_cost,
                "chapter_count": total_chapters_count,
                "avg_input_per_chapter": (
                    total_chapters_input / total_chapters_count
                    if total_chapters_count > 0
                    else 0
                ),
                "avg_output_per_chapter": (
                    total_chapters_output / total_chapters_count
                    if total_chapters_count > 0
                    else 0
                ),
                "avg_cost_per_chapter": (
                    total_chapters_cost / total_chapters_count
                    if total_chapters_count > 0
                    else 0.0
                ),
            },
            "grand_total": {
                "input_tokens": total_pages_input + total_chapters_input,
                "output_tokens": total_pages_output + total_chapters_output,
                "cost_usd": total_pages_cost + total_chapters_cost,
            },
        },
        "by_category": dict(category_stats),
        "book_count": len(stats_list),
    }


def generate_text_report(summary_stats: Dict[str, Any]) -> str:
    """
    텍스트 리포트 생성

    Args:
        summary_stats: 전체 통계

    Returns:
        리포트 텍스트
    """
    total = summary_stats["total"]
    pages = total["pages"]
    chapters = total["chapters"]
    grand_total = total["grand_total"]

    report = f"""
========================================
Extraction Token Usage Report
========================================

Total Books Processed: {summary_stats['book_count']}

--- Page Extraction ---
Total Pages: {pages['page_count']}
Total Input Tokens: {pages['input_tokens']:,}
Total Output Tokens: {pages['output_tokens']:,}
Total Cost: ${pages['cost_usd']:.4f}
Average Input per Page: {pages['avg_input_per_page']:.0f} tokens
Average Output per Page: {pages['avg_output_per_page']:.0f} tokens
Average Cost per Page: ${pages['avg_cost_per_page']:.6f}

--- Chapter Structuring ---
Total Chapters: {chapters['chapter_count']}
Total Input Tokens: {chapters['input_tokens']:,}
Total Output Tokens: {chapters['output_tokens']:,}
Total Cost: ${chapters['cost_usd']:.4f}
Average Input per Chapter: {chapters['avg_input_per_chapter']:.0f} tokens
Average Output per Chapter: {chapters['avg_output_per_chapter']:.0f} tokens
Average Cost per Chapter: ${chapters['avg_cost_per_chapter']:.6f}

--- Grand Total ---
Total Input Tokens: {grand_total['input_tokens']:,}
Total Output Tokens: {grand_total['output_tokens']:,}
Total Cost: ${grand_total['cost_usd']:.4f}

========================================
"""
    return report


def main():
    """메인 함수"""
    logger.info("[INFO] Starting token statistics collection...")

    # 1. 토큰 통계 파일 로드
    stats_list = load_token_stats()
    if not stats_list:
        logger.warning("[WARNING] No token stats files found")
        return

    # 2. 전체 통계 계산
    summary_stats = calculate_summary_stats(stats_list)

    # 3. JSON 리포트 저장
    report_dir = settings.output_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    json_report_file = report_dir / "extraction_token_stats.json"
    with open(json_report_file, "w", encoding="utf-8") as f:
        json.dump(
            {"summary": summary_stats, "details": stats_list},
            f,
            ensure_ascii=False,
            indent=2,
        )
    logger.info(f"[INFO] JSON report saved to {json_report_file}")

    # 4. 텍스트 리포트 생성 및 저장
    text_report = generate_text_report(summary_stats)
    text_report_file = report_dir / "extraction_token_stats.txt"
    with open(text_report_file, "w", encoding="utf-8") as f:
        f.write(text_report)
    logger.info(f"[INFO] Text report saved to {text_report_file}")

    # 5. 콘솔 출력
    print(text_report)

    logger.info("[INFO] Token statistics collection completed")


if __name__ == "__main__":
    main()

