"""
처리 문제 진단 스크립트

3가지 문제 유형별로 문제가 있는 책 목록을 추출합니다:
1. 파싱 불완전한 도서 (페이지 완전성 검증 포함)
2. 파싱 완료했지만 구조 분석 실패
3. 구조 분석 완료했지만 텍스트 생성 실패
"""
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.api.database import SessionLocal, init_db
from backend.api.models.book import Book, BookStatus, Page
from backend.parsers.cache_manager import CacheManager
from backend.config.settings import settings

# 디렉토리 설정
TEXT_DIR = project_root / "data" / "output" / "text"
STRUCTURE_DIR = project_root / "data" / "output" / "structure"
CACHE_DIR = project_root / "data" / "cache" / "upstage"


def get_cache_file_path(book: Book) -> Optional[Path]:
    """책의 캐시 파일 경로 찾기"""
    if not book.source_file_path:
        return None
    
    pdf_path = Path(book.source_file_path)
    if not pdf_path.exists():
        return None
    
    try:
        cache_manager = CacheManager()
        cache_key = cache_manager.get_file_hash(str(pdf_path))
        cache_file = cache_manager.cache_dir / f"{cache_key}.json"
        return cache_file if cache_file.exists() else None
    except Exception:
        return None


def verify_parsing_completeness(book: Book, db: Session) -> Dict[str, Any]:
    """
    파싱 완전성 검증
    
    Returns:
        {
            "is_complete": bool,
            "issues": List[str],
            "cache_pages": int,  # 캐시 파일의 페이지 수
            "db_pages": int,     # Pages 테이블의 레코드 수
            "expected_pages": int,  # DB의 page_count
            "missing_pages": List[int],  # 누락된 페이지 번호
            "empty_pages": List[int],   # raw_text가 비어있는 페이지 번호
        }
    """
    result = {
        "is_complete": True,
        "issues": [],
        "cache_pages": 0,
        "db_pages": 0,
        "expected_pages": book.page_count or 0,
        "missing_pages": [],
        "empty_pages": [],
    }
    
    # 1. 캐시 파일에서 페이지 수 확인
    cache_file = get_cache_file_path(book)
    if cache_file:
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # elements를 페이지별로 그룹화
            elements = cache_data.get("elements", [])
            pages_in_cache = set()
            for elem in elements:
                page_num = elem.get("page", 0)
                if page_num > 0:
                    pages_in_cache.add(page_num)
            
            result["cache_pages"] = len(pages_in_cache)
            
            # 예상 페이지 수와 비교
            if result["expected_pages"] > 0:
                if result["cache_pages"] < result["expected_pages"]:
                    result["is_complete"] = False
                    result["issues"].append(
                        f"캐시 파일의 페이지 수({result['cache_pages']})가 예상 페이지 수({result['expected_pages']})보다 적음"
                    )
        except Exception as e:
            result["is_complete"] = False
            result["issues"].append(f"캐시 파일 읽기 실패: {e}")
    else:
        result["is_complete"] = False
        result["issues"].append("캐시 파일 없음")
    
    # 2. Pages 테이블 레코드 수 확인
    db_pages = db.query(Page).filter(Page.book_id == book.id).all()
    result["db_pages"] = len(db_pages)
    
    if result["expected_pages"] > 0:
        if result["db_pages"] < result["expected_pages"]:
            result["is_complete"] = False
            result["issues"].append(
                f"Pages 테이블 레코드 수({result['db_pages']})가 예상 페이지 수({result['expected_pages']})보다 적음"
            )
    
    # 3. 페이지 번호 연속성 확인
    if db_pages:
        page_numbers = sorted([p.page_number for p in db_pages])
        expected_numbers = list(range(1, result["expected_pages"] + 1)) if result["expected_pages"] > 0 else []
        
        if expected_numbers:
            missing = set(expected_numbers) - set(page_numbers)
            if missing:
                result["is_complete"] = False
                result["missing_pages"] = sorted(missing)
                result["issues"].append(
                    f"누락된 페이지 번호: {sorted(missing)[:10]}{'...' if len(missing) > 10 else ''}"
                )
    
    # 4. 각 페이지의 raw_text 확인
    empty_pages = []
    for page in db_pages:
        if not page.raw_text or len(page.raw_text.strip()) == 0:
            empty_pages.append(page.page_number)
    
    if empty_pages:
        result["is_complete"] = False
        result["empty_pages"] = empty_pages
        result["issues"].append(
            f"raw_text가 비어있는 페이지: {empty_pages[:10]}{'...' if len(empty_pages) > 10 else ''}"
        )
    
    return result


