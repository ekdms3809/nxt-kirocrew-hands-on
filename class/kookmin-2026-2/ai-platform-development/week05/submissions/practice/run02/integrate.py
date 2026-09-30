"""통합·저재고 판정·산출물 생성 작업 (수렴 노드).

세 창고 중간 파일(warehouse-a-agg.json, warehouse-b-agg.json,
warehouse-c-agg.json)을 모두 읽어:
  - 창고별 합계(warehouse_totals)를 모은다.
  - 품목별 총수량(item_totals)을 세 창고 값의 합으로 계산한다.
  - item_total < 5 인 품목을 저재고(low_stock)로 판정한다.
    (low_stock_basis="item_total", threshold=5)
  - 전체 총합(grand_total)을 계산한다.

practice/출력형식.md 형식에 맞춰 result.json 과 report.md 를 생성한다.

DAG상 창고 A·B·C 집계 세 작업 모두에 의존하는 수렴 노드다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

BASE_DIR = Path(__file__).resolve().parent

# 정규화된 창고 id -> 해당 중간 파일 경로.
# 중간 파일들의 "warehouse" 필드 값이 제각각("A", "B", "warehouse-c")이므로
# 파일명 기준의 표준 id를 신뢰원으로 삼는다.
AGG_FILES = {
    "warehouse-a": BASE_DIR / "warehouse-a-agg.json",
    "warehouse-b": BASE_DIR / "warehouse-b-agg.json",
    "warehouse-c": BASE_DIR / "warehouse-c-agg.json",
}

RESULT_FILE = BASE_DIR / "result.json"
REPORT_FILE = BASE_DIR / "report.md"

THRESHOLD = 5
LOW_STOCK_BASIS = "item_total"


def _load_agg(path: Path) -> Dict:
    """중간 집계 파일을 읽어 dict로 반환한다."""
    return json.loads(path.read_text(encoding="utf-8"))


def integrate() -> Dict:
    """세 창고 중간 파일을 통합해 result 딕셔너리를 생성한다."""
    warehouse_totals: Dict[str, int] = {}
    item_totals: Dict[str, int] = {}

    for wh_id, path in AGG_FILES.items():
        agg = _load_agg(path)
        items: Dict[str, int] = agg.get("items", {})
        # 창고 합계: 파일의 total 우선, 없으면 items 합으로 방어적 계산.
        total = agg.get("total")
        if total is None:
            total = sum(items.values())
        warehouse_totals[wh_id] = total

        for name, qty in items.items():
            item_totals[name] = item_totals.get(name, 0) + int(qty)

    # 품목명 정렬로 결정적 출력 보장.
    item_totals = dict(sorted(item_totals.items()))

    # 저재고 판정: 품목별 총수량이 5 미만.
    low_stock = [
        {"item": name, "item_total": qty, "threshold": THRESHOLD}
        for name, qty in item_totals.items()
        if qty < THRESHOLD
    ]

    grand_total = sum(warehouse_totals.values())

    result = {
        "warehouse_totals": warehouse_totals,
        "item_totals": item_totals,
        "low_stock": low_stock,
        "low_stock_basis": LOW_STOCK_BASIS,
        "threshold": THRESHOLD,
        "grand_total": grand_total,
    }
    return result


def _build_report(result: Dict) -> str:
    """result 딕셔너리로 사람이 읽는 report.md 본문을 만든다."""
    wt = result["warehouse_totals"]
    it = result["item_totals"]
    low = result["low_stock"]

    lines = []
    lines.append("# 창고 재고 집계 및 저재고 판정 보고서")
    lines.append("")
    lines.append(
        "practice/data 의 창고 A·B·C 마크다운 파일을 파싱해 창고별 합계와 "
        "품목별 총수량을 집계하고, 품목별 총수량이 5 미만인 저재고 품목을 판정한 결과다."
    )
    lines.append("")

    # 창고별 합계
    lines.append("## 창고별 합계")
    lines.append("")
    lines.append("| 창고 | 합계 |")
    lines.append("| --- | --- |")
    for wh_id, total in wt.items():
        lines.append(f"| {wh_id} | {total} |")
    lines.append(f"| **전체(grand_total)** | **{result['grand_total']}** |")
    lines.append("")

    # 품목별 총수량
    lines.append("## 품목별 총수량")
    lines.append("")
    lines.append("| 품목 | 총수량 |")
    lines.append("| --- | --- |")
    for name, qty in it.items():
        lines.append(f"| {name} | {qty} |")
    lines.append("")

    # 저재고 목록
    lines.append("## 저재고 목록")
    lines.append("")
    lines.append(
        f"판정 기준: 전체 창고 품목별 총수량(`{result['low_stock_basis']}`)이 "
        f"임계값 `{result['threshold']}` 미만(`< {result['threshold']}`)인 품목."
    )
    lines.append("")
    if low:
        lines.append("| 품목 | 총수량 | 임계값 |")
        lines.append("| --- | --- | --- |")
        for row in low:
            lines.append(
                f"| {row['item']} | {row['item_total']} | {row['threshold']} |"
            )
    else:
        lines.append("저재고 품목이 없습니다.")
    lines.append("")

    return "\n".join(lines) + "\n"


def main() -> Dict:
    result = integrate()

    RESULT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    REPORT_FILE.write_text(_build_report(result), encoding="utf-8")
    return result


if __name__ == "__main__":
    res = main()
    print(f"warehouse_totals = {res['warehouse_totals']}")
    print(f"grand_total = {res['grand_total']}")
    print(f"low_stock = {[r['item'] for r in res['low_stock']]}")
    print(f"saved -> {RESULT_FILE}")
    print(f"saved -> {REPORT_FILE}")
