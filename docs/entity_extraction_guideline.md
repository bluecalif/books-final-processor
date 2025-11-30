````markdown
# 장문 도서 JSON → 구조 스키마 변환 프레임워크 가이드라인  
(Book JSON → Structured Knowledge Schema Framework)

버전: v1.0  
대상: `100권 노션 원본` + 각 도서의 `*_simple.json` (페이지 단위 텍스트)  
목적:  
- 장문 도서 텍스트를 **페이지/챕터/도메인 구조화 스키마**로 변환  
- 단순 요약을 넘어 **사건·예시·개념·인사이트·참고자료**가 입체적으로 재사용 가능하게 만들기

---

## 1. 전체 구조 개요

### 1.1. 입력(Input)

1. **메타 도서 리스트 (CSV)**  
   - 파일 예: `100권 노션 원본_수정.csv`
   - 핵심 컬럼:
     - `일련번호`
     - `Title` (책 제목)
     - `구분` (분야: `역사/사회`, `경제/경영`, `인문/자기계발`, `과학/기술`)
     - `요약` (도서 전체 요약)
     - 그 외 저자, 연도, Topic 등

2. **개별 도서 텍스트 JSON**  
   - 파일 예: `1등의_통찰_simple.json`, `12가지인생_simple.json`, …  
   - 기본 구조 예시(공통 가정):

     ```jsonc
     {
       "book_title": "1등의 통찰",
       "metadata": {
         "total_pages": 284,
         "main_start_page": 37,
         "main_end_page": 246,
         "chapter_count": 7
       },
       "text_content": {
         "chapters": [
           {
             "order_index": 0,
             "chapter_number": 1,
             "title": "어깨를펴고똑바로서라",
             "start_page": 35,
             "end_page": 86,
             "pages": [
               { "page_number": 35, "text": "..." },
               { "page_number": 36, "text": "..." }
               // ...
             ]
           }
           // ...
         ]
       }
     }
     ```

### 1.2. 출력(Output)

도서 1권 기준, 최소 2단계 결과물을 생성:

1. **페이지 단위 구조화 (Page Schema)**  
   - `HistoryPage` / `EconomyPage` / `HumanitiesPage` / `SciencePage`  
   - 공통 필수 필드: `page_summary`, `persons`, `concepts`, `events`, `examples`, `references`, `key_sentences`  
   - 도메인별 확장 필드(예: 역사 → `locations`, `time_periods`, …)

2. **챕터 단위 구조화 (Chapter Schema)**  
   - `HistoryChapter` / `EconomyChapter` / `HumanitiesChapter` / `ScienceChapter`  
   - 공통 필수 필드: `core_message`, `summary_3_5_sentences`, `argument_flow`, `key_*`, `insights`, `chapter_level_synthesis`, `references`  
   - 도메인별 확장 필드(예: 경제 → `claims`, `frameworks`, `scenarios`, `playbooks` …)

---

## 2. 도메인별 스키마 선택 규칙

도서 리스트 CSV의 `구분` 컬럼을 기준으로 도메인 매핑:

- `구분 = "역사/사회"` →  
  - 페이지: `HistoryPage`  
  - 챕터: `HistoryChapter`

- `구분 = "경제/경영"` →  
  - 페이지: `EconomyPage`  
  - 챕터: `EconomyChapter`

- `구분 = "인문/자기계발"` →  
  - 페이지: `HumanitiesPage`  
  - 챕터: `HumanitiesChapter`

- `구분 = "과학/기술"` →  
  - 페이지: `SciencePage`  
  - 챕터: `ScienceChapter`

**원칙**  
- 공통 스키마(`BasePage`, `BaseChapter`)는 항상 동일  
- 도메인별 스키마는 **“추가 필드만 다르다”**  
  - 기존 파이프라인 재사용을 위해 공통 필드 중심으로 설계  
  - 도메인별 필드는 LLM이 추가적으로 태깅/추출

---

## 3. 처리 파이프라인 개요

### 단계 0. 준비 (도서 메타 매핑)

1. `100권 노션 원본_수정.csv` 로드
2. 각 행(도서)에 대해:
   - `book_id` 생성:  
     - 예: `일련번호` 또는 `slug(제목)` 기반
   - `domain` 매핑:
     - `domain = row["구분"]`  (4개 값 중 하나)
   - `book_summary = row["요약"]` 저장 (후속 컨텍스트에 사용)

