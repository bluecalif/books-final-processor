# Cursor 프로젝트 진행 순서 

## 1. 마스터 작업 순서 확인
* **cursor-master-sequence.md 파일** 확인(@/vibe-coding/)

## 2. 프로젝트 기초 준비
* 프로젝트명 기준 폴더 생성 -> 하부 디렉토리 /docs 생성 -> /docs에 PRD 파일 넣기

## 3. 프로젝트 계획 세우기 (이후는 커서 에이전트 창에서 진행)
* PRD 기반으로 한 프로젝트 플래닝을 플랜모드에서 요청
* 커서가 질문을 하는 경우, 이에 대한 답변을 통해 구체화된 내용 반영을 요청
* **필수 패키지**: poetry.lock 및 pyproject.toml로 확인 요청
* **참고 코드 스니펫**: TODOs.md에 반영할 것을 요청 
* 커서가 작성한 플랜은 **/TODOs.md 파일**로 작성을 요청. 1차 작성후 한번더 정제 요청

## 4. 프로젝트 지침 및 컨텍스트 준비
* **AGENTS.md**:  파일 복사 붙이기 (@/vibe-coding/) 파워쉘 명령어. 환경변수 관리. => 반드시 시작시 이것 참고하라고 할 것(특히 사용자 지시 반영후 시작)
* **Cursor rule**: PRD와 TODOs.md를 바탕으로 커서룰 작성을 요청 (명령어: @.cursor/rules)
* **api-contract**:API-Contract의 sync는 매우 중요. 파일 복사한 후(@vibe-coding) 본 프로젝트에 맞게 각색하여 커서룰로 넣기 
* **test세션**: backend-frontend가 별도로 구성된 경우, backend에서 E2E 테스트가 완료되어야 합니다. 이를 위해 각 단계별 sub 테스트가 정합성있게 빠짐없이 되어 있는지 TODOs.md에 반영
* **Git**: 깃 업데이트 및 실행을 안하는 경우가 있으니, 주의할 것
* **supabase**: connection string 확인. transaction pooler에서 ipv4 버전 string 확인

## 5. 프로젝트 작업 개시(주의사항)
* **계획 설정 완료후 => 반드시 새로운 채팅창에서 프로젝트 Phase 시작**
* **실제 데이터**: 테스트시 Mock이 아닌 실제 데이터로 E2E 테스트
* **Supabase 연동**: Phase 마다 supabase와 연동되어 처리 되도록 작성되어야 함. 테스트도 동일하게 진행
* **데이터 Coverage 조기 확인**: 여러 Phase로 나눠진 경우, 첫 Phase에서 가능한 모든 데이터 수집경로(소소, 카테고리등)에 대해서 실행시 문제없는것 확인해야 함. 최소한 검증으로 Phase 번호만 계속 올라가는것은 의미없음. 나중에 문제가 더 커짐.