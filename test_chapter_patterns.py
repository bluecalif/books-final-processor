"""
챕터 패턴 매칭 테스트 스크립트

실패한 도서들의 Footer 텍스트가 현재 패턴으로 매칭되는지 확인합니다.
"""
import re

# 현재 사용 중인 챕터 패턴 (ContentBoundaryDetector와 ChapterDetector 동일)
current_patterns = [
    re.compile(r"제\s*\d+\s*[장강부]"),  # 제1장, 제1강, 제1부
    re.compile(r"CHAPTER\s*\d+", re.IGNORECASE),  # Chapter 1, Chapter1
    re.compile(r"Part\s*\d+", re.IGNORECASE),  # Part 1, Part1
    re.compile(r"^\d+\s*[장강부]"),  # 1장, 1강 (문자열 시작)
    re.compile(r"^\d+\.\s*[가-힣]"),  # 1. 제목, 1.제목 (문자열 시작)
]

# ChapterDetector용 패턴 (그룹 포함)
chapter_patterns_with_group = [
    re.compile(r"제\s*(\d+)\s*[장강부]"),  # 제1장, 제1강, 제1부
    re.compile(r"CHAPTER\s*(\d+)", re.IGNORECASE),  # Chapter 1, Chapter1
    re.compile(r"Part\s*(\d+)", re.IGNORECASE),  # Part 1, Part1
    re.compile(r"^(\d+)\s*[장강부]"),  # 1장, 1강 (문자열 시작)
    re.compile(r"^(\d+)\.\s*[가-힣]"),  # 1. 제목, 1.제목 (문자열 시작)
]

# 실패한 도서들의 Footer 텍스트
test_texts = [
    {
        "book": "30개 도시로 읽는 세계사",
        "text": "03 아테네 _ 민주정을 꽃피운 문화와 학문의 도시",
        "expected_chapter": 3
    },
    {
        "book": "10년후 이곳은 제2의 강남",
        "text": "1장 위기인가 기회인가, 대한민국 부동산의 미래",
        "expected_chapter": 1
    },
    {
        "book": "10년후 이곳은 제2의 판교",
        "text": "1장 위기인가 기회인가, 대한민국 부동산의 미래",  # 동일 형식
        "expected_chapter": 1
    },
    {
        "book": "3D프린터의 모든것",
        "text": "1_3D 프린터가 만들 세상의 모든 것",
        "expected_chapter": 1
    },
    {
        "book": "99를 위한 경제",
        "text": "1장 우리가 직면한 여섯 가지 위기",
        "expected_chapter": 1
    },
    {
        "book": "12가지 인생의 법칙",
        "text": "법칙 2 당신 자신을 도와줘야 할 사림처럼 대하라",
        "expected_chapter": 2
    },
]

def test_pattern_matching():
    """패턴 매칭 테스트"""
    print("=" * 80)
    print("챕터 패턴 매칭 테스트")
    print("=" * 80)
    print()
    
    for test_case in test_texts:
        book = test_case["book"]
        text = test_case["text"]
        expected = test_case["expected_chapter"]
        
        print(f"[도서] {book}")
        print(f"[텍스트] {text}")
        print(f"[예상 챕터 번호] {expected}")
        print()
        
        # 1. ContentBoundaryDetector 패턴 테스트 (매칭 여부만)
        print("1. ContentBoundaryDetector 패턴 매칭 (본문 시작 탐지용):")
        matched = False
        for i, pattern in enumerate(current_patterns):
            match = pattern.search(text)
            if match:
                matched = True
                print(f"   ✓ 패턴 {i+1} 매칭: {pattern.pattern}")
                print(f"     매칭 결과: {match.group()}")
            else:
                print(f"   ✗ 패턴 {i+1} 미매칭: {pattern.pattern}")
        
        if not matched:
            print("   ❌ 모든 패턴 미매칭 → chapter_marker로 분류되지 않음")
        print()
        
        # 2. ChapterDetector 패턴 테스트 (숫자 추출)
        print("2. ChapterDetector 패턴 매칭 (챕터 번호 추출용):")
        extracted_number = None
        matched_pattern = None
        for i, pattern in enumerate(chapter_patterns_with_group):
            match = pattern.search(text)
            if match:
                groups = match.groups()
                if groups:
                    try:
                        number = int(groups[0])
                        extracted_number = number
                        matched_pattern = pattern.pattern
                        print(f"   ✓ 패턴 {i+1} 매칭: {pattern.pattern}")
                        print(f"     추출된 번호: {number}")
                        print(f"     매칭 결과: {match.group()}")
                        break
                    except (ValueError, IndexError):
                        continue
        
        if extracted_number is None:
            print("   ❌ 모든 패턴 미매칭 → 챕터 번호 추출 실패")
        elif extracted_number != expected:
            print(f"   ⚠️ 추출된 번호({extracted_number})와 예상 번호({expected}) 불일치")
        else:
            print(f"   ✓ 추출된 번호({extracted_number})와 예상 번호({expected}) 일치")
        print()
        
        # 3. 문제점 분석
        print("3. 문제점 분석:")
        issues = []
        if not matched:
            issues.append("본문 시작 페이지 탐지 실패 가능성 (chapter_marker로 분류되지 않음)")
        if extracted_number is None:
            issues.append("챕터 번호 추출 실패 (챕터 경계 탐지 불가)")
        elif extracted_number != expected:
            issues.append(f"챕터 번호 오추출 (추출: {extracted_number}, 예상: {expected})")
        
        if issues:
            for issue in issues:
                print(f"   - {issue}")
        else:
            print("   ✓ 패턴 매칭 정상")
        print()
        print("-" * 80)
        print()

if __name__ == "__main__":
    test_pattern_matching()

