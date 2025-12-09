# AI 에이전트 운영 가이드

> **환경**: Windows PowerShell 5.1

---

## 🚨 가장 중요: 프로젝트 진행 규칙

### Phase별 진행 원칙

**절대 혼자서 전체 작업을 진행하지 마세요. 반드시 Phase별로 사용자 피드백을 받아서 진행하세요.**

1. **Phase별 진행 필수**
   - 프로젝트 계획 문서에 정의된 Phase 단위로만 작업 진행
   - 한 번에 여러 Phase를 진행하지 않음
   - 각 Phase 완료 후 반드시 사용자에게 보고 및 피드백 요청

2. **작업 전 사용자 확인**
   - Phase 작업을 시작하기 전에 반드시 사용자에게 설명
   - 사용자 승인 후에만 작업 시작
   - 작업 중간에도 중요한 결정사항은 사용자에게 확인

3. **작업 완료 후 피드백 대기**
   - Phase 완료 후 사용자 피드백 대기
   - 다음 Phase 진행은 사용자 명시적 승인 후에만 시작
   - 피드백 없이는 다음 Phase로 진행하지 않음

4. **예외 상황**
   - 사용자가 명시적으로 "모든 Phase를 진행하라"고 요청한 경우에만 전체 진행
   - 그 외의 경우에는 항상 Phase별로 진행

### Phase 진행 템플릿

#### Phase 시작 전
```
## Phase X 시작 준비

**작업 범위**: [Phase 제목]
- [ ] 작업 목록 1
- [ ] 작업 목록 2
- ...

**예상 시간**: [예상 소요 시간]
**의존성**: [이전 Phase 완료 여부]

진행하시겠습니까?
```

#### Phase 완료 후
```
## Phase X 완료

**완료된 작업**:
- [완료된 항목들]

**확인 사항**:
- [사용자가 확인해야 할 것들]

**다음 단계**:
- Phase X+1 진행 준비

피드백 주시면 다음 Phase로 진행하겠습니다.
```

---

## ⚠️ 가장 중요: 사용자 설명 필수 원칙

### 핵심 원칙

**모든 작업 전에 반드시 설명하고, 실행은 사용자 확인 후 진행**

1. **설명 우선, 실행 후순위**
   - 작업 내용을 먼저 설명
   - 사용자 확인 후 실행
   - 실행 결과를 해석하고 다음 단계 제시

2. **단계별 명확한 설명**
   - 무엇을 할 것인지 (What)
   - 왜 하는지 (Why)
   - 어떻게 할 것인지 (How)
   - 예상 결과와 대책 (Result & Action)

3. **Sequential Thinking 활용**
   - 복잡한 문제는 단계별 분석
   - 각 단계의 원인과 해결책 제시
   - 사용자에게 명확한 진단 결과 제공

4. **결과 해석 및 대책 제시**
   - 실행 결과를 정량적으로 설명
   - 문제가 있으면 원인 분석
   - 구체적인 해결 방법 제시
   - 다음 단계 명확히 안내

### 설명 템플릿

#### 작업 전 설명
```
## 작업 내용
- 무엇을 할 것인지 명확히 설명

## 작업 이유
- 왜 이 작업이 필요한지 설명

## 실행 방법
- 어떻게 실행할 것인지 단계별 설명

## 예상 결과
- 성공 시: 어떤 결과가 나올지
- 실패 시: 어떤 문제가 발생할지

## 확인 사항
- 사용자가 확인해야 할 것들
- 실행 전 체크리스트
```

#### 실행 후 설명
```
## 실행 결과
- 실제로 무엇이 실행되었는지
- 결과 파일/로그 위치

## 결과 해석
- 성공/실패 여부
- 문제가 있다면 원인 분석
- 로그/데이터 기반 정량적 설명

## 다음 단계
- 성공 시: 다음 작업
- 실패 시: 해결 방법 및 재시도
- 사용자가 해야 할 일
```

### 금지 사항

❌ **절대 하지 말 것**:
- 설명 없이 바로 실행
- 결과만 보여주고 해석 없음
- 사용자 확인 없이 작업 진행
- 모호한 표현만 사용
- 정량적 근거 없이 결론 제시

