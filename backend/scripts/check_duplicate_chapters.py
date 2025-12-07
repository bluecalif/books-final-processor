"""
챕터 서머리 캐시 중복 확인
"""
import json
from pathlib import Path
from collections import defaultdict

def check_duplicates():
    cache_dir = Path('data/cache/summaries')
    book_dirs = [d for d in cache_dir.iterdir() if d.is_dir() and d.name != "backup"]
    
    for book_dir in book_dirs:
        print(f"\n=== {book_dir.name} ===")
        chapter_groups = defaultdict(list)
        chapter_files = list(book_dir.glob("chapter_*.json"))
        
        for f in chapter_files:
            try:
                data = json.load(open(f, 'r', encoding='utf-8'))
                chapter_num = data.get('chapter_number')
                chapter_title = data.get('chapter_title')
                
                if chapter_num and chapter_title:
                    key = f"{chapter_num}_{chapter_title}"
                    chapter_groups[key].append({
                        "file": f.name,
                        "cached_at": data.get("cached_at", 0),
                        "page_count": data.get("page_count"),
                    })
            except Exception as e:
                print(f"  ERROR reading {f.name}: {e}")
        
        # 중복 확인
        duplicates = {k: v for k, v in chapter_groups.items() if len(v) > 1}
        if duplicates:
            print(f"  중복 발견: {len(duplicates)}개 그룹")
            for key, files in duplicates.items():
                print(f"    {key}: {len(files)}개 파일")
                for f_info in files:
                    print(f"      - {f_info['file']} (cached_at={f_info['cached_at']}, page_count={f_info['page_count']})")
        else:
            print(f"  중복 없음 (총 {len(chapter_groups)}개 챕터)")

if __name__ == "__main__":
    check_duplicates()