def find_text_file(book: Book) -> Optional[Path]:
    """책의 텍스트 파일 찾기 (해시 기반, 6글자 해시 사용)"""
    if not book.source_file_path:
        return None
    
    pdf_path = Path(book.source_file_path)
    if not pdf_path.exists():
        return None
    
    try:
        cache_manager = CacheManager()
        full_hash = cache_manager.get_file_hash(str(pdf_path))
        hash_6 = full_hash[:6]  # 6글자 해시만 사용
        
        # 제목 정규화 (text_organizer와 동일한 로직)
        safe_title = (book.title or "").replace(" ", "_").replace("/", "_")
        # 특수문자 제거
        safe_title = "".join(c for c in safe_title if c.isalnum() or c in ("_", "-"))[:10]
        
        # 텍스트 파일명 패턴: {hash_6}_{safe_title}_text.json
        # 여러 패턴으로 시도
        patterns = [
            f"{hash_6}_{safe_title}_text.json",  # 해시 + 제목
            f"{hash_6}_*_text.json",  # 해시만 (와일드카드)
        ]
        
        for pattern in patterns:
            if "*" in pattern:
                # 와일드카드 패턴
                matches = list(TEXT_DIR.glob(pattern))
                if matches:
                    return matches[0]
            else:
                # 정확한 패턴
                text_file = TEXT_DIR / pattern
                if text_file.exists():
                    return text_file
        
        # 해시만으로도 시도 (6글자)
        for text_file in TEXT_DIR.glob(f"{hash_6}_*_text.json"):
            return text_file
        
        # 전체 해시로도 시도 (하위 호환성)
        for text_file in TEXT_DIR.glob(f"{full_hash}_*_text.json"):
            return text_file
        
        return None
    except Exception as e:
        print(f"[DEBUG] find_text_file error for {book.id}: {e}")
        return None


def find_structure_file(book: Book) -> Optional[Path]:
    """책의 구조 파일 찾기 (해시 기반, 6글자 해시 사용)"""
    if not book.source_file_path:
        return None
    
    pdf_path = Path(book.source_file_path)
    if not pdf_path.exists():
        return None
    
    try:
        cache_manager = CacheManager()
        full_hash = cache_manager.get_file_hash(str(pdf_path))
        hash_6 = full_hash[:6]  # 6글자 해시만 사용
        
        # 제목 정규화 (text_organizer와 동일한 로직)
        safe_title = (book.title or "").replace(" ", "_").replace("/", "_")
        # 특수문자 제거
        safe_title = "".join(c for c in safe_title if c.isalnum() or c in ("_", "-"))[:10]
        
        # 구조 파일명 패턴: {hash_6}_{safe_title}_structure.json
        patterns = [
            f"{hash_6}_{safe_title}_structure.json",  # 해시 + 제목
            f"{hash_6}_*_structure.json",  # 해시만 (와일드카드)
        ]
        
        for pattern in patterns:
            if "*" in pattern:
                # 와일드카드 패턴
                matches = list(STRUCTURE_DIR.glob(pattern))
                if matches:
                    return matches[0]
            else:
                # 정확한 패턴
                structure_file = STRUCTURE_DIR / pattern
                if structure_file.exists():
                    return structure_file
        
        # 해시만으로도 시도 (6글자)
        for structure_file in STRUCTURE_DIR.glob(f"{hash_6}_*_structure.json"):
            return structure_file
        
        # 전체 해시로도 시도 (하위 호환성)
        for structure_file in STRUCTURE_DIR.glob(f"{full_hash}_*_structure.json"):
            return structure_file
        
        return None
    except Exception as e:
        print(f"[DEBUG] find_structure_file error for {book.id}: {e}")
        return None