✅ **반드시 해야 할 것**:
- 실행 전 상세 설명
- 사용자 확인 요청
- 결과 해석 및 근거 제시
- 구체적인 다음 단계 안내
- 문제 발생 시 원인 분석 및 해결책

### 예시

**❌ 나쁜 예시**: "디버깅 로그를 추가했습니다. 커밋하시겠어요?"

**✅ 좋은 예시**: 작업 내용(What) → 작업 이유(Why) → 실행 방법(How) → 예상 결과 → 확인 사항을 포함한 상세 설명 후 사용자 확인 요청

---

## 1. PowerShell 명령어 표준

### 1.1 명령어 연결

```powershell
# ✅ 세미콜론 사용
cd /path/to/project; python -m pytest tests/

# ❌ Bash && 연산자 사용 금지
```

### 1.2 환경 변수

```powershell
# 설정
$env:PYTHONPATH = "/path/to/project"
$env:API_KEY = "your-api-key"

# 확인
echo $env:API_KEY
Get-ChildItem Env:
```

### 1.3 디렉토리 및 파일

```powershell
New-Item -ItemType Directory -Path "backend\api\models" -Force  # 디렉토리 생성
Get-Content file.txt          # 읽기
Copy-Item src.txt dst.txt     # 복사
Remove-Item file.txt          # 삭제
Test-Path .env                # 존재 확인
```

### 1.4 Python 실행

```powershell
python -m pytest backend/tests/ -v
$env:LOG_LEVEL = "DEBUG"; python script.py
python -c 'print("Hello")'  # 작은따옴표 사용
```

#### ⚠️ 중요: 임시 실행 코드는 항상 스크립트 파일로 작성

**PowerShell 환경 문제**: 한글/특수문자 포함된 Python 코드를 `python -c`로 직접 실행 시 인코딩 및 따옴표 처리 문제 발생

**규칙**: 
- ❌ `python -c "복잡한 코드"` 직접 실행 금지
- ✅ 임시 실행 코드는 항상 스크립트 파일로 작성 후 실행
- ✅ 실행 후 임시 스크립트 파일은 삭제 (단, 테스트용 스크립트는 보존)

**예시**:
```powershell
# ❌ BAD - 직접 실행 (PowerShell 인코딩 문제)
poetry run python -c "from pathlib import Path; print(list(Path('data').glob('*.json')))"

# ✅ GOOD - 스크립트 파일로 작성 후 실행
# 1. 스크립트 파일 작성
# check_files.py 파일 생성
# 2. 실행
poetry run python check_files.py
# 3. 정리
Remove-Item check_files.py
```

#### 모듈 실행 시 경로 문제 해결

**문제**: `python module/submodule/script.py` 실행 시 `ModuleNotFoundError: No module named 'module'` 발생

**해결 방법** (우선순위 순):
```powershell
# 1. -m 옵션 사용 (권장)
poetry run python -m module.submodule.script_name

# 2. PYTHONPATH 설정
$env:PYTHONPATH = "/path/to/project/root"
poetry run python module/submodule/script.py
```

**권장**: 항상 `python -m` 형식 사용

### 1.5 서버 실행

**중요**: 모든 서버는 프로젝트 루트에서 실행. `cd` 사용 금지.

```powershell
# 백엔드 (FastAPI 등)
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 프론트엔드 (Next.js 등)
npm --prefix frontend run dev
```

**주의**: ❌ `cd subdirectory; poetry run uvicorn...` → `ModuleNotFoundError` 발생

### 1.6 출력 제한

```powershell
git diff file.py | Select-Object -First 50  # head 대체
git log | Select-Object -Last 20            # tail 대체
git status | Select-String "modified"        # 필터링
```

### 1.7 인코딩 규칙

**PowerShell은 이모지 미지원 → 텍스트 사용**

**문제**: `UnicodeEncodeError: 'cp949' codec can't encode character`

**해결**: Python 코드에서 이모지 제거, `[OK]`, `[PASS]`, `[FAIL]` 같은 태그 사용

#### 1.7.1 한글 파일명/문자열 처리

**문제**: 한글 파일명 또는 문자열이 포함된 명령어 실행 시 실패

