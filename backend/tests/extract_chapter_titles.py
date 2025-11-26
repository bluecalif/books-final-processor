"""
챕터 제목 추출 스크립트

파싱된 PDF 데이터에서 각 챕터 시작 페이지의 제목을 추출합니다.
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.parsers.pdf_parser import PDFParser
from backend.config.settings import settings

# Ground Truth에서 챕터 시작 페이지 가져오기
CHAPTER_START_PAGES = [36, 66, 97, 121, 167, 195, 224]

# PDF 파일 경로
PDF_PATH = Path(__file__).parent.parent.parent / "data" / "input" / "1등의 통찰.pdf"


def extract_chapter_title(parsed_data: dict, page_number: int) -> str:
    """
    특정 페이지에서 챕터 제목 추출
    
    Args:
        parsed_data: PDFParser.parse_pdf() 결과
        page_number: 챕터 시작 페이지 번호
    
    Returns:
        챕터 제목 (추출 실패 시 빈 문자열)
    """
    pages = parsed_data.get("pages", [])
    
    # 해당 페이지 찾기
    target_page = None
    for page in pages:
        if page.get("page_number") == page_number:
            target_page = page
            break
    
    if not target_page:
        return f"[페이지 {page_number}를 찾을 수 없음]"
    
    # 방법 1: elements에서 추출
    elements = target_page.get("elements", [])
    if elements:
        # 페이지 상단 요소 찾기 (y0가 가장 작은 요소)
        valid_elements = [e for e in elements if e.get("bbox", {}).get("y0") is not None]
        if valid_elements:
            top_elements = sorted(
                valid_elements,
                key=lambda e: e.get("bbox", {}).get("y0", 1.0)
            )
            
            # 상위 5개 요소 확인
            candidates = []
            for elem in top_elements[:5]:
                text = (elem.get("text") or "").strip()
                if text:
                    # 챕터 패턴 확인
                    if any([
                        "제" in text and "장" in text,
                        "CHAPTER" in text.upper(),
                        text[0].isdigit() and "." in text[:5],
                    ]):
                        candidates.append(text)
            
            if candidates:
                # 가장 긴 후보를 선택
                return max(candidates, key=len)
            
            # 패턴이 없으면 상단 첫 번째 요소의 텍스트 반환
            if top_elements:
                text = (top_elements[0].get("text") or "").strip()
                if text:
                    # 처음 100자만 반환
                    return text[:100] if len(text) > 100 else text
    
    # 방법 2: raw_text에서 추출 (elements가 없는 경우)
    raw_text = target_page.get("raw_text", "")
    if raw_text:
        # 첫 200자 확인
        first_lines = raw_text[:200].split("\n")
        for line in first_lines[:5]:  # 처음 5줄만 확인
            line = line.strip()
            if line:
                # 챕터 패턴 확인
                if any([
                    "제" in line and "장" in line,
                    "CHAPTER" in line.upper(),
                    line[0].isdigit() and "." in line[:5],
                ]):
                    return line
                # 패턴이 없으면 첫 번째 비어있지 않은 줄 반환
                if len(line) > 5:  # 너무 짧은 줄은 제외
                    return line[:100] if len(line) > 100 else line
    
    return f"[페이지 {page_number}에서 제목을 추출할 수 없음]"


def main():
    """메인 함수"""
    print("=" * 80)
    print("챕터 제목 추출 시작")
    print("=" * 80)
    print(f"PDF 파일: {PDF_PATH}")
    print(f"챕터 시작 페이지: {CHAPTER_START_PAGES}")
    print()
    
    # PDF 파싱 (캐시 사용)
    print("PDF 파싱 중...")
    pdf_parser = PDFParser(api_key=settings.upstage_api_key)
    parsed_data = pdf_parser.parse_pdf(str(PDF_PATH), use_cache=True)
    
    print(f"파싱 완료: 총 {parsed_data.get('total_pages', 0)}페이지")
    print()
    
    # 각 챕터 제목 추출
    print("챕터 제목 추출 중...")
    print("-" * 80)
    
    chapter_titles = []
    for idx, start_page in enumerate(CHAPTER_START_PAGES, 1):
        title = extract_chapter_title(parsed_data, start_page)
        chapter_titles.append({
            "number": idx,
            "start_page": start_page,
            "title": title,
        })
        print(f"제{idx}장 (페이지 {start_page}): {title}")
    
    print("-" * 80)
    print()
    
    # 결과 출력
    print("=" * 80)
    print("추출 결과 (Ground Truth 파일 업데이트용)")
    print("=" * 80)
    print()
    print("chapters = [")
    for ch in chapter_titles:
        print(f'    {{')
        print(f'        "number": {ch["number"]},')
        print(f'        "title": "{ch["title"]}",')
        print(f'        "start_page": {ch["start_page"]},')
        print(f'        "end_page": ...,  # Ground Truth에서 확인')
        print(f'    }},')
    print("]")
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()

