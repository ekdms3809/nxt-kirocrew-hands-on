"""창고 A 집계 작업 (독립 노드).

warehouse_parser로 practice/data/warehouse-a.md를 파싱해
창고 A의 합계와 품목별 수량을 계산하고,
submissions/practice/run02/warehouse-a-agg.json 중간 파일에
{"warehouse": "A", "total": ..., "items": {품목: 수량}} 형태로 저장한다.

창고 B·C 작업에 의존하지 않는 병렬 가능 노드다.
"""
from __future__ import annotations

import json
from pathlib import Path

from warehouse_parser import parse_warehouse

WAREHOUSE = "A"
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[2]  # .../plan_plan_1790734179442467000
INPUT_FILE = PROJECT_ROOT / "practice" / "data" / "warehouse-a.md"
OUTPUT_FILE = BASE_DIR / "warehouse-a-agg.json"


def aggregate() -> dict:
    """창고 A를 파싱해 집계 결과 딕셔너리를 반환하고 중간 파일에 저장한다."""
    items, total = parse_warehouse(INPUT_FILE)
    result = {
        "warehouse": WAREHOUSE,
        "total": total,
        "items": items,
    }
    OUTPUT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


if __name__ == "__main__":
    agg = aggregate()
    print(f"[warehouse {WAREHOUSE}] total={agg['total']} items={agg['items']}")
    print(f"saved -> {OUTPUT_FILE}")