```powershell
# ❌ 실패
python -c "from pypdf import PdfReader; reader = PdfReader(r'data\input\1등의 통찰.pdf')"
Select-String -Pattern "CACHE_SAVE|서버 로그|파싱 완료"
```

**해결**:
```powershell
# ✅ Python 스크립트 파일 사용 (권장)
poetry run python script.py

# ✅ 세션 시작 시 인코딩 설정
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001

# ✅ Select-String은 영문 패턴 사용
Select-String -Pattern "CACHE_SAVE|server|parsing"
```

#### 1.7.2 Tee-Object 인코딩 파라미터

**문제**: PowerShell 5.1에서 `Tee-Object -Encoding` 미지원

```powershell
# ❌ 실패
Tee-Object -FilePath "output.log" -Encoding UTF8
```

**해결**:
```powershell
# ✅ Out-File 사용
poetry run pytest ... | Out-File -FilePath "output.log" -Encoding UTF8
```

#### 1.7.3 파일 경로 처리

**문제**: 한글 파일명 경로에서 변수 할당 실패

**해결**:
```powershell
# ✅ 절대 경로 사용
$pdfPath = (Resolve-Path "data\input\1등의 통찰.pdf").Path

# ✅ 파일 존재 확인 후 처리
$file = Get-ChildItem "path" | Select-Object -First 1
if ($file) { Get-Content $file.FullName -Raw -Encoding UTF8 }
```

---

### 1.8 실행 경로 규칙 (중요)

- 모든 명령은 프로젝트 루트 기준으로 실행
- 세션 중 `cd` 사용 금지 (경로 중첩 오류 방지)

---

### 1.9 답변 가이드라인 (친절 모드)

**⚠️ 중요: 위의 "사용자 설명 필수 원칙"을 먼저 참고하세요.**

- 기본 형식: 요약(결론) → 근거(파일/라인/결과) → 다음 액션
- 정량적 근거 필수 (결과 파일/로그 경로와 핵심 필드 인용)
- 주소/설정 문제와 데이터/시그널 문제 구분
- 실행 전 설명 및 사용자 확인 필수
- 실행 후 결과 해석 및 다음 단계 제시

---

## 2. 터미널 문제 해결

### 2.1 프로세스 강제 종료

```powershell
taskkill /F /IM node.exe
taskkill /F /IM python.exe
# 또는
Stop-Process -Name "node" -Force
```

### 2.2 포트 점유 확인 및 종료

```powershell
netstat -ano | findstr :3000  # 포트 확인
taskkill /F /PID [PID번호]    # PID로 종료
```

### 2.3 프로세스 모니터링

```powershell
Get-Process | Where-Object {$_.ProcessName -eq "node"}
Get-Process | Where-Object {$_.ProcessName -eq "python"}
```

---

## 3. 환경변수 파일 관리

### 3.1 핵심 문제

**.env 파일이 숨김 속성 → AI 도구가 인식 못함**

### 3.2 파일 확인 표준 (우선순위 순)

```powershell
Get-ChildItem -Name "*.env*" -Force  # 1. -Force 옵션 (최우선)
Get-Content .env                      # 2. 파일 내용 확인
Test-Path .env                       # 3. 파일 존재 확인
```

**주의**: ❌ `dir *.env*`, `glob_file_search(".env*")` → 숨김 파일 미포함

### 3.3 파일 위치

- `.env`: 백엔드/프로젝트 루트
- `frontend/.env.local`: 프론트엔드 (Next.js 등)

### 3.4 환경변수 검증

```powershell
echo $env:OPENAI_API_KEY
Get-ChildItem Env:
```

```python
import os
from dotenv import load_dotenv
load_dotenv()
print(f"API_KEY: {os.getenv('API_KEY')}")
```

### 3.5 Next.js 환경변수 규칙

- 클라이언트 사이드: `NEXT_PUBLIC_` 접두사 필수
- 서버 사이드: 접두사 없음

---

## 4. Poetry 패키지 관리

### 4.1 버전 요구사항

**Poetry 1.8.5 이상 필수** (최신 패키지의 PEP 621 메타데이터 버전 2.4 지원)

```powershell
# 버전 확인 및 업데이트
poetry --version
pip install --upgrade poetry>=1.8.5
```

