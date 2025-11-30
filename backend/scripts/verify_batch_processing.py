"""
대량 도서 처리 결과 검증 스크립트

로그 파일과 디렉토리를 분석하여 각 도서의 생성물(캐시, 구조, 텍스트 파일)이 
제대로 만들어졌는지 확인하고 리포트를 생성합니다.
"""
import logging
import sys
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import defaultdict

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session

from backend.api.database import SessionLocal
from backend.api.models.book import Book, BookStatus
from backend.config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_log_file(log_file: Path) -> Dict[str, Any]:
    """
    로그 파일 파싱하여 도서별 처리 결과 추출
    
    Args:
        log_file: 로그 파일 경로
        
    Returns:
        도서별 처리 결과 딕셔너리
    """
    if not log_file.exists():
        logger.error(f"[ERROR] 로그 파일이 존재하지 않습니다: {log_file}")
        return {}
    
    logger.info(f"[INFO] 로그 파일 파싱 중: {log_file}")
    
    books_data = {}  # {book_id: {...}} 또는 {title: {...}} 형태
    books_by_id = {}  # book_id로 빠르게 찾기 위한 딕셔너리
    books_by_title = {}  # title로 빠르게 찾기 위한 딕셔너리
    
    def get_or_create_book(book_id: Optional[int] = None, title: Optional[str] = None):
        """책 정보 가져오기 또는 생성"""
        book = None
        
        # book_id로 찾기
        if book_id and book_id in books_by_id:
            book = books_by_id[book_id]
        
        # title로 찾기
        if not book and title and title in books_by_title:
            book = books_by_title[title]
        
        # 없으면 새로 생성
        if not book:
            book = {
                "title": title or "Unknown",
                "status": "unknown",
                "book_id": book_id,
                "steps": {
                    "pdf_found": False,
                    "book_created": False,
                    "parsing": "unknown",
                    "structure": "unknown",
                    "text_file": "unknown",
                },
                "output_files": {
                    "cache_file": None,
                    "structure_file": None,
                    "text_file": None,
                },
                "errors": [],
            }
            
            # 딕셔너리에 추가
            if book_id:
                books_by_id[book_id] = book
                books_data[book_id] = book
            if title:
                books_by_title[title] = book
                if title not in books_data:
                    books_data[title] = book
        
        # 정보 업데이트
        if book_id and not book["book_id"]:
            book["book_id"] = book_id
            books_by_id[book_id] = book
            books_data[book_id] = book
        if title and book["title"] == "Unknown":
            book["title"] = title
            books_by_title[title] = book
            if title not in books_data:
                books_data[title] = book
        
        return book
    
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            # 책 처리 시작 (기존 패턴)
            if "[BOOK] 처리 시작:" in line:
                match = re.search(r'처리 시작: (.+)', line)
                if match:
                    title = match.group(1).strip()
                    get_or_create_book(title=title)
            
            # Book ID 추출 (여러 패턴)
            book_id_match = None
            title_match = None
            
            # "[PHASE 1] 새 Book 레코드 생성: ID {book_id}"
            if "[PHASE 1] 새 Book 레코드 생성:" in line or "[STEP 2] 새 Book 레코드 생성:" in line:
                match = re.search(r'ID (\d+)', line)
                if match:
                    book_id = int(match.group(1))
                    get_or_create_book(book_id=book_id)
            
            # "[PHASE 2] 파싱 시작: ID {book_id}, {csv_title}"
            if "[PHASE 2] 파싱 시작:" in line:
                match = re.search(r'ID (\d+),\s*(.+)', line)
                if match:
                    book_id = int(match.group(1))
                    title = match.group(2).strip()
                    book = get_or_create_book(book_id=book_id, title=title)
            
            # "[PHASE 3] 구조 분석 시작: ID {book_id}, {csv_title}"
            if "[PHASE 3] 구조 분석 시작:" in line:
                match = re.search(r'ID (\d+),\s*(.+)', line)
                if match:
                    book_id = int(match.group(1))
                    title = match.group(2).strip()
                    book = get_or_create_book(book_id=book_id, title=title)
            
            # "[PHASE 4] 텍스트 정리 시작: ID {book_id}, {csv_title}"
            if "[PHASE 4] 텍스트 정리 시작:" in line:
                match = re.search(r'ID (\d+),\s*(.+)', line)
                if match:
                    book_id = int(match.group(1))
                    title = match.group(2).strip()
                    book = get_or_create_book(book_id=book_id, title=title)
            
            # "Book ID {book_id}" 패턴
            if "Book ID" in line:
                match = re.search(r'Book ID (\d+)', line)
                if match:
                    book_id = int(match.group(1))
                    get_or_create_book(book_id=book_id)
            
            # book_id 추출 헬퍼 함수
            def get_book_id_from_line(line: str) -> Optional[int]:
                """라인에서 book_id 추출"""
                # "[PHASE X] ... ID {book_id}, ..." 패턴
                match = re.search(r'ID (\d+)', line)
                if match:
                    return int(match.group(1))
                return None
            
            def get_book_by_id(book_id: int) -> Optional[Dict[str, Any]]:
                """book_id로 책 찾기"""
                if book_id in books_by_id:
                    return books_by_id[book_id]
                return None
            
            # PDF 파일 찾기
            if "[STEP 1] PDF 파일 발견:" in line:
                book_id = get_book_id_from_line(line)
                if book_id:
                    book = get_book_by_id(book_id)
                    if book:
                        book["steps"]["pdf_found"] = True
            elif "[WARNING] PDF 파일을 찾을 수 없습니다" in line:
                book_id = get_book_id_from_line(line)
                if book_id:
                    book = get_book_by_id(book_id)
                    if book:
                        book["steps"]["pdf_found"] = False
                        book["errors"].append("PDF 파일을 찾을 수 없음")
            
            # Book 레코드 생성
            if "[PHASE 1] 새 Book 레코드 생성:" in line or "[STEP 2] 새 Book 레코드 생성:" in line:
                book_id = get_book_id_from_line(line)
                if book_id:
                    book = get_book_by_id(book_id)
                    if book:
                        book["steps"]["book_created"] = True
            
            # 파싱 상태
            if "[PHASE 2] 파싱 완료:" in line or "[STEP 3] PDF 파싱 완료:" in line:
                book_id = get_book_id_from_line(line)
                if book_id:
                    book = get_book_by_id(book_id)
                    if book:
                        book["steps"]["parsing"] = "success"
            elif "[PHASE 2] 이미 파싱됨:" in line or "[STEP 3] 이미 파싱됨:" in line:
                book_id = get_book_id_from_line(line)
                if book_id:
                    book = get_book_by_id(book_id)
                    if book:
                        book["steps"]["parsing"] = "skipped"
            elif "[PHASE 2] 파싱 실패:" in line or "[ERROR]" in line and "파싱" in line:
                book_id = get_book_id_from_line(line)
                if book_id:
                    book = get_book_by_id(book_id)
                    if book:
                        book["steps"]["parsing"] = "failed"
            
            # 구조 분석 상태
            if "[PHASE 3] 구조 분석 완료:" in line or "[STEP 4] 구조 분석 완료:" in line:
                book_id = get_book_id_from_line(line)
                if book_id:
                    book = get_book_by_id(book_id)
                    if book:
                        book["steps"]["structure"] = "success"
            elif "[PHASE 3] 이미 구조 분석됨:" in line or "[STEP 4] 이미 구조 분석됨:" in line:
                book_id = get_book_id_from_line(line)
                if book_id:
                    book = get_book_by_id(book_id)
                    if book:
                        book["steps"]["structure"] = "skipped"
            elif "[PHASE 3] 구조 후보 생성 완료" in line or "[STEP 4] 구조 후보 생성 완료 (자동 적용 안 함)" in line:
                book_id = get_book_id_from_line(line)
                if book_id:
                    book = get_book_by_id(book_id)
                    if book:
                        book["steps"]["structure"] = "skipped"
            elif "[PHASE 3] 구조 분석 실패:" in line or "[ERROR]" in line and "구조" in line:
                book_id = get_book_id_from_line(line)
                if book_id:
                    book = get_book_by_id(book_id)
                    if book:
                        book["steps"]["structure"] = "failed"
            
            # 텍스트 파일 상태
            if "[PHASE 4] 텍스트 정리 완료:" in line or "[STEP 5] 텍스트 정리 완료:" in line:
                book_id = get_book_id_from_line(line)
                if book_id:
                    book = get_book_by_id(book_id)
                    if book:
                        book["steps"]["text_file"] = "success"
                        # 파일 경로 추출
                        match = re.search(r'파일: (.+)', line)
                        if match:
                            book["output_files"]["text_file"] = match.group(1).strip()
            elif "[PHASE 4] 이미 텍스트 파일 생성됨:" in line or "[STEP 5] 텍스트 정리 스킵:" in line:
                book_id = get_book_id_from_line(line)
                if book_id:
                    book = get_book_by_id(book_id)
                    if book:
                        book["steps"]["text_file"] = "skipped"
            elif "[PHASE 4] 텍스트 정리 실패:" in line or "[ERROR]" in line and "텍스트" in line:
                book_id = get_book_id_from_line(line)
                if book_id:
                    book = get_book_by_id(book_id)
                    if book:
                        book["steps"]["text_file"] = "failed"
            
            # 파일 경로 추출
            if "[FILE] 캐시 파일:" in line:
                book_id = get_book_id_from_line(line)
                if book_id:
                    book = get_book_by_id(book_id)
                    if book:
                        match = re.search(r'캐시 파일: (.+)', line)
                        if match:
                            book["output_files"]["cache_file"] = match.group(1).strip()
            
            if "[FILE] 구조 파일:" in line:
                book_id = get_book_id_from_line(line)
                if book_id:
                    book = get_book_by_id(book_id)
                    if book:
                        match = re.search(r'구조 파일: (.+)', line)
                        if match:
                            book["output_files"]["structure_file"] = match.group(1).strip()
    
    logger.info(f"[INFO] 로그 파일에서 {len(books_data)}개 도서 정보 추출")
    return books_data


