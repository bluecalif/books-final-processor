# 책 전체 보고서 명세서

## 개요

챕터 서머리를 집계하여 책 전체 보고서를 생성하는 기능의 상세 명세입니다.

## 데이터 구조

### 전체 구조

```json
{
  "metadata": { ... },
  "book_summary": { ... },
  "chapters": [ ... ],
  "entity_synthesis": { ... },
  "statistics": { ... }
}
```

## 항목별 생성 방식 상세

### 1. 메타데이터 (metadata)

| 항목명 | 생성 방식 | 입력 소스 | 처리 방법 | 비고 |
|--------|----------|----------|----------|------|
| `book_id` | 단순 집계 | `Book.id` | DB 조회 | - |
| `title` | 단순 집계 | `Book.title` | DB 조회 | - |
| `author` | 단순 집계 | `Book.author` | DB 조회 | - |
| `category` | 단순 집계 | `Book.category` | DB 조회 | - |
| `page_count` | 단순 집계 | `Book.page_count` | DB 조회 | - |
| `chapter_count` | 단순 집계 | `Chapter` 테이블 COUNT | DB 조회 | - |
| `processed_chapters` | 단순 집계 | `ChapterSummary` 테이블 COUNT | DB 조회 | 서머리 생성된 챕터 수 |
| `skipped_chapters` | 단순 집계 | `Chapter` COUNT - `ChapterSummary` COUNT | 계산 | 2페이지 이하 스킵된 챕터 수 |
| `generated_at` | 단순 집계 | 현재 시간 | `datetime.utcnow()` | 보고서 생성 일시 |
| `status` | 단순 집계 | `Book.status` | DB 조회 | - |

**요약**: 메타데이터는 모두 **단순 집계** (DB 조회 또는 계산)

---

### 2. 책 전체 요약 (book_summary)

| 항목명 | 생성 방식 | 입력 소스 | 처리 방법 | 비고 |
|--------|----------|----------|----------|------|
| `core_message` | **LLM 생성** | 챕터별 `core_message` 리스트 | LLM 프롬프트: "챕터별 핵심 메시지를 바탕으로 책 전체의 한 줄 핵심 메시지 생성" | - |
| `summary_3_5_sentences` | **LLM 생성** | 챕터별 `summary_3_5_sentences` 리스트 | LLM 프롬프트: "챕터별 요약을 바탕으로 책 전체를 3-5문장으로 요약" | - |
| `main_themes` | **LLM 생성** | 챕터별 `core_message`, `summary_3_5_sentences` | LLM 프롬프트: "챕터별 핵심 메시지와 요약을 바탕으로 책의 주요 주제 5-7개 추출" | - |
| `argument_flow.overall_problem` | **LLM 생성** | 챕터별 `argument_flow.problem` | LLM 프롬프트: "챕터별 문제 제기를 바탕으로 책 전체의 핵심 문제 제기" | - |
| `argument_flow.overall_background` | **LLM 생성** | 챕터별 `argument_flow.background` | LLM 프롬프트: "챕터별 배경 설명을 바탕으로 책 전체의 배경 설명 통합" | - |
| `argument_flow.key_arguments` | **LLM 생성** | 챕터별 `argument_flow.main_claims` | LLM 프롬프트: "챕터별 주요 주장을 바탕으로 책 전체의 핵심 주장 8-12개 선별 및 통합" | 중복 제거 및 통합 |
| `argument_flow.overall_conclusion` | **LLM 생성** | 챕터별 `argument_flow.conclusion_or_action` | LLM 프롬프트: "챕터별 결론을 바탕으로 책 전체의 결론 통합" | - |

**요약**: 책 전체 요약은 모두 **LLM 생성** (챕터별 요약을 집계하여 LLM으로 통합)

---

### 3. 챕터별 요약 (chapters)

| 항목명 | 생성 방식 | 입력 소스 | 처리 방법 | 비고 |
|--------|----------|----------|----------|------|
| `chapter_number` | 단순 집계 | `Chapter.order_index + 1` | DB 조회 | 1-based |
| `chapter_title` | 단순 집계 | `Chapter.title` | DB 조회 | - |
| `page_range` | 단순 집계 | `Chapter.start_page`, `Chapter.end_page` | 계산: `"{start_page}-{end_page}"` | - |
| `page_count` | 단순 집계 | `Chapter.start_page`, `Chapter.end_page` | 계산: `end_page - start_page + 1` | - |
| `core_message` | 단순 집계 | `ChapterSummary.structured_data.core_message` | DB 조회 | - |
| `summary_3_5_sentences` | 단순 집계 | `ChapterSummary.structured_data.summary_3_5_sentences` | DB 조회 | - |

**요약**: 챕터별 요약은 모두 **단순 집계** (DB에서 조회하여 그대로 나열)

---

### 4. 엔티티 집계 (entity_synthesis)