### 4.2 주요 오류: "Unknown metadata version: 2.4"

**원인**: Poetry 1.8.4 이하는 메타데이터 버전 2.4 미지원  
**해결**: Poetry 1.8.5 이상으로 업데이트

```powershell
pip uninstall poetry -y
pip install poetry>=1.8.5
poetry lock
poetry install
```

### 4.3 프로젝트 초기 설정

```powershell
poetry --version  # 1.8.5 이상 확인
poetry lock       # lock 파일 생성
poetry install    # 패키지 설치
```

### 4.4 대안: requirements.txt

Poetry 문제 시: `python -m venv venv; .\venv\Scripts\Activate.ps1; pip install -r requirements.txt`

---

## 5. Git 버전 관리

### 5.1 ⚠️ 중요: Git 업데이트 필수

**Git 업데이트 및 실행을 안하는 경우가 있으니, 반드시 주의할 것**

1. **작업 완료 후 반드시 커밋**
   - 각 작업 단위 완료 시 변경사항을 커밋
   - 작업 전 `git status`로 변경사항 확인
   - 작업 후 `git add`, `git commit` 실행

2. **정기적인 커밋 습관**
   - 기능 단위별로 커밋 (작은 커밋 권장)
   - 의미 있는 커밋 메시지 작성
   - 작업 전에 반드시 `git status` 확인

3. **원격 저장소 동기화**
   - 작업 전 `git pull` 실행 (원격 변경사항 확인)
   - 작업 후 `git push` 실행 (원격 저장소 업데이트)
   - 충돌 발생 시 즉시 해결

### 5.2 원격 저장소 설정

```powershell
# 원격 저장소 확인
git remote -v

# 원격 저장소 설정 (최초 1회, 예시)
git remote add origin https://github.com/username/repository.git

# 원격 저장소 변경사항 가져오기
git pull origin main

# 로컬 변경사항 푸시
git push origin main
```

### 5.3 Git 기본 워크플로우

**작업 시작 전**:
```powershell
# 1. 현재 상태 확인
git status

# 2. 원격 저장소 변경사항 가져오기
git pull origin main

# 3. 브랜치 확인 (필요시)
git branch
```

**작업 중**:
```powershell
# 변경사항 확인
git status
git diff

# 특정 파일만 확인
git diff path/to/file.py
```

**작업 완료 후**:
```powershell
# 1. 변경사항 스테이징
git add .

# 또는 특정 파일만
git add path/to/file.py

# 2. 커밋 (의미 있는 메시지 작성)
git commit -m "feat: 프로젝트 기초 및 환경 설정 완료"

# 3. 원격 저장소에 푸시
git push origin main
```

### 5.4 커밋 메시지 규칙

**형식**: `타입: 작업 내용 (선택: 상세 설명)`

**타입 예시**: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`

**예시**:
```powershell
git commit -m "feat: 프로젝트 초기화 및 기본 구조 생성"
git commit -m "feat: API 클라이언트 구현 (재시도 로직 포함)"
git commit -m "fix: 모듈 import 오류 수정"
git commit -m "test: E2E 테스트 추가 (실제 데이터 사용)"
git commit -m "docs: API 문서 업데이트"
```

**참고**: 프로젝트별 커밋 메시지 규칙이 있으면 해당 규칙 따르기

### 5.5 Git 명령어 (PowerShell 환경)

**⚠️ Git status 멈춤 문제 대안**:
- `git status` 명령어가 터미널에서 멈출 경우, 대신 `git status --short` 사용
- 간략한 출력으로 빠르게 상태 확인 가능

```powershell
# 상태 확인
git status

# 변경사항 확인 (간략) - 멈춤 문제 시 대안
git status --short

# 변경사항 확인 (상세)
git diff

# 변경사항 확인 (특정 파일)
git diff path/to/file.py

# 커밋 로그 확인
git log --oneline -10

# 브랜치 목록
git branch

# 원격 저장소 정보
git remote -v

# 원격 변경사항 가져오기
git pull origin main

# 로컬 변경사항 푸시
git push origin main

# 마지막 커밋 수정 (아직 푸시하지 않은 경우)
git commit --amend -m "수정된 커밋 메시지"
```

### 5.6 충돌 해결

**Pull 시 충돌 발생**:
```powershell
# 1. 충돌 파일 확인
git status

