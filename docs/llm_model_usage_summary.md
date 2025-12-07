# LLM 모델 사용 현황 (Summary 관련)

## 현재 모델 사용 현황

**모든 Summary 관련 작업은 `gpt-4.1-mini`로 통일되었습니다.**

### 1. Page Extraction (페이지 엔티티 추출)
- **클래스**: `PageExtractionChain`
- **모델**: `gpt-4.1-mini`
- **위치**: `backend/summarizers/llm_chains.py:43`
- **용도**: 페이지 텍스트에서 구조화된 엔티티 추출 (Structured Output 사용)
- **특징**: 도메인별 스키마에 맞는 엔티티 추출

### 2. Chapter Structuring (챕터 구조화)
- **클래스**: `ChapterStructuringChain`
- **모델**: `gpt-4.1-mini`
- **위치**: `backend/summarizers/llm_chains.py:298`
- **용도**: 페이지 엔티티를 집계하여 챕터 구조화 (Structured Output 사용)
- **특징**: 도메인별 스키마에 맞는 챕터 구조 생성

### 3. Book Summary (책 전체 요약)
- **클래스**: `BookSummaryChain`
- **모델**: `gpt-4.1-mini` ✅ (변경됨)
- **위치**: `backend/summarizers/llm_chains.py:533`
- **용도**: 챕터별 요약을 집계하여 책 전체 요약 생성
- **특징**: JSON 응답 파싱 (Structured Output 미사용)

### 4. Entity Synthesis (엔티티 집계)
- **클래스**: `EntitySynthesisChain`
- **모델**: `gpt-4.1-mini` ✅ (변경됨)
- **위치**: `backend/summarizers/llm_chains.py:756`
- **용도**: 챕터별 엔티티를 집계하여 책 전체 엔티티 생성
- **특징**: JSON 배열 응답 파싱 (Structured Output 미사용)

---

## 모델 통일 이유

### gpt-4.1-mini로 통일
- **비용 효율성**: 모든 작업에서 일관된 비용 구조
- **Structured Output 지원**: 필요시 Structured Output 활용 가능
- **일관성**: 모든 Summary 작업에서 동일한 모델 사용

---

## 참고사항

- **모든 Summary 관련 작업**: `gpt-4.1-mini` 사용
- **Structured Output**: Page/Chapter에서 사용, Book/Entity는 일반 JSON 파싱
- **비용 절감**: 통일된 모델로 비용 관리 용이