def diagnose_all_books() -> Dict[str, Any]:
    """모든 책의 처리 상태 진단"""
    db = SessionLocal()
    
    try:
        all_books = db.query(Book).order_by(Book.id).all()
        
        # 문제 유형별로 분류
        parsing_issues = []      # 파싱 불완전
        structure_issues = []    # 구조 분석 실패
        text_issues = []         # 텍스트 생성 실패
        
        for book in all_books:
            book_info = {
                "id": book.id,
                "title": book.title,
                "status": book.status.value,
                "page_count": book.page_count,
                "source_file_path": book.source_file_path,
            }
            
            # 1. 파싱 불완전 확인
            if book.status == BookStatus.UPLOADED:
                parsing_issues.append({
                    **book_info,
                    "issue_type": "파싱 시작 안 됨",
                    "issue_detail": "Status가 UPLOADED (파싱이 시작되지 않음)",
                })
            elif book.status == BookStatus.ERROR_PARSING:
                parsing_issues.append({
                    **book_info,
                    "issue_type": "파싱 실패",
                    "issue_detail": "Status가 ERROR_PARSING (파싱 중 에러 발생)",
                })
            elif book.status == BookStatus.PARSED:
                # page_count 확인
                if not book.page_count or book.page_count == 0:
                    parsing_issues.append({
                        **book_info,
                        "issue_type": "page_count 비정상",
                        "issue_detail": f"Status는 PARSED이지만 page_count가 {book.page_count}",
                    })
                else:
                    # 모든 PARSED 상태 책에 대해 페이지 파싱 완전성 검증
                    completeness = verify_parsing_completeness(book, db)
                    if not completeness["is_complete"]:
                        parsing_issues.append({
                            **book_info,
                            "issue_type": "페이지 파싱 불완전",
                            "issue_detail": "; ".join(completeness["issues"]),
                            "completeness": completeness,
                        })
            
            # 2. 구조 분석 실패 확인
            if book.status == BookStatus.PARSED:
                structure_file = find_structure_file(book)
                if not structure_file:
                    structure_issues.append({
                        **book_info,
                        "issue_type": "구조 분석 안 됨",
                        "issue_detail": "Status가 PARSED이지만 구조 파일이 없음",
                    })
            elif book.status == BookStatus.ERROR_STRUCTURING:
                structure_issues.append({
                    **book_info,
                    "issue_type": "구조 분석 실패",
                    "issue_detail": "Status가 ERROR_STRUCTURING (구조 분석 중 에러 발생)",
                })
            
            # 3. 텍스트 생성 실패 확인
            if book.status == BookStatus.STRUCTURED:
                text_file = find_text_file(book)
                if not text_file:
                    text_issues.append({
                        **book_info,
                        "issue_type": "텍스트 생성 안 됨",
                        "issue_detail": "Status가 STRUCTURED이지만 텍스트 파일이 없음",
                    })
        
        return {
            "parsing_issues": parsing_issues,
            "structure_issues": structure_issues,
            "text_issues": text_issues,
            "total_books": len(all_books),
        }
    
    finally:
        db.close()


