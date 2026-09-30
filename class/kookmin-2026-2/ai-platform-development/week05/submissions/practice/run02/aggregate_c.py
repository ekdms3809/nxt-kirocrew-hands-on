"""창고 C 집계 작업 (독립 노드).

practice/data/warehouse-c.md 를 파싱해 창고 C의 합계와 품목별 수량을
계산하고 submissions/practice/run02/warehouse-c-agg.json 중간 파일에 저장한다.
창고 A·B 작업에 의존하지 않는 병렬 가능 노드다.
"""
from __future__ import annotations

import json
from pathlib import Path

from warehouse_parser import parse_warehouse

WAREHOUSE_ID = "warehouse-c"
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[2]
INPUT_PATH = PROJECT_ROOT / "practice" / "data" / "warehouse-c.md"
OUTPUT_PATH = BASE_DIR / "warehouse-c-agg.json"


def aggregate() -> dict:
    items, total = parse_warehouse(INPUT_PATH)
    result = {
        "warehouse": WAREHOUSE_ID,
        "items": items,
        "total": total,
    }
    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


if __name__ == "__main__":
    agg = aggregate()
    print(f"[{WAREHOUSE_ID}] total = {agg['total']}")
    print(f"[{WAREHOUSE_ID}] items = {agg['items']}")
    print(f"[{WAREHOUSE_ID}] wrote {OUTPUT_PATH}")
