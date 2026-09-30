"""창고 재고 파서 및 계산 모듈.

warehouse-x.md 파일을 읽어 창고별 행(warehouse row)을 파싱하고,
창고 합계 / 품목별 수량 / 저재고 목록(행 수량 < 5)을 계산한다.

저재고 판정 기준(low_stock_basis)은 "warehouse_row"로 고정한다:
개별 창고에 기록된 행(row)의 수량이 5 미만이면 저재고로 판정한다.
"""

from __future__ import annotations

import json
import os
import re

# 저재고 판정 임계값 및 근거 라벨
LOW_STOCK_THRESHOLD = 5
LOW_STOCK_BASIS = "warehouse_row"

# 입력 데이터 디렉터리 (이 모듈 기준 상대 경로 → practice/data)
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(
    os.path.join(_THIS_DIR, "..", "..", "..", "practice", "data")
)

# 창고별 중간 파일이 저장되는 디렉터리 (이 모듈이 위치한 run01/)
RUN01_DIR = _THIS_DIR


def warehouse_json_path(warehouse_id: str) -> str:
    """창고 id(예: 'warehouse-a')에 대응하는 중간 파일 절대경로를 반환한다."""
    return os.path.join(RUN01_DIR, f"{warehouse_id}.json")


def warehouse_md_path(warehouse_id: str) -> str:
    """창고 id(예: 'warehouse-a')에 대응하는 md 파일 절대경로를 반환한다."""
    return os.path.join(DATA_DIR, f"{warehouse_id}.md")


def parse_warehouse_rows(text: str) -> list[dict]:
    """창고 md 텍스트에서 (품목, 수량) 행 목록을 파싱한다.

    마크다운 표 형식과 `품목: 수량` 리스트 형식을 모두 방어적으로 처리한다.
    헤더 행(품목/수량)과 구분선(---) 행은 무시한다.

    반환: [{"item": str, "quantity": int}, ...]  (원본 행 순서 유지)
    """
    rows: list[dict] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):  # 제목 행
            continue

        item = None
        qty_str = None

        if line.startswith("|"):
            # 마크다운 표 행: | 품목 | 수량 |
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < 2:
                continue
            item, qty_str = cells[0], cells[1]
        elif ":" in line:
            # 리스트 형식: 품목: 수량  (선행 '-' 허용)
            candidate = line.lstrip("-* \t")
            item, qty_str = candidate.split(":", 1)
            item, qty_str = item.strip(), qty_str.strip()
        else:
            continue

        # 헤더 행 / 구분선 행 무시
        if item in ("품목", "item", "Item"):
            continue
        if set(qty_str) <= set("-: ") or set(item) <= set("-: "):
            continue

        m = re.search(r"-?\d+", qty_str)
        if not m:
            continue

        rows.append({"item": item, "quantity": int(m.group())})

    return rows


def read_warehouse(warehouse_id: str) -> list[dict]:
    """창고 md 파일을 읽어 행 목록을 반환한다."""
    path = warehouse_md_path(warehouse_id)
    with open(path, encoding="utf-8") as f:
        return parse_warehouse_rows(f.read())


def warehouse_total(rows: list[dict]) -> int:
    """창고 합계: 모든 행 수량의 합."""
    return sum(r["quantity"] for r in rows)


def item_quantities(rows: list[dict]) -> dict[str, int]:
    """품목별 수량: 같은 품목이 여러 행에 나오면 합산한다."""
    result: dict[str, int] = {}
    for r in rows:
        result[r["item"]] = result.get(r["item"], 0) + r["quantity"]
    return result


def low_stock_rows(warehouse_id: str, rows: list[dict]) -> list[dict]:
    """저재고 목록: 행 수량 < LOW_STOCK_THRESHOLD 인 항목.

    판정은 창고별 행(warehouse_row) 단위로 수행한다.
    각 원소: {"warehouse": id, "item": 품목, "quantity": 수량}
    """
    return [
        {"warehouse": warehouse_id, "item": r["item"], "quantity": r["quantity"]}
        for r in rows
        if r["quantity"] < LOW_STOCK_THRESHOLD
    ]


