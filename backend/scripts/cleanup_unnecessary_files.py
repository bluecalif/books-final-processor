"""
불필요한 파일 정리 스크립트

Phase 7.2 시작 전 정리:
- data/test_results/ 오래된 로그 파일 (최신 5개만 유지)
- data/input/처리완료/ 중복 PDF 파일
- backend/scripts/ 임시/테스트용 스크립트 확인
- docs/reference_code/ 참고용 코드 확인
"""
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent


def cleanup_test_results():
    """data/test_results/ 오래된 로그 파일 정리 (최신 5개만 유지)"""
    test_results_dir = PROJECT_ROOT / "data" / "test_results"
    if not test_results_dir.exists():
        logger.info("[INFO] test_results 디렉토리가 없습니다.")
        return
    
    log_files = sorted(
        test_results_dir.glob("*.log"),
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )
    
    if len(log_files) <= 5:
        logger.info(f"[INFO] test_results 로그 파일 {len(log_files)}개 (5개 이하, 정리 불필요)")
        return
    
    # 최신 5개 제외하고 삭제
    files_to_delete = log_files[5:]
    deleted_count = 0
    for file in files_to_delete:
        try:
            file.unlink()
            deleted_count += 1
            logger.info(f"[INFO] 삭제: {file.name}")
        except Exception as e:
            logger.error(f"[ERROR] 삭제 실패: {file.name}, error={e}")
    
    logger.info(f"[INFO] test_results 정리 완료: {deleted_count}개 파일 삭제, {len(log_files) - deleted_count}개 유지")


def cleanup_processed_pdfs():
    """data/input/처리완료/ 중복 PDF 파일 확인"""
    processed_dir = PROJECT_ROOT / "data" / "input" / "처리완료"
    if not processed_dir.exists():
        logger.info("[INFO] 처리완료 디렉토리가 없습니다.")
        return
    
    input_dir = PROJECT_ROOT / "data" / "input"
    processed_files = list(processed_dir.glob("*.pdf"))
    
    if not processed_files:
        logger.info("[INFO] 처리완료 디렉토리에 PDF 파일이 없습니다.")
        return
    
    # input 디렉토리의 파일과 비교
    input_files = {f.name for f in input_dir.glob("*.pdf") if f.is_file()}
    
    duplicates = []
    for processed_file in processed_files:
        if processed_file.name in input_files:
            duplicates.append(processed_file)
    
    if duplicates:
        logger.info(f"[INFO] 처리완료 디렉토리에서 중복 파일 {len(duplicates)}개 발견:")
        for dup in duplicates:
            logger.info(f"  - {dup.name}")
        logger.info("[INFO] 중복 파일은 수동으로 확인 후 삭제하세요.")
    else:
        logger.info("[INFO] 처리완료 디렉토리에 중복 파일이 없습니다.")


def check_scripts():
    """backend/scripts/ 스크립트 파일 확인"""
    scripts_dir = PROJECT_ROOT / "backend" / "scripts"
    if not scripts_dir.exists():
        logger.info("[INFO] scripts 디렉토리가 없습니다.")
        return
    
    script_files = sorted(scripts_dir.glob("*.py"))
    logger.info(f"[INFO] scripts 디렉토리: {len(script_files)}개 Python 파일")
    
    # 임시/테스트용 스크립트 확인 (이름 패턴 기반)
    temp_patterns = ["test_", "temp_", "tmp_", "_test", "_temp", "_tmp"]
    temp_scripts = []
    
    for script in script_files:
        name = script.stem.lower()
        if any(pattern in name for pattern in temp_patterns):
            temp_scripts.append(script)
    
    if temp_scripts:
        logger.info(f"[INFO] 임시/테스트용으로 보이는 스크립트 {len(temp_scripts)}개:")
        for script in temp_scripts:
            logger.info(f"  - {script.name}")
        logger.info("[INFO] 임시 스크립트는 수동으로 확인 후 삭제하세요.")
    else:
        logger.info("[INFO] 임시/테스트용 스크립트가 없습니다.")


def check_reference_code():
    """docs/reference_code/ 참고용 코드 확인"""
    ref_dir = PROJECT_ROOT / "docs" / "reference_code"
    if not ref_dir.exists():
        logger.info("[INFO] reference_code 디렉토리가 없습니다.")
        return
    
    ref_files = list(ref_dir.rglob("*"))
    logger.info(f"[INFO] reference_code 디렉토리: {len(ref_files)}개 파일/디렉토리")
    logger.info("[INFO] 참고용 코드는 유지하세요.")


def main():
    """메인 함수"""
    logger.info("[INFO] 불필요한 파일 정리 시작")
    logger.info("=" * 60)
    
    cleanup_test_results()
    logger.info("-" * 60)
    
    cleanup_processed_pdfs()
    logger.info("-" * 60)
    
    check_scripts()
    logger.info("-" * 60)
    
    check_reference_code()
    logger.info("=" * 60)
    logger.info("[INFO] 불필요한 파일 정리 완료")


if __name__ == "__main__":
    main()