3. 개별 도서 JSON 파일명과 `book_id` 매핑 테이블 생성  
   - 예:  
     - `book_id = 12` → `12가지인생_simple.json`  
     - `book_id = 7` → `1등의_통찰_simple.json`

---

### 단계 1. JSON 파싱 → “Raw Chapter/Pages” 구조 생성

각 도서 JSON 파일에 대해:

1. `book_title`, `metadata`, `text_content.chapters` 파싱
2. 각 챕터별로 다음 정보를 1차 구조화:

   ```jsonc
   {
     "book_id": "12",
     "book_title": "12가지 인생의 법칙",
     "chapter_number": 1,
     "chapter_title": "어깨를펴고똑바로서라",
     "page_range": { "start": 35, "end": 86 },
     "pages": [
       { "page_number": 35, "raw_text": "..." },
       { "page_number": 36, "raw_text": "..." }
     ]
   }
````

3. 이 단계는 **LLM 전 단계**이며, 순수 파싱/정리만 수행.

---

### 단계 2. 페이지 단위 구조화 (Page-level Structuring)

목표:

* `raw_text` → 도메인별 `*Page` 스키마로 변환
* **텍스트 손실 최소화 + 구조적 태깅 최대화**

#### 2.1. 공통 처리 항목

각 `raw_page`에 대해 LLM으로 다음을 생성:

* `page_summary`

  * 2~4문장
  * 가능한 한 이 페이지가 장 전체 논지에서 **어떤 역할**인지 포함
* `page_function_tag`

  * 예: `"problem_statement"`, `"example_story"`, `"data_explanation"` 등
* `persons`
* `concepts`
* `events`
* `examples`
* `references`
* `key_sentences`
* `tone_tag`, `topic_tags`, `complexity` (간단 태그)

#### 2.2. 도메인별 확장 처리 항목

도메인에 따라 같은 LLM 요청 안에서 추가 추출:

1. **역사/사회 (HistoryPage)**

   * `locations` (도시/국가/지역/강 등)
   * `time_periods` (연대/세기/시대)
   * `polities` (왕조/제국/문명)

2. **경제/경영 (EconomyPage)**

   * `indicators` (지표/수치/그래프 요약)
   * `actors` (정부/기업/개인 투자자 등 이해관계자)
   * `strategies` (전략/원칙/규칙)
   * `cases` (회사/도시/산업/투자 사례)

3. **인문/자기계발 (HumanitiesPage)**

   * `psychological_states` (정서/심리 상태)
   * `life_situations` (직장/가족/관계 등 구체 상황)
   * `practices` (추천 습관/행동)
   * `inner_conflicts` (내적 갈등/딜레마)

4. **과학/기술 (SciencePage)**

   * `technologies` (핵심 기술)
   * `systems` (시스템/프로세스 구조)
   * `applications` (적용 영역/사례)
   * `risks_ethics` (위험/윤리/정책 이슈)

#### 2.3. LLM 프롬프트 설계 기본 원칙 (페이지 단위)

* **입력 컨텍스트**:

  * `book_title`
  * `chapter_title`, `chapter_number`
  * `domain(구분)`
  * `raw_page_text` (해당 페이지 전체)
* **출력 포맷**:

  * 도메인별 `*Page` 스키마 구조를 **JSON 형식**으로 고정
* **주의 사항**:

  * 원문에 없는 인물/사건/수치 생성 금지 (할루시네이션 방지)
  * 애매한 경우, `unknown`, `null`, 또는 빈 배열 사용
  * 한 페이지 내 사건/예시 ID는 `p{page_number}_ev1` 같은 규칙으로 생성

---

### 단계 3. 챕터 단위 구조화 (Chapter-level Structuring)

목표:

* **페이지별 구조화 결과를 집계/요약**해

  * `*Chapter` 스키마로 변환
* 이 단계는 페이지-level 결과를 LLM에게 요약/추상화 요청하는 형태

#### 3.1. 입력 컨텍스트

각 챕터에 대해 LLM 입력으로 제공:

1. `book_title`, `chapter_title`, `chapter_number`, `page_range`
2. 도서 요약 (`book_summary`)
3. 페이지-level 요약/엔티티 중 **압축된 버전**

   * 예: 각 페이지마다:

     * `page_number`
     * `page_summary`
     * `page_function_tag`
     * 주요 `concepts`/`events`/`examples`/`indicators` 등만 발췌

> 메모:
> 페이지 전체 엔티티를 전부 넣기보다는,
> **사전 집계/압축**(예: 상위 N개만 추려서) 후 LLM에 넘기는 설계가 비용/성능 측면에서 유리.

#### 3.2. 공통 항목 생성

LLM은 다음을 생성:

* `core_message` (한 줄)
* `summary_3_5_sentences`
* `argument_flow` 구조

  * `problem`, `background`, `main_claims`, `evidence_overview`, `counterpoints_or_limits`, `conclusion_or_action`
* `key_events`, `key_examples`, `key_persons`, `key_concepts`

  * 페이지-level 엔티티를 통합/중복 제거/정리
* `insights`

  * 한 문장 인사이트
  * `type` (principle/observation/strategy 등)
  * `supporting_evidence_ids` (페이지 이벤트/예시/참고자료 id와 연결)
* `chapter_level_synthesis`
* `references` (참고 문헌·자료 통합 정리)

#### 3.3. 도메인별 추가 항목 생성

1. **역사/사회 (HistoryChapter)**

   * `timeline`
   * `geo_map`
   * `structure_layer` (정치/경제/사회/문화 구조 요약)

2. **경제/경영 (EconomyChapter)**

   * `claims` (핵심 주장 목록)
   * `frameworks` (모델/프레임워크)
   * `scenarios` (미래 시나리오)
   * `playbooks` (행동 가이드/체크리스트)

3. **인문/자기계발 (HumanitiesChapter)**

   * `life_themes` (삶의 큰 주제)
   * `practice_recipes` (실천 프로토콜)
   * `dilemmas` (독자에게 던지는 딜레마/질문)
   * `identity_shifts` (정체성/세계관 변화)

4. **과학/기술 (ScienceChapter)**

   * `problem_domains` (다루는 문제 영역)
   * `impact_map` (이해관계자별 영향)
   * `ethics_issues` (윤리/사회 논쟁)
   * `future_scenarios` (기술/사회 변화 시나리오)

#### 3.4. LLM 프롬프트 설계 기본 원칙 (챕터 단위)

* **입력**:

  * 도서/챕터 메타
  * 도서 전체 요약
  * 압축된 페이지-level 요약/엔티티 목록
* **출력**:

  * 도메인별 `*Chapter` 스키마(JSON)
* **주의**:

  * 페이지-level 엔티티 id를 최대한 재사용
  * 새로운 사건/인물/개념을 임의로 만들지 말 것
  * 인사이트는 “요약”이 아니라 “통합된 새로운 문장”을 생성

---

## 4. 품질 관리 및 검증(Validation) 가이드

### 4.1. 기본 검증

1. 필수 필드 존재 여부

   * `page_summary`, `core_message`, `summary_3_5_sentences`, `insights` 등
2. ID 일관성

   * `supporting_evidence_ids`가 실제 `key_events`, `key_examples`, `references`에 존재하는지
3. 페이지 범위 확인

   * `page_range.start ≤ page_number ≤ page_range.end` 여부

### 4.2. 내용 품질 체크 포인트

* 페이지 요약이 **실제 텍스트와 맞는지** 샘플링 검토
* 도메인별 추가 필드가 **해당 분야 특성**을 잘 살렸는지:

  * 역사/사회: 타임라인/지리 구조가 명확한가
  * 경제/경영: 지표/전략/시나리오가 활용 가능하게 정리되었는가
  * 인문/자기계발: 인사이트+실천법이 실제로 “사람이 써먹을 수 있는” 형태인가
  * 과학/기술: 기술/응용/리스크/윤리 포인트가 균형 있게 정리되었는가

---

## 5. 확장/향후 작업 방향

1. **API/서비스화**

   * `POST /books/{id}/chapters/{n}/structure`

     * 입력: 도서 JSON / chapter index
     * 출력: 도메인별 `*Chapter` 구조
2. **UI/툴링**

   * 페이지별/챕터별 구조화 결과를 테이블·카드 형태로 시각화
   * 타임라인/지도/인사이트 카드/체크리스트 등의 뷰 구축
3. **다른 LLM/에이전트에 재사용**

   * 이 구조화 결과를 “도서 전문 지식 베이스”로 삼아:

     * 요약, 비교비평, 기획서, 강의안, 커리큘럼 생성 등에 활용

---

## 6. 한 줄 요약

> **입력 JSON(페이지 텍스트) + 도서 메타(구분/요약)** →
> **페이지 엔티티 추출(도메인별 강화) → 챕터 통합 구조화(인사이트/타임라인/프레임워크 등)**
> 의 2단계 파이프라인을 통해,
> 장문의 도서 텍스트를 재사용 가능한 지식 스키마로 변환한다.


