# Phase 3 참고 파일 Align 계획

## 참고 파일 목록

1. `content_boundary_detector.py`: 본문 영역 경계 탐지
2. `chapter_detector.py`: 챕터 경계 탐지
3. `structure_builder.py`: 전체 구조 통합
4. `footer_analyzer.py`: Footer 분석 (보조 수단, 선택적)
5. `hierarchy_builder.py`: 계층 구조 구축 (선택적)

## 주요 차이점 요약

### 1. 이모지 사용
- **참고 파일**: 이모지 사용 (🔍, ✅, 🏗️, 📑 등)
- **현재 프로젝트**: 이모지 사용 금지 → `[INFO]`, `[ERROR]`, `[WARNING]` 형식 사용

### 2. 로깅 형식
- **참고 파일**: 일반 로깅 (`logger.info()`, `logger.error()`, `logger.warning()`)
- **현재 프로젝트**: `[INFO]`, `[ERROR]`, `[WARNING]` 형식 사용

### 3. FooterAnalyzer 의존성
- **참고 파일**: `ContentBoundaryDetector`가 `FooterAnalyzer` 사용
- **현재 프로젝트**: FooterAnalyzer는 보조 수단이므로 선택적 구현 (Phase 3에서는 제외 가능)

### 4. HierarchyBuilder 의존성
- **참고 파일**: `StructureBuilder`가 `HierarchyBuilder` 사용 (챕터 내 섹션 구조)
- **현재 프로젝트**: Phase 3에서는 챕터 레벨만 구현, 섹션 구조는 선택적 (제외 가능)

### 5. 설정 관리
- **참고 파일**: 상수 직접 정의
- **현재 프로젝트**: `backend/config/constants.py`에 상수 정의 권장

### 6. 키워드 및 패턴
- **참고 파일**: 확장된 키워드 리스트 사용
- **현재 프로젝트**: 동일하게 적용하되, `constants.py`로 이동

## 클래스명/함수명 매핑 테이블

### ContentBoundaryDetector

| 참고 파일 | 현재 프로젝트 | 변경 사항 |
|-----------|--------------|----------|
| `ContentBoundaryDetector` | `ContentBoundaryDetector` | 동일 (유지) |
| `detect_boundaries()` | `detect_boundaries()` | 동일 (유지) |
| `_detect_main_start()` | `_detect_main_start()` | 동일 (유지) |
| `_detect_notes_start()` | `_detect_notes_start()` | 동일 (유지) |
| `_check_footer_elements()` | `_check_footer_elements()` | 동일 (유지) |
| `_check_title_like_elements()` | `_check_title_like_elements()` | 동일 (유지) |
| `_check_full_text()` | `_check_full_text()` | 동일 (유지) |
| `_calculate_main_start_score()` | `_calculate_main_start_score()` | 동일 (유지) |
| `_default_result()` | `_default_result()` | 동일 (유지) |
| `PRE_BODY_KEYWORDS` | `START_KEYWORDS` (constants.py) | 이름 변경, constants.py로 이동 |
| `POST_BODY_KEYWORDS` | `END_KEYWORDS` (constants.py) | 이름 변경, constants.py로 이동 |
| `MAIN_START_PATTERNS` | `MAIN_START_PATTERNS` (constants.py) | constants.py로 이동 |
| `MIN_PARAGRAPH_LENGTH` | `MIN_PARAGRAPH_LENGTH` (constants.py) | constants.py로 이동 |

**주의사항**:
- `FooterAnalyzer` 의존성 제거 또는 선택적 사용
- 이모지 제거 및 로깅 형식 변경

### ChapterDetector

| 참고 파일 | 현재 프로젝트 | 변경 사항 |
|-----------|--------------|----------|
| `ChapterDetector` | `ChapterDetector` | 동일 (유지) |
| `detect_chapters()` | `detect_chapters()` | 동일 (유지) |
| `_find_chapter_candidates()` | `_find_chapter_candidates()` | 동일 (유지) |
| `_calculate_chapter_score()` | `_calculate_chapter_score()` | 동일 (유지) |
| `_validate_and_refine_chapters()` | `_validate_and_refine_chapters()` | 동일 (유지) |
| `CHAPTER_PATTERNS` | `CHAPTER_PATTERNS` (constants.py) | constants.py로 이동 |
| `MIN_CHAPTER_SPACING` | `MIN_CHAPTER_SPACING` (constants.py) | constants.py로 이동 |
| `LARGE_FONT_THRESHOLD` | `LARGE_FONT_THRESHOLD` (constants.py) | constants.py로 이동 |
| `SCORE_THRESHOLD` | `SCORE_THRESHOLD` (constants.py) | constants.py로 이동 |

**주의사항**:
- 이모지 제거 및 로깅 형식 변경

### StructureBuilder

| 참고 파일 | 현재 프로젝트 | 변경 사항 |
|-----------|--------------|----------|
| `StructureBuilder` | `StructureBuilder` | 동일 (유지) |
| `build_structure()` | `build_structure()` | 동일 (유지) |
| `boundary_detector` | `boundary_detector` | 동일 (유지) |
| `chapter_detector` | `chapter_detector` | 동일 (유지) |
| `hierarchy_builder` | 제외 (Phase 3에서는 불필요) | 제거 |

**주의사항**:
- `HierarchyBuilder` 의존성 제거 (Phase 3에서는 챕터 레벨만 구현)
- 이모지 제거 및 로깅 형식 변경

## 구현 순서

1. **ContentBoundaryDetector** 구현
   - FooterAnalyzer 의존성 제거 또는 선택적 사용
   - 키워드 상수를 constants.py로 이동
   - 이모지 제거 및 로깅 형식 변경

2. **ChapterDetector** 구현
   - 패턴 상수를 constants.py로 이동
   - 이모지 제거 및 로깅 형식 변경

3. **StructureBuilder** 구현
   - HierarchyBuilder 의존성 제거
   - ContentBoundaryDetector와 ChapterDetector 통합
   - 이모지 제거 및 로깅 형식 변경

## 로깅 형식 변경 예시

### 참고 파일
```python
logger.info("🔍 Detecting content boundaries (서문/본문/종문)...")
logger.info(f"✅ Boundaries detected:")
```

### 현재 프로젝트
```python
logger.info("[INFO] Detecting content boundaries (서문/본문/종문)...")
logger.info("[INFO] Boundaries detected:")
```

## 상수 이동 예시

### 참고 파일
```python
class ContentBoundaryDetector:
    PRE_BODY_KEYWORDS = [...]
    POST_BODY_KEYWORDS = [...]
```

### 현재 프로젝트
```python
# backend/config/constants.py
START_KEYWORDS = [...]
END_KEYWORDS = [...]

# backend/structure/content_boundary_detector.py
from backend.config.constants import START_KEYWORDS, END_KEYWORDS
```