def verify_file_exists(file_path: Optional[str]) -> bool:
    """
    파일 존재 여부 확인
    
    Args:
        file_path: 파일 경로
        
    Returns:
        파일이 존재하면 True
    """
    if not file_path:
        return False
    
    file = Path(file_path)
    return file.exists() and file.is_file()


def verify_output_files(books_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    실제 출력 파일 존재 여부 확인
    
    Args:
        books_data: 로그에서 추출한 도서 데이터
        
    Returns:
        검증 결과가 추가된 도서 데이터
    """
    logger.info("[INFO] 출력 파일 존재 여부 확인 중...")
    
    for title, book_data in books_data.items():
        # 캐시 파일 확인
        cache_file = book_data["output_files"].get("cache_file")
        if cache_file:
            book_data["output_files"]["cache_file_exists"] = verify_file_exists(cache_file)
        else:
            book_data["output_files"]["cache_file_exists"] = False
        
        # 구조 파일 확인
        structure_file = book_data["output_files"].get("structure_file")
        if structure_file:
            book_data["output_files"]["structure_file_exists"] = verify_file_exists(structure_file)
        else:
            # 로그에 없어도 디렉토리에서 찾기
            book_id = book_data.get("book_id")
            if book_id:
                structure_dir = settings.output_dir / "structure"
                pattern = f"*_{book_id}_structure.json"
                for found_file in structure_dir.glob(pattern):
                    book_data["output_files"]["structure_file"] = str(found_file)
                    book_data["output_files"]["structure_file_exists"] = True
                    break
                else:
                    book_data["output_files"]["structure_file_exists"] = False
            else:
                book_data["output_files"]["structure_file_exists"] = False
        
        # 텍스트 파일 확인
        text_file = book_data["output_files"].get("text_file")
        if text_file:
            book_data["output_files"]["text_file_exists"] = verify_file_exists(text_file)
        else:
            # 로그에 없어도 디렉토리에서 찾기
            book_id = book_data.get("book_id")
            if book_id:
                text_dir = settings.output_dir / "text"
                pattern = f"*_{book_id}_text.json"
                for found_file in text_dir.glob(pattern):
                    book_data["output_files"]["text_file"] = str(found_file)
                    book_data["output_files"]["text_file_exists"] = True
                    break
                else:
                    book_data["output_files"]["text_file_exists"] = False
            else:
                book_data["output_files"]["text_file_exists"] = False
    
    return books_data


def verify_db_records(books_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    DB 레코드 확인
    
    Args:
        books_data: 도서 데이터
        
    Returns:
        DB 검증 결과가 추가된 도서 데이터
    """
    logger.info("[INFO] DB 레코드 확인 중...")
    
    db = SessionLocal()
    try:
        for title, book_data in books_data.items():
            book_id = book_data.get("book_id")
            if not book_id:
                book_data["db_record"] = None
                book_data["db_status"] = None
                continue
            
            book = db.query(Book).filter(Book.id == book_id).first()
            if book:
                book_data["db_record"] = {
                    "id": book.id,
                    "title": book.title,
                    "status": book.status.value if book.status else None,
                    "page_count": book.page_count,
                    "category": book.category,
                }
                book_data["db_status"] = book.status.value if book.status else None
            else:
                book_data["db_record"] = None
                book_data["db_status"] = None
    finally:
        db.close()
    
    return books_data


def generate_verification_report(
    books_data: Dict[str, Any],
    log_file: Path,
    output_file: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    검증 리포트 생성
    
    Args:
        books_data: 검증된 도서 데이터
        log_file: 로그 파일 경로
        output_file: 출력 리포트 파일 경로 (선택)
        
    Returns:
        리포트 딕셔너리
    """
    logger.info("[INFO] 검증 리포트 생성 중...")
    
    # 통계 집계
    stats = {
        "total_books": len(books_data),
        "success": 0,
        "failed": 0,
        "unknown": 0,
        "steps": {
            "pdf_found": 0,
            "book_created": 0,
            "parsing_success": 0,
            "parsing_failed": 0,
            "parsing_skipped": 0,
            "structure_success": 0,
            "structure_failed": 0,
            "structure_skipped": 0,
            "text_file_success": 0,
            "text_file_failed": 0,
            "text_file_skipped": 0,
        },
        "files": {
            "cache_file_exists": 0,
            "structure_file_exists": 0,
            "text_file_exists": 0,
        },
    }
    
    issues = []
    
    for title, book_data in books_data.items():
        # 상태 통계
        status = book_data.get("status", "unknown")
        if status == "success":
            stats["success"] += 1
        elif status == "failed":
            stats["failed"] += 1
        else:
            stats["unknown"] += 1
        
        # 단계별 통계
        steps = book_data.get("steps", {})
        if steps.get("pdf_found"):
            stats["steps"]["pdf_found"] += 1
        if steps.get("book_created"):
            stats["steps"]["book_created"] += 1
        
        parsing = steps.get("parsing", "unknown")
        if parsing == "success":
            stats["steps"]["parsing_success"] += 1
        elif parsing == "failed":
            stats["steps"]["parsing_failed"] += 1
        else:
            stats["steps"]["parsing_skipped"] += 1
        
        structure = steps.get("structure", "unknown")
        if structure == "success":
            stats["steps"]["structure_success"] += 1
        elif structure == "failed":
            stats["steps"]["structure_failed"] += 1
        else:
            stats["steps"]["structure_skipped"] += 1
        
        text_file = steps.get("text_file", "unknown")
        if text_file == "success":
            stats["steps"]["text_file_success"] += 1
        elif text_file == "failed":
            stats["steps"]["text_file_failed"] += 1
        else:
            stats["steps"]["text_file_skipped"] += 1
        
        # 파일 존재 통계
        output_files = book_data.get("output_files", {})
        if output_files.get("cache_file_exists"):
            stats["files"]["cache_file_exists"] += 1
        if output_files.get("structure_file_exists"):
            stats["files"]["structure_file_exists"] += 1
        if output_files.get("text_file_exists"):
            stats["files"]["text_file_exists"] += 1
        
        # 이슈 체크
        book_issues = []
        if not steps.get("pdf_found"):
            book_issues.append("PDF 파일 없음")
        if parsing == "failed":
            book_issues.append("파싱 실패")
        if structure == "failed":
            book_issues.append("구조 분석 실패")
        if text_file == "failed":
            book_issues.append("텍스트 파일 생성 실패")
        if structure == "success" and not output_files.get("structure_file_exists"):
            book_issues.append("구조 파일 없음 (로그에는 성공)")
        if text_file == "success" and not output_files.get("text_file_exists"):
            book_issues.append("텍스트 파일 없음 (로그에는 성공)")
        
        if book_issues:
            issues.append({
                "title": title,
                "book_id": book_data.get("book_id"),
                "issues": book_issues,
                "errors": book_data.get("errors", []),
            })
    
    report = {
        "log_file": str(log_file),
        "verification_time": datetime.now().isoformat(),
        "statistics": stats,
        "issues": issues,
        "books": books_data,
    }
    
    # 리포트 파일 저장
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"[INFO] 검증 리포트 저장: {output_file}")
    
    return report


def print_summary(report: Dict[str, Any]):
    """콘솔에 요약 리포트 출력"""
    stats = report["statistics"]
    issues = report["issues"]
    
    print("\n" + "=" * 80)
    print("대량 도서 처리 검증 리포트")
    print("=" * 80)
    
    print(f"\n[전체 통계]")
    print(f"  전체 도서: {stats['total_books']}개")
    print(f"  성공: {stats['success']}개")
    print(f"  실패: {stats['failed']}개")
    print(f"  상태 불명: {stats['unknown']}개")
    
    print(f"\n[단계별 통계]")
    print(f"  PDF 파일 찾기: {stats['steps']['pdf_found']}개")
    print(f"  Book 레코드 생성: {stats['steps']['book_created']}개")
    print(f"  파싱 - 성공: {stats['steps']['parsing_success']}개, 실패: {stats['steps']['parsing_failed']}개, 스킵: {stats['steps']['parsing_skipped']}개")
    print(f"  구조 분석 - 성공: {stats['steps']['structure_success']}개, 실패: {stats['steps']['structure_failed']}개, 스킵: {stats['steps']['structure_skipped']}개")
    print(f"  텍스트 파일 - 성공: {stats['steps']['text_file_success']}개, 실패: {stats['steps']['text_file_failed']}개, 스킵: {stats['steps']['text_file_skipped']}개")
    
    print(f"\n[파일 존재 여부]")
    print(f"  캐시 파일: {stats['files']['cache_file_exists']}개")
    print(f"  구조 파일: {stats['files']['structure_file_exists']}개")
    print(f"  텍스트 파일: {stats['files']['text_file_exists']}개")
    
    if issues:
        print(f"\n[이슈] ({len(issues)}개 도서)")
        for issue in issues[:10]:  # 최대 10개만 출력
            print(f"  - {issue['title']} (ID: {issue['book_id']})")
            for issue_item in issue['issues']:
                print(f"    * {issue_item}")
        if len(issues) > 10:
            print(f"  ... 외 {len(issues) - 10}개 도서에 이슈 있음")
    
    print(f"\n[로그 파일]")
    print(f"  {report['log_file']}")
    print(f"\n[검증 리포트 파일]")
    if 'report_file' in report:
        print(f"  {report['report_file']}")
    
    print("=" * 80 + "\n")


def verify_batch_processing(
    log_file: Path,
    output_report_file: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    대량 도서 처리 결과 검증
    
    Args:
        log_file: 로그 파일 경로
        output_report_file: 출력 리포트 파일 경로 (선택)
        
    Returns:
        검증 리포트 딕셔너리
    """
    logger.info("=" * 80)
    logger.info("[VERIFY] 대량 도서 처리 결과 검증 시작")
    logger.info("=" * 80)
    
    # 1. 로그 파일 파싱
    books_data = parse_log_file(log_file)
    
    if not books_data:
        logger.error("[ERROR] 로그 파일에서 도서 정보를 추출할 수 없습니다")
        return {}
    
    # 2. 출력 파일 확인
    books_data = verify_output_files(books_data)
    
    # 3. DB 레코드 확인
    books_data = verify_db_records(books_data)
    
    # 4. 검증 리포트 생성
    report = generate_verification_report(
        books_data,
        log_file,
        output_report_file,
    )
    
    if output_report_file:
        report["report_file"] = str(output_report_file)
    
    logger.info("[VERIFY] 검증 완료")
    
    return report


def find_latest_log_file() -> Optional[Path]:
    """
    가장 최근 로그 파일 찾기
    
    Returns:
        가장 최근 로그 파일 경로 또는 None
    """
    log_dir = project_root / "data" / "logs" / "batch_processing"
    if not log_dir.exists():
        return None
    
    log_files = list(log_dir.glob("batch_process_*.log"))
    if not log_files:
        return None
    
    # 수정 시간 기준으로 정렬
    log_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return log_files[0]


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="대량 도서 처리 결과 검증")
    parser.add_argument(
        "log_file",
        type=str,
        nargs="?",
        default=None,
        help="로그 파일 경로 (지정하지 않으면 가장 최근 로그 파일 사용)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="출력 리포트 파일 경로 (JSON 형식)",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="가장 최근 로그 파일 사용",
    )
    
    args = parser.parse_args()
    
    # 로그 파일 경로 결정
    if args.latest or args.log_file is None:
        log_file = find_latest_log_file()
        if not log_file:
            print("[ERROR] 로그 파일을 찾을 수 없습니다.")
            print(f"[INFO] 로그 디렉토리: {project_root / 'data' / 'logs' / 'batch_processing'}")
            sys.exit(1)
        print(f"[INFO] 가장 최근 로그 파일 사용: {log_file}")
    else:
        log_file = Path(args.log_file)
        if not log_file.is_absolute():
            log_file = project_root / log_file
    
    if not log_file.exists():
        print(f"[ERROR] 로그 파일이 존재하지 않습니다: {log_file}")
        sys.exit(1)
    
    # 출력 리포트 파일 경로
    output_report_file = None
    if args.output:
        output_report_file = Path(args.output)
        if not output_report_file.is_absolute():
            output_report_file = project_root / output_report_file
    else:
        # 기본 리포트 파일 경로 (로그 파일과 같은 디렉토리)
        report_dir = log_file.parent
        report_name = log_file.stem.replace("batch_process", "verification_report") + ".json"
        output_report_file = report_dir / report_name
    
    # 검증 실행
    report = verify_batch_processing(log_file, output_report_file)
    
    # 요약 출력
    if report:
        print_summary(report)
    else:
        print("[ERROR] 검증 리포트를 생성할 수 없습니다.")
        sys.exit(1)