def compute_warehouse(warehouse_id: str, rows: list[dict] | None = None) -> dict:
    """단일 창고의 합계·품목별 수량·저재고 목록을 계산한 dict를 반환한다."""
    if rows is None:
        rows = read_warehouse(warehouse_id)
    return {
        "warehouse": warehouse_id,
        "total": warehouse_total(rows),
        "item_quantities": item_quantities(rows),
        "low_stock": low_stock_rows(warehouse_id, rows),
        "low_stock_basis": LOW_STOCK_BASIS,
    }


def process_warehouse(warehouse_id: str) -> dict:
    """단일 창고 집계 노드.

    지정된 창고 md를 읽어 합계·품목별 수량·저재고 목록을 계산하고,
    그 결과를 창고별 중간 파일 RUN01_DIR/warehouse-<id>.json 에 저장한다.

    A·B·C 각 창고에 대해 서로 의존 없이 독립적으로 호출할 수 있으며,
    계산 결과 dict를 반환한다(중간 파일에 기록된 내용과 동일).
    """
    summary = compute_warehouse(warehouse_id)

    os.makedirs(RUN01_DIR, exist_ok=True)
    out_path = warehouse_json_path(warehouse_id)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return summary


def read_warehouse_summary(warehouse_id: str) -> dict:
    """창고별 중간 파일(warehouse-<id>.json)을 읽어 요약 dict를 반환한다."""
    path = warehouse_json_path(warehouse_id)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def aggregate(warehouse_ids: tuple[str, ...] = ("warehouse-a", "warehouse-b", "warehouse-c")) -> dict:
    """통합 작업 노드.

    세 창고의 중간 파일(warehouse-a.json, warehouse-b.json, warehouse-c.json)을 읽어
    창고별 합계, 품목별 총수량, 저재고 목록을 통합 산출한다.

    반환 dict는 practice/출력형식.md 구조를 따른다:
      - warehouse_totals: {창고 id: 합계}
      - item_totals: {품목: 전체 창고 총수량}
      - low_stock: [{warehouse, item, quantity}, ...]  (행 수량 < 5)
      - low_stock_basis: "warehouse_row"
      - grand_total: 전체 창고 총합
    """
    summaries = {wid: read_warehouse_summary(wid) for wid in warehouse_ids}

    warehouse_totals: dict[str, int] = {}
    item_totals: dict[str, int] = {}
    low_stock: list[dict] = []

    for wid in warehouse_ids:
        summary = summaries[wid]
        # 창고별 합계
        warehouse_totals[wid] = summary["total"]
        # 품목별 총수량 (전체 창고 합산)
        for item, qty in summary["item_quantities"].items():
            item_totals[item] = item_totals.get(item, 0) + qty
        # 저재고 목록 통합 (창고별 행 기준)
        low_stock.extend(summary["low_stock"])

    grand_total = sum(warehouse_totals.values())
    source_files = [f"{wid}.md" for wid in warehouse_ids]

    # practice/출력형식.md 구조 및 필드 순서를 따른다.
    return {
        "source_files": source_files,
        "warehouse_totals": warehouse_totals,
        "item_totals": item_totals,
        "grand_total": grand_total,
        "low_stock_basis": LOW_STOCK_BASIS,
        "threshold": LOW_STOCK_THRESHOLD,
        "low_stock": low_stock,
    }


if __name__ == "__main__":
    # 간단한 자체 점검용 실행
    for wid in ("warehouse-a", "warehouse-b", "warehouse-c"):
        result = process_warehouse(wid)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    print("=== aggregate ===")
    print(json.dumps(aggregate(), ensure_ascii=False, indent=2))