# 2. 충돌 파일 열어서 수정
# <<<<<<< HEAD
# 로컬 변경사항
# =======
# 원격 변경사항
# >>>>>>> origin/main

# 3. 충돌 해결 후
git add .
git commit -m "Merge conflict resolved"
git push origin main
```

### 5.7 .gitignore 확인

**중요 파일은 .gitignore에 포함**:
- `.env`, `.env.local` (환경변수 파일)
- `*.db`, `*.sqlite`, `*.sqlite3` (데이터베이스 파일)
- `poetry.lock` (선택적, 프로젝트 정책에 따라)
- `node_modules/` (Node.js 의존성)
- `__pycache__/`, `*.pyc` (Python 캐시)
- `venv/`, `env/` (가상환경)
- `cache/`, `temp/` (캐시/임시 디렉토리)

```powershell
# .gitignore 확인
Get-Content .gitignore

# 추적 중인 파일 중 .gitignore에 포함된 파일 확인
git ls-files | Select-String "\.env"
```

---

## 6. 테스트 환경 설정

### 6.1 E2E 테스트: 실제 서버 실행 필수

**원칙**: 모든 테스트는 E2E 테스트만 사용하며, 실제 서버를 띄워서 프로덕션 플로우와 동일하게 검증

**구현 방법**:
- `conftest_e2e.py`에 `test_server` fixture로 실제 uvicorn 서버 실행
- `httpx.Client`로 실제 HTTP 요청
- `TestClient` 사용 금지 (백그라운드 작업이 제대로 실행되지 않음)
- 실제 데이터만 사용 (Mock 사용 절대 금지)

**⚠️ 중요: DB 직접 조회 금지**:
- 서버는 실제 파일 데이터베이스 사용 (프로덕션 DB)
- 테스트는 메모리 데이터베이스 (`:memory:`) 사용
- **서로 다른 DB이므로 테스트에서 DB 직접 조회 시 데이터를 찾을 수 없음**
- **해결**: API 응답만 검증 (프로덕션 플로우와 동일)

**참고**: 프로덕션 플로우와 동일하게 검증하여 배포 후 문제가 없음을 보장

### 6.2 테스트 후 자동 보고 (필수)

**⚠️ 중요: 테스트 실행 후 반드시 자동으로 상세 보고**

1. **자동 보고 원칙**
   - 테스트 실행 후 사용자 질문 없이도 자동으로 상세 보고
   - 로그 기반 분석 우선 (이미 실행된 결과가 있으면 재실행하지 않고 분석)
   - 정량적 데이터 제시 및 문제 발견 시 원인 분석 포함

2. **금지 사항**
   - ❌ 테스트 실행 후 결과만 보여주고 분석 없음
   - ❌ 사용자가 물어봐야만 보고
   - ❌ 이미 실행된 결과가 있는데 불필요하게 재실행

---

## 체크리스트

### Poetry 프로젝트 시작 전
- [ ] `poetry --version` 확인 (1.8.5 이상 필수)
- [ ] `poetry lock` 성공 확인
- [ ] `poetry install` 완료 확인

### 서버 실행 전
- [ ] `Get-Content .env` 로 파일 확인
- [ ] 환경변수 확인 (예: `echo $env:API_KEY`)
- [ ] `$env:PYTHONPATH` 설정 (필요시)
- [ ] 포트 충돌 확인 (예: `netstat -ano | findstr :8000`)

### 코드 작성 시
- [ ] 이모지 사용 금지 → `[OK]`, `[PASS]`, `[FAIL]` 사용
- [ ] 명령어 연결은 세미콜론(`;`) 사용
- [ ] 환경변수는 PowerShell 명령어로 확인

### 작업 전/후 (Git 필수)
- [ ] **작업 시작 전**: `git status` 확인 → `git pull origin main` 실행 (또는 해당 브랜치)
- [ ] **작업 완료 후**: `git add .` → `git commit -m "타입: 작업 내용"` → `git push origin main`
- [ ] 커밋 메시지는 의미 있게 작성 (프로젝트별 규칙 따르기)
- [ ] 충돌 발생 시 즉시 해결