def print_diagnosis_report(report: Dict[str, Any]):
    """진단 리포트 출력"""
    print("=" * 80)
    print("처리 문제 진단 리포트")
    print("=" * 80)
    
    print(f"\n[전체 통계]")
    print(f"  전체 책: {report['total_books']}권")
    print(f"  파싱 문제: {len(report['parsing_issues'])}권")
    print(f"  구조 분석 문제: {len(report['structure_issues'])}권")
    print(f"  텍스트 생성 문제: {len(report['text_issues'])}권")
    
    # 파싱 문제 상세
    if report['parsing_issues']:
        print(f"\n[1. 파싱 불완전한 도서] ({len(report['parsing_issues'])}권)")
        for issue in report['parsing_issues']:
            print(f"\n  ID {issue['id']}: {issue['title']}")
            print(f"    Status: {issue['status']}")
            print(f"    page_count: {issue['page_count']}")
            print(f"    문제 유형: {issue['issue_type']}")
            print(f"    상세: {issue['issue_detail']}")
            if 'completeness' in issue:
                comp = issue['completeness']
                print(f"    - 캐시 페이지 수: {comp['cache_pages']}")
                print(f"    - DB 페이지 수: {comp['db_pages']}")
                print(f"    - 예상 페이지 수: {comp['expected_pages']}")
                if comp['missing_pages']:
                    print(f"    - 누락된 페이지: {comp['missing_pages'][:10]}{'...' if len(comp['missing_pages']) > 10 else ''}")
                if comp['empty_pages']:
                    print(f"    - 빈 페이지: {comp['empty_pages'][:10]}{'...' if len(comp['empty_pages']) > 10 else ''}")
    
    # 구조 분석 문제 상세
    if report['structure_issues']:
        print(f"\n[2. 구조 분석 실패한 도서] ({len(report['structure_issues'])}권)")
        for issue in report['structure_issues']:
            print(f"\n  ID {issue['id']}: {issue['title']}")
            print(f"    Status: {issue['status']}")
            print(f"    문제 유형: {issue['issue_type']}")
            print(f"    상세: {issue['issue_detail']}")
    
    # 텍스트 생성 문제 상세
    if report['text_issues']:
        print(f"\n[3. 텍스트 생성 실패한 도서] ({len(report['text_issues'])}권)")
        for issue in report['text_issues']:
            print(f"\n  ID {issue['id']}: {issue['title']}")
            print(f"    Status: {issue['status']}")
            print(f"    문제 유형: {issue['issue_type']}")
            print(f"    상세: {issue['issue_detail']}")
    
    print("\n" + "=" * 80)


def save_diagnosis_report(report: Dict[str, Any], output_file: Path):
    """진단 리포트를 JSON 파일로 저장"""
    # JSON 직렬화 가능하도록 변환
    json_report = {
        "total_books": report["total_books"],
        "parsing_issues": [
            {
                "id": issue["id"],
                "title": issue["title"],
                "status": issue["status"],
                "page_count": issue["page_count"],
                "issue_type": issue["issue_type"],
                "issue_detail": issue["issue_detail"],
                "completeness": issue.get("completeness"),
            }
            for issue in report["parsing_issues"]
        ],
        "structure_issues": [
            {
                "id": issue["id"],
                "title": issue["title"],
                "status": issue["status"],
                "issue_type": issue["issue_type"],
                "issue_detail": issue["issue_detail"],
            }
            for issue in report["structure_issues"]
        ],
        "text_issues": [
            {
                "id": issue["id"],
                "title": issue["title"],
                "status": issue["status"],
                "issue_type": issue["issue_type"],
                "issue_detail": issue["issue_detail"],
            }
            for issue in report["text_issues"]
        ],
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(json_report, f, ensure_ascii=False, indent=2)
    
    print(f"\n[INFO] 진단 리포트 저장: {output_file}")


if __name__ == "__main__":
    init_db()
    
    print("진단 스크립트 실행 중...")
    report = diagnose_all_books()
    
    print_diagnosis_report(report)
    
    # 리포트 파일 저장
    output_file = project_root / "data" / "logs" / "batch_processing" / "diagnosis_report.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    save_diagnosis_report(report, output_file)
    
    print(f"\n[요약]")
    print(f"  전체: {report['total_books']}권")
    print(f"  파싱 문제: {len(report['parsing_issues'])}권")
    print(f"  구조 분석 문제: {len(report['structure_issues'])}권")
    print(f"  텍스트 생성 문제: {len(report['text_issues'])}권")
    print(f"  총 문제: {len(report['parsing_issues']) + len(report['structure_issues']) + len(report['text_issues'])}권")