| 항목명 | 생성 방식 | 입력 소스 | 처리 방법 | 비고 |
|--------|----------|----------|----------|------|
| `insights` | **LLM 생성** | 챕터별 `insights` 리스트 | LLM 프롬프트: "챕터별 인사이트를 바탕으로 책 전체의 핵심 인사이트 10-15개 선별 및 융합" | 중복 제거, 유사 항목 융합 |
| `key_events` | **LLM 생성** | 챕터별 `key_events` 리스트 | LLM 프롬프트: "챕터별 핵심 사건을 바탕으로 책 전체의 핵심 사건 15-20개 선별 및 통합" | 중복 제거, 시간순 정렬 (가능시) |
| `key_examples` | **LLM 생성** | 챕터별 `key_examples` 리스트 | LLM 프롬프트: "챕터별 핵심 예시를 바탕으로 책 전체의 대표 예시 10-15개 선별 및 통합" | 중복 제거, 대표성 기반 선별 |
| `key_persons` | **LLM 생성** | 챕터별 `key_persons` 리스트 | LLM 프롬프트: "챕터별 핵심 인물을 바탕으로 책 전체의 핵심 인물 15-20개 선별 및 통합" | 중복 제거 (동일 인물 통합) |
| `key_concepts` | **LLM 생성** | 챕터별 `key_concepts` 리스트 | LLM 프롬프트: "챕터별 핵심 개념을 바탕으로 책 전체의 핵심 개념 20-25개 선별 및 통합" | 중복 제거, 유사 개념 융합 |
| `references` | **단순 집계** | 챕터별 `references` 리스트 | 중복 제거 후 병합 | Set을 사용한 중복 제거 |
| `main_arguments` | **LLM 생성** | 챕터별 `argument_flow.main_claims` | LLM 프롬프트: "챕터별 주요 주장을 바탕으로 책 전체의 핵심 주장 12-18개 선별 및 통합" | 중복 제거, 논리적 통합 |

**도메인별 추가 엔티티**:

| 도메인 | 항목명 | 생성 방식 | 입력 소스 | 처리 방법 | 비고 |
|--------|--------|----------|----------|----------|------|
| History | `timeline` | **LLM 생성** | 챕터별 `timeline` 리스트 | LLM 프롬프트: "챕터별 타임라인을 바탕으로 책 전체의 통합 타임라인 생성 (시간순 정렬)" | 시간순 정렬, 중복 제거 |
| History | `geo_map` | **LLM 생성** | 챕터별 `geo_map` | LLM 프롬프트: "챕터별 지리적 맵을 바탕으로 책 전체의 지리적 맵 통합 설명" | - |
| History | `structure_layer` | **LLM 생성** | 챕터별 `structure_layer` | LLM 프롬프트: "챕터별 구조 레이어를 바탕으로 책 전체의 정치/경제/사회/문화 구조 통합 설명" | - |
| Economy | `frameworks` | **LLM 생성** | 챕터별 `frameworks` 리스트 | LLM 프롬프트: "챕터별 프레임워크를 바탕으로 책 전체의 핵심 프레임워크 8-12개 선별 및 통합" | 중복 제거, 통합 |
| Economy | `scenarios` | **LLM 생성** | 챕터별 `scenarios` 리스트 | LLM 프롬프트: "챕터별 시나리오를 바탕으로 책 전체의 핵심 시나리오 5-8개 선별 및 통합" | - |
| Economy | `playbooks` | **LLM 생성** | 챕터별 `playbooks` 리스트 | LLM 프롬프트: "챕터별 행동 가이드를 바탕으로 책 전체의 핵심 행동 가이드 8-12개 선별 및 통합" | - |
| Humanities | `life_themes` | **LLM 생성** | 챕터별 `life_themes` 리스트 | LLM 프롬프트: "챕터별 삶의 주제를 바탕으로 책 전체의 핵심 삶의 주제 8-12개 선별 및 통합" | - |
| Humanities | `practice_recipes` | **LLM 생성** | 챕터별 `practice_recipes` 리스트 | LLM 프롬프트: "챕터별 실천 프로토콜을 바탕으로 책 전체의 핵심 실천 프로토콜 10-15개 선별 및 통합" | - |
| Humanities | `dilemmas` | **LLM 생성** | 챕터별 `dilemmas` 리스트 | LLM 프롬프트: "챕터별 딜레마를 바탕으로 책 전체의 핵심 딜레마 8-12개 선별 및 통합" | - |
| Humanities | `identity_shifts` | **LLM 생성** | 챕터별 `identity_shifts` 리스트 | LLM 프롬프트: "챕터별 정체성 변화를 바탕으로 책 전체의 핵심 정체성 변화 5-8개 선별 및 통합" | - |
| Science | `technologies` | **LLM 생성** | 챕터별 `technologies` 리스트 | LLM 프롬프트: "챕터별 기술을 바탕으로 책 전체의 핵심 기술 10-15개 선별 및 통합" | - |
| Science | `systems` | **LLM 생성** | 챕터별 `systems` 리스트 | LLM 프롬프트: "챕터별 시스템을 바탕으로 책 전체의 핵심 시스템 8-12개 선별 및 통합" | - |
| Science | `applications` | **LLM 생성** | 챕터별 `applications` 리스트 | LLM 프롬프트: "챕터별 적용 영역을 바탕으로 책 전체의 핵심 적용 영역 8-12개 선별 및 통합" | - |
| Science | `risks_ethics` | **LLM 생성** | 챕터별 `risks_ethics` 리스트 | LLM 프롬프트: "챕터별 위험/윤리를 바탕으로 책 전체의 핵심 위험/윤리 이슈 5-8개 선별 및 통합" | - |

