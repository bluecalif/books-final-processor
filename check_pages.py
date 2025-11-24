"""pypdf와 Upstage API 인식 페이지 수 비교"""
import json
from pathlib import Path
from pypdf import PdfReader

# pypdf로 페이지 수 확인
pdf_path = Path(r"data/input/1등의 통찰.pdf")
reader = PdfReader(str(pdf_path))
pypdf_pages = len(reader.pages)
print(f"pypdf로 읽은 페이지 수: {pypdf_pages}")

# 캐시 파일에서 Upstage API 인식 페이지 수 확인
cache_dir = Path("data/cache/upstage")
cache_files = list(cache_dir.glob("*.json"))
if cache_files:
    latest = max(cache_files, key=lambda p: p.stat().st_mtime)
    with open(latest, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    api_pages = data.get("usage", {}).get("pages", 0)
    split_parsing = data.get("metadata", {}).get("split_parsing", False)
    total_chunks = data.get("metadata", {}).get("total_chunks", 1)
    
    print(f"\n캐시 파일: {latest.name}")
    print(f"Upstage API 인식 페이지 수: {api_pages}")
    print(f"분할 파싱: {split_parsing}")
    print(f"총 청크: {total_chunks}")
    print(f"\n비율: {api_pages / pypdf_pages:.2f}배")
else:
    print("\n캐시 파일 없음")

