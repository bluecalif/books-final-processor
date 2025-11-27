# 구조 분석 로직 상세 설명 (단계별)

이 문서는 Footer 기반 구조 분석 모듈의 실제 구현을 단계별로 상세하게 설명합니다.

## 목차

1. [전체 파이프라인](#1-전체-파이프라인)
2. [Footer 요소 추출](#2-footer-요소-추출)
3. [Footer 요소 분류](#3-footer-요소-분류)
4. [본문 시작 페이지 탐지](#4-본문-시작-페이지-탐지)
5. [종문 시작 페이지 탐지](#5-종문-시작-페이지-탐지)
6. [챕터 번호 추출](#6-챕터-번호-추출)
7. [챕터 경계 계산](#7-챕터-경계-계산)

---

## 1. 전체 파이프라인

### 1.1 실행 순서

```
StructureBuilder.build_structure()
  ↓
1. ContentBoundaryDetector.detect_boundaries()
   - 본문 시작 페이지 탐지
   - 종문 시작 페이지 탐지
   - 서문/본문/종문 경계 확정
  ↓
2. ChapterDetector.detect_chapters()
   - 본문 영역의 홀수 페이지에서 챕터 번호 추출
   - 챕터 번호 연속성 검증
   - 챕터 경계 계산
   - 챕터 제목 추출
```

### 1.2 핵심 원칙

- **홀수 페이지 우선**: 모든 판단은 홀수 페이지(좌측)의 Footer를 기준으로 수행
- **Footer 기반**: 페이지 하단(y0 > 0.9) 또는 category='footer'인 요소만 사용
- **챕터 표시 판별자 우선**: Footer 요소 중 챕터 표시 판별자(`chapter_marker`)를 최우선으로 사용
- **페이지 번호 제외**: Footer의 페이지 번호는 챕터 탐지에서 제외

---

## 2. Footer 요소 추출

### 2.1 추출 조건

**메서드**: `_get_footer_elements(page: Dict) -> List[Dict]`

**조건 (OR 관계)**:
1. `category == 'footer'`인 요소
2. `y0 > 0.9`인 요소 (페이지 하단 10% 영역)

**정렬**:
- `y0` 기준 내림차순 정렬 (하단에 가까울수록 우선)

### 2.2 구현 코드

```python
def _get_footer_elements(self, page: Dict) -> List[Dict]:
    elements = page.get("elements", [])
    footer_elements = []
    
    for elem in elements:
        # 1. category='footer'인 요소
        if elem.get("category") == "footer":
            footer_elements.append(elem)
            continue
        
        # 2. y0 좌표가 큰 요소 (페이지 하단)
        bbox = elem.get("bbox", {})
        y0 = bbox.get("y0", 0.0)
        if y0 > 0.9:  # 페이지 하단 10% 영역
            footer_elements.append(elem)
    
    # y0 기준으로 정렬 (하단에 가까울수록 우선)
    footer_elements.sort(
        key=lambda e: e.get("bbox", {}).get("y0", 0.0), reverse=True
    )
    
    return footer_elements
```

### 2.3 식별자

- **y0 좌표**: 정규화된 좌표 (0.0 ~ 1.0), 0.9 이상이면 Footer 영역
- **category**: Upstage API에서 제공하는 요소 분류 ('footer', 'text', 'title' 등)

---

## 3. Footer 요소 분류

### 3.1 분류 목적

Footer 요소를 3가지로 분류하여 챕터 표시 판별자만 추출:
- `chapter_marker`: 챕터 표시 판별자 (예: "제1장", "Chapter 1")
- `page_number`: 페이지 번호 (예: "36", "37")
- `other`: 기타 (저자명, 출판사 등)

### 3.2 분류 로직

**메서드**: `_classify_footer_element(elem: Dict) -> str`

**우선순위**:
1. **챕터 패턴 확인** (최우선)
   - 정규식 패턴 매칭으로 챕터 표시 판별자 확인
   - 매칭되면 → `chapter_marker`
2. **위치 기반 판단**
   - `x0 < 0.05` (왼쪽 끝) + 페이지 번호 패턴 → `page_number`
3. **중앙 영역 판단**
   - `0.05 < x0 < 0.5` (중앙) + 챕터 키워드 포함 → `chapter_marker`
4. **기타**
   - 위 조건에 해당하지 않으면 → `other`

### 3.3 챕터 패턴 목록

**정규식 패턴** (공백 유무 모두 매칭):
1. `제\s*\d+\s*[장강부]` → "제1장", "제 1 장", "제1강", "제1부"
2. `CHAPTER\s*\d+` (대소문자 무시) → "Chapter 1", "Chapter1", "CHAPTER 1"
3. `Part\s*\d+` (대소문자 무시) → "Part 1", "Part1"
4. `^\d+\s*[장강부]` → "1장", "1 장", "1강"
5. `^\d+\.\s*[가-힣]` → "1. 제목", "1.제목"

### 3.4 페이지 번호 판별

**조건**:
- `x0 < 0.05` (왼쪽 끝 영역)
- 정규식: `^\d{1,3}$` (1-3자리 숫자만)
- 범위: 1-1000

### 3.5 챕터 키워드

**키워드 목록**: `["제", "장", "강", "부", "chapter", "part"]`

**사용 조건**:
- `0.05 < x0 < 0.5` (중앙 영역)
- 위 키워드 중 하나라도 포함되면 → `chapter_marker`

### 3.6 구현 코드

```python
def _classify_footer_element(self, elem: Dict) -> str:
    text = elem.get("text", "").strip()
    bbox = elem.get("bbox", {})
    x0 = bbox.get("x0", 0.5)
    
    # 1. 챕터 패턴 확인 (최우선)
    if self._is_chapter_pattern(text):
        return "chapter_marker"
    
    # 2. 위치 기반 판단
    if x0 < 0.05:  # 왼쪽 끝 (페이지 번호 영역)
        if self._is_page_number(text):
            return "page_number"
    
    # 3. 중앙 영역 (챕터 제목 영역)
    if 0.05 < x0 < 0.5:  # 중앙
        if self._has_chapter_keywords(text):
            return "chapter_marker"
    
    # 4. 기타
    return "other"
```

### 3.7 식별자

- **x0 좌표**: 정규화된 좌표 (0.0 ~ 1.0)
  - `x0 < 0.05`: 왼쪽 끝 (페이지 번호 영역)
  - `0.05 < x0 < 0.5`: 중앙 (챕터 제목 영역)
  - `x0 > 0.5`: 오른쪽 (기타)
- **정규식 패턴**: 챕터 표시 판별자 인식
- **키워드**: 챕터 관련 키워드로 보조 판별

---

## 4. 본문 시작 페이지 탐지

### 4.1 탐지 목적

서문과 본문의 경계를 찾아 본문 시작 페이지를 결정합니다.

### 4.2 탐지 로직

**메서드**: `_detect_main_start_improved(pages: List[Dict]) -> int`

**단계**:
1. **홀수 페이지만 순회** (3페이지부터 시작, 1-2페이지는 표지로 제외)
2. **각 페이지의 Footer 요소 분류**
   - `_get_footer_elements()`로 Footer 요소 추출
   - `_classify_footer_element()`로 각 요소 분류
   - `chapter_marker` 분류된 요소만 추출
3. **챕터 표시 판별자 확인**
   - `chapter_marker`가 있으면 본문 시작 후보
4. **서문 키워드 확인**
   - 페이지 전체 텍스트에서 START_KEYWORDS 확인
   - 서문 키워드가 없으면 → 본문 시작으로 확정
5. **기본값**
   - 챕터 표시 판별자가 없으면 → 3페이지 (기본값)

### 4.3 서문 키워드 목록

**한글**: "작가", "작가 소개", "저자", "저자 소개", "저자소개", "지은이", "추천", "추천의 글", "추천사", "추천하는 말", "서문", "머리말", "프롤로그", "들어가며", "들어가는 글", "들어가는 말", "처음으로", "작품 소개", "작품소개", "옮긴이", "서론", "감수", "시작하며", "감사의 글", "감사", "헌정", "표지", "판권", "저작권", "차례", "목차"

**영어**: "author", "about the author", "recommendation", "foreword", "preface", "prologue", "introduction", "acknowledgment", "dedication", "copyright", "contents", "table of contents"

### 4.4 구현 코드

```python
def _detect_main_start_improved(self, pages: List[Dict]) -> int:
    for page in pages:
        page_num = page.get("page_number", 0)
        
        # 표지는 제외 (1-2페이지)
        if page_num <= 2:
            continue
        
        # 홀수 페이지만 처리
        if page_num % 2 == 0:
            continue
        
        # Footer 요소 분류
        footer_elements = self._get_footer_elements(page)
        chapter_markers = [
            elem
            for elem in footer_elements
            if self._classify_footer_element(elem) == "chapter_marker"
        ]
        
        # 챕터 표시가 있으면 본문 시작 후보
        if chapter_markers:
            # 서문 키워드 확인 (페이지 전체 텍스트에서)
            if not self._has_start_keywords(page):
                logger.info(f"[INFO] Main starts at page {page_num} (챕터 표시 판별자 발견)")
                return page_num
    
    # 기본값: 3페이지부터
    logger.info("[INFO] Main starts at page 3 (기본값, 챕터 표시 판별자 없음)")
    return 3
```

### 4.5 식별자

- **챕터 표시 판별자** (`chapter_marker`): Footer에서 추출된 챕터 패턴 매칭 요소
- **서문 키워드** (START_KEYWORDS): 페이지 전체 텍스트에서 확인
- **페이지 번호**: 홀수 페이지만 처리 (1, 3, 5, 7, ...)

---

## 5. 종문 시작 페이지 탐지

### 5.1 탐지 목적

본문과 종문의 경계를 찾아 종문 시작 페이지를 결정합니다.

### 5.2 탐지 로직

**메서드**: `_detect_notes_start_improved(pages: List[Dict], main_start: int) -> Optional[int]`

**단계**:
1. **본문 후반부만 검사** (전체의 50% 이후 또는 본문 시작 이후)
2. **홀수 페이지만 역순 순회** (뒤에서 앞으로)
3. **각 페이지의 Footer 텍스트 추출**
   - Footer 요소들의 텍스트를 공백으로 연결
4. **종문 키워드 확인**
   - Footer 텍스트에서 END_KEYWORDS 부분 문자열 매칭
   - 매칭되면 → 종문 시작으로 확정
5. **매칭된 키워드 로깅**
   - 어떤 키워드가 어디서 매칭되었는지 상세 로깅

### 5.3 종문 키워드 목록

**한글**: "맺음말", "맺는 글", "맺는 말", "끝맺음", "나가며", "마치며", "에필로그", "결론", "주", "각주", "미주", "참고 주", "주석", "참고문헌", "참고 문헌", "참고자료", "문헌", "부록", "색인", "용어집", "출판", "출판사", "출판정보", "판권", "출처", "해설", "감사", "닫는 글", "도서정보", "찾아보기", "감수"

**영어**: "epilogue", "conclusion", "closing", "endnote", "endnotes", "notes", "footnote", "references", "bibliography", "appendix", "appendices", "index", "glossary", "publisher", "publishing"

**주의사항**: 부분 문자열 매칭으로 인한 오탐지 가능 (예: "자주" 안의 "주")

### 5.4 구현 코드

```python
def _detect_notes_start_improved(self, pages: List[Dict], main_start: int) -> Optional[int]:
    # 본문 후반부만 검사 (전체의 50% 이후)
    search_start_idx = max(main_start, int(len(pages) * 0.5))
    
    for page in pages[search_start_idx:]:
        page_num = page.get("page_number", 0)
        
        # 홀수 페이지만 처리
        if page_num % 2 == 0:
            continue
        
        # Footer 요소에서 종문 키워드 확인
        footer_elements = self._get_footer_elements(page)
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
        
        if matched_keywords:
            logger.info(f"[INFO] Post-body starts at page {page_num} (종문 키워드 발견: {matched_keywords})")
            return page_num
    
    return None
```

### 5.5 식별자

- **종문 키워드** (END_KEYWORDS): Footer 텍스트에서 부분 문자열 매칭
- **Footer 텍스트**: Footer 요소들의 텍스트를 공백으로 연결한 전체 문자열

---

## 6. 챕터 번호 추출

### 6.1 추출 목적

본문 영역의 각 홀수 페이지에서 챕터 번호를 추출합니다.

### 6.2 추출 로직

**메서드**: `_extract_chapter_numbers_improved(pages: List[Dict]) -> Dict[int, Optional[int]]`

**단계**:
1. **본문 영역의 홀수 페이지만 필터링**
2. **각 페이지의 Footer 요소 분류**
   - `_get_footer_elements()`로 Footer 요소 추출
   - `_classify_footer_element()`로 각 요소 분류
   - `chapter_marker` 분류된 요소만 추출
3. **챕터 패턴에서 숫자 추출**
   - `_extract_chapter_number_from_pattern()`로 패턴에서 숫자 추출
   - 첫 번째 매칭된 패턴의 숫자를 챕터 번호로 사용
4. **결과 저장**
   - `{page_number: chapter_number or None}` 형식으로 저장

### 6.3 챕터 번호 추출 로직

**메서드**: `_extract_chapter_number_from_pattern(text: str) -> Optional[int]`

**단계**:
1. **챕터 패턴 순회**
   - 각 정규식 패턴에 대해 `search()` 실행
2. **매칭 그룹에서 숫자 추출**
   - 패턴의 첫 번째 그룹 `(\d+)`에서 숫자 추출
   - 예: "제1장" → 패턴 `제\s*(\d+)\s*[장강부]` → 그룹 1 → `1`
3. **유효성 검증**
   - 숫자가 1 이상이면 유효
4. **반환**
   - 유효한 숫자 반환, 없으면 `None`

### 6.4 챕터 번호 연속성 필터링

**메서드**: `_filter_valid_chapter_numbers(page_chapter_numbers: Dict[int, Optional[int]]) -> Dict[int, Optional[int]]`

**목적**: 비연속적인 챕터 번호 제거 (예: [1, 2, 3, 100, 200] → [1, 2, 3])

**단계**:
1. **모든 챕터 번호 수집**
2. **가장 긴 연속 시퀀스 찾기**
   - `_find_continuous_sequence()`로 연속적인 번호 시퀀스 찾기
   - 예: [1, 2, 3, 4, 5, 6, 7, 100, 200] → {1, 2, 3, 4, 5, 6, 7}
3. **유효한 번호만 유지**
   - 연속 시퀀스에 포함된 번호만 유지
   - 나머지는 `None`으로 변경

### 6.5 구현 코드

```python
def _extract_chapter_numbers_improved(self, pages: List[Dict]) -> Dict[int, Optional[int]]:
    page_chapter_numbers = {}
    
    for page in pages:
        page_num = page.get("page_number", 0)
        
        # Footer 영역 요소 추출
        footer_elements = self._get_footer_elements(page)
        
        # 각 Footer 요소 분류
        chapter_markers = []
        for elem in footer_elements:
            classification = self._classify_footer_element(elem)
            if classification == "chapter_marker":
                chapter_markers.append(elem)
        
        # 챕터 번호 추출
        chapter_number = None
        for marker in chapter_markers:
            text = marker.get("text", "").strip()
            number = self._extract_chapter_number_from_pattern(text)
            if number:
                chapter_number = number
                break
        
        page_chapter_numbers[page_num] = chapter_number
    
    return page_chapter_numbers
```

### 6.6 식별자

- **챕터 표시 판별자** (`chapter_marker`): Footer에서 추출된 챕터 패턴 매칭 요소
- **정규식 그룹**: 패턴의 첫 번째 그룹 `(\d+)`에서 숫자 추출
- **연속 시퀀스**: 가장 긴 연속적인 번호 집합

---

## 7. 챕터 경계 계산

### 7.1 계산 목적

챕터 번호가 변경되는 지점을 찾아 각 챕터의 시작/끝 페이지를 계산합니다.

### 7.2 경계 계산 로직

**메서드**: `_detect_chapter_boundaries(page_chapter_numbers: Dict[int, Optional[int]], main_pages: List[int]) -> List[Dict[str, Any]]`

**단계**:
1. **페이지 번호 순서대로 정렬**
2. **챕터 번호 변경 지점 탐지**
   - 현재 챕터 번호와 다른 번호가 나타나면 → 새 챕터 시작
   - 이전 챕터의 끝 페이지 = 새 챕터 시작 페이지 - 1
3. **마지막 챕터 처리**
   - 마지막 챕터의 끝 페이지 = 본문 끝 페이지
4. **짝수 페이지 포함 조정**
   - `_adjust_boundaries_for_even_pages()`로 짝수 페이지도 포함

### 7.3 짝수 페이지 조정

**메서드**: `_adjust_boundaries_for_even_pages(chapters: List[Dict], main_pages: List[int]) -> List[Dict]`

**로직**:
- 다음 챕터가 홀수 페이지에서 시작하면 → 현재 챕터는 그 전 짝수 페이지까지
- 다음 챕터가 짝수 페이지에서 시작하면 → 현재 챕터는 그 전 홀수 페이지까지
- 마지막 챕터는 본문 끝 페이지까지

### 7.4 구현 코드

```python
def _detect_chapter_boundaries(self, page_chapter_numbers: Dict[int, Optional[int]], main_pages: List[int]) -> List[Dict[str, Any]]:
    chapters = []
    current_chapter = None
    current_start_page = None
    
    # 페이지 번호 순서대로 정렬
    sorted_pages = sorted(page_chapter_numbers.keys())
    
    for page_num in sorted_pages:
        chapter_number = page_chapter_numbers[page_num]
        
        if chapter_number is None:
            # 숫자가 없으면 현재 챕터에 포함
            continue
        
        if current_chapter is None or chapter_number != current_chapter:
            # 새로운 챕터 시작
            if current_chapter is not None:
                # 이전 챕터 종료
                chapters.append({
                    "id": f"ch{current_chapter}",
                    "number": current_chapter,
                    "title": f"제{current_chapter}장",
                    "start_page": current_start_page,
                    "end_page": page_num - 1,  # 다음 챕터 시작 전까지
                    "score": 100.0,
                    "detection_method": "footer_pattern",
                })
            
            # 새 챕터 시작
            current_chapter = chapter_number
            current_start_page = page_num
    
    # 마지막 챕터 종료
    if current_chapter is not None:
        chapters.append({
            "id": f"ch{current_chapter}",
            "number": current_chapter,
            "title": f"제{current_chapter}장",
            "start_page": current_start_page,
            "end_page": main_pages[-1] if main_pages else current_start_page,
            "score": 100.0,
            "detection_method": "footer_pattern",
        })
    
    # 짝수 페이지도 포함하여 경계 조정
    chapters = self._adjust_boundaries_for_even_pages(chapters, main_pages)
    
    return chapters
```

### 7.5 식별자

- **챕터 번호 변경 지점**: `page_chapter_numbers`에서 번호가 변경되는 페이지
- **홀수 페이지 기준**: 챕터 시작 페이지는 항상 홀수 페이지
- **짝수 페이지 포함**: 인접한 짝수 페이지도 같은 챕터로 간주

---

## 요약: 식별자 정리

### Footer 요소 추출
- **y0 좌표**: `y0 > 0.9` (페이지 하단 10% 영역)
- **category**: `category == 'footer'`

### Footer 요소 분류
- **챕터 패턴**: 정규식 패턴 5가지
- **x0 좌표**: 위치 기반 판별
  - `x0 < 0.05`: 페이지 번호 영역
  - `0.05 < x0 < 0.5`: 챕터 제목 영역
- **키워드**: 챕터 관련 키워드 목록

### 본문 시작 페이지 탐지
- **챕터 표시 판별자** (`chapter_marker`): Footer에서 추출
- **서문 키워드** (START_KEYWORDS): 페이지 전체 텍스트에서 확인
- **홀수 페이지**: 3페이지부터 홀수 페이지만 처리

### 종문 시작 페이지 탐지
- **종문 키워드** (END_KEYWORDS): Footer 텍스트에서 부분 문자열 매칭
- **본문 후반부**: 전체의 50% 이후 또는 본문 시작 이후

### 챕터 번호 추출
- **챕터 표시 판별자** (`chapter_marker`): Footer에서 추출
- **정규식 그룹**: 패턴의 첫 번째 그룹 `(\d+)`에서 숫자 추출
- **연속 시퀀스**: 가장 긴 연속적인 번호 집합

### 챕터 경계 계산
- **챕터 번호 변경 지점**: `page_chapter_numbers`에서 번호가 변경되는 페이지
- **홀수 페이지 기준**: 챕터 시작 페이지는 항상 홀수 페이지
- **짝수 페이지 포함**: 인접한 짝수 페이지도 같은 챕터로 간주