**요약**: 
- 공통 엔티티: `insights`, `key_events`, `key_examples`, `key_persons`, `key_concepts`, `main_arguments` → **LLM 생성**
- `references` → **단순 집계** (중복 제거)
- 도메인별 엔티티 → **LLM 생성**

---

### 5. 통계 정보 (statistics)

| 항목명 | 생성 방식 | 입력 소스 | 처리 방법 | 비고 |
|--------|----------|----------|----------|------|
| `total_pages` | 단순 집계 | `Book.page_count` | DB 조회 | - |
| `total_chapters` | 단순 집계 | `Chapter` 테이블 COUNT | DB 조회 | - |
| `processed_chapters` | 단순 집계 | `ChapterSummary` 테이블 COUNT | DB 조회 | - |
| `skipped_chapters` | 단순 집계 | `Chapter` COUNT - `ChapterSummary` COUNT | 계산 | - |
| `total_insights` | 단순 집계 | `entity_synthesis.insights` 길이 | 계산 | LLM 생성 후 카운트 |
| `total_key_events` | 단순 집계 | `entity_synthesis.key_events` 길이 | 계산 | LLM 생성 후 카운트 |
| `total_key_examples` | 단순 집계 | `entity_synthesis.key_examples` 길이 | 계산 | LLM 생성 후 카운트 |
| `total_key_persons` | 단순 집계 | `entity_synthesis.key_persons` 길이 | 계산 | LLM 생성 후 카운트 |
| `total_key_concepts` | 단순 집계 | `entity_synthesis.key_concepts` 길이 | 계산 | LLM 생성 후 카운트 |

**요약**: 통계 정보는 모두 **단순 집계** (DB 조회 또는 계산)

---

## LLM 호출 요약

### LLM 호출 횟수

1. **책 전체 요약 생성**: 1회
   - 입력: 챕터별 `core_message`, `summary_3_5_sentences`, `argument_flow`
   - 출력: `book_summary` 전체 (core_message, summary_3_5_sentences, main_themes, argument_flow)

2. **공통 엔티티 집계**: 6회
   - `insights` 집계: 1회
   - `key_events` 집계: 1회
   - `key_examples` 집계: 1회
   - `key_persons` 집계: 1회
   - `key_concepts` 집계: 1회
   - `main_arguments` 집계: 1회

3. **도메인별 엔티티 집계**: 도메인에 따라 1-4회
   - History: `timeline`, `geo_map`, `structure_layer` (3회)
   - Economy: `frameworks`, `scenarios`, `playbooks` (3회)
   - Humanities: `life_themes`, `practice_recipes`, `dilemmas`, `identity_shifts` (4회)
   - Science: `technologies`, `systems`, `applications`, `risks_ethics` (4회)

**총 LLM 호출 횟수**:
- 공통: 7회 (책 전체 요약 1회 + 공통 엔티티 6회)
- History: 10회 (공통 7회 + 도메인별 3회)
- Economy: 10회 (공통 7회 + 도메인별 3회)
- Humanities: 11회 (공통 7회 + 도메인별 4회)
- Science: 11회 (공통 7회 + 도메인별 4회)

### 단순 집계 항목

- 메타데이터 전체 (10개 항목)
- 챕터별 요약 전체 (6개 항목 × 챕터 수)
- `references` (중복 제거만)
- 통계 정보 전체 (9개 항목)

---

## 구현 우선순위

### Phase 1: 필수 항목 (기본 보고서)
1. 메타데이터 (단순 집계)
2. 책 전체 요약: `core_message`, `summary_3_5_sentences` (LLM 생성)
3. 챕터별 요약 (단순 집계)
4. 엔티티 집계: `insights`, `key_events`, `key_examples`, `key_persons`, `key_concepts` (LLM 생성)
5. 통계 정보 (단순 집계)

### Phase 2: 확장 항목 (선택)
6. 책 전체 요약: `main_themes`, `argument_flow` (LLM 생성)
7. 엔티티 집계: `references` (단순 집계), `main_arguments` (LLM 생성)
8. 도메인별 엔티티 집계 (LLM 생성)

---

## 참고사항

1. **캐시 전략**: 
   - 책 전체 요약: 캐시 저장 (챕터 요약 변경 시 재생성)
   - 엔티티 집계: 각 엔티티 타입별 캐시 저장

2. **성능 최적화**:
   - 엔티티 집계는 병렬 처리 가능 (각 엔티티 타입별 독립적)
   - 책 전체 요약과 엔티티 집계는 순차 처리 (의존성 없음)

3. **에러 처리**:
   - LLM 호출 실패 시 해당 항목만 None 또는 빈 리스트로 처리
   - 단순 집계 실패 시 기본값 사용

