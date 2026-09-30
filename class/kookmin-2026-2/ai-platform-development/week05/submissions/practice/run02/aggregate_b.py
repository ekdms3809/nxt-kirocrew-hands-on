"""창고 B 집계 작업 (독립 노드).

practice/data/warehouse-b.md 를 파싱해 창고 B의 합계와 품목별 수량을
계산하고 submissions/practice/run02/warehouse-b-agg.json 중간 파일에 저장한다.

창고 A·C 집계 작업에 의존하지 않는 병렬 가능 노드다.
"""
from __future__ import annotations

import json
from pathlib import Path

from warehouse_parser import parse_warehouse

# run02/ 기준으로 경로를 해석한다.
RUN_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = RUN_DIR.parents[2]  # .../plan_plan_.../
INPUT_PATH = PROJECT_ROOT / "practice" / "data" / "warehouse-b.md"
OUTPUT_PATH = RUN_DIR / "warehouse-b-agg.json"

WAREHOUSE_ID = "B"


def aggregate() -> dict:
    """창고 B를 파싱해 집계 결과 딕셔너리를 반환한다."""
    items, total = parse_warehouse(INPUT_PATH)
    return {
        "warehouse": WAREHOUSE_ID,
        "source": str(INPUT_PATH),
        "items": items,
        "total": total,
    }


def main() -> None:
    result = aggregate()
    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"[창고 {WAREHOUSE_ID}] items={result['items']} total={result['total']}")
    print(f"저장: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
