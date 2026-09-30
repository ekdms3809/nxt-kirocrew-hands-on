"""창고 A·B·C 재고 집계 DAG 오케스트레이션.

DAG 의존 구조:

    process(warehouse-a) ─┐
    process(warehouse-b) ─┼─▶ aggregate()
    process(warehouse-c) ─┘

- 세 창고 집계 노드(process_warehouse)는 서로 의존하지 않는 독립 노드로,
  concurrent.futures.ThreadPoolExecutor로 병렬 실행한다.
- 통합 노드(aggregate)는 세 창고 노드가 "모두" 완료된 뒤에만 실행되도록
  의존 관계를 명시적으로 구성한다.

이 스크립트는 오케스트레이션(노드 실행 순서/병렬성)을 담당한다.
개별 계산 로직은 inventory.py의 process_warehouse / aggregate에 위임한다.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import inventory

# DAG의 독립 창고 노드 정의 (서로 의존 없음)
WAREHOUSE_NODES: tuple[str, ...] = ("warehouse-a", "warehouse-b", "warehouse-c")

# 최종 산출물 저장 경로 (이 스크립트가 위치한 run01/)
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
RESULT_JSON_PATH = os.path.join(_THIS_DIR, "result.json")
REPORT_MD_PATH = os.path.join(_THIS_DIR, "report.md")


def run_warehouse_nodes(
    warehouse_ids: tuple[str, ...] = WAREHOUSE_NODES,
) -> dict[str, dict]:
    """세 창고 집계 노드를 병렬 실행한다.

    각 노드는 inventory.process_warehouse(wid)를 호출하여 창고별 중간 파일을
    생성하고 요약 dict를 반환한다. 노드 간 의존이 없으므로 동시에 실행한다.

    반환: {warehouse_id: summary_dict}  (모든 노드 완료 후)
    """
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=len(warehouse_ids)) as executor:
        future_to_wid = {
            executor.submit(inventory.process_warehouse, wid): wid
            for wid in warehouse_ids
        }
        for future in as_completed(future_to_wid):
            wid = future_to_wid[future]
            # 노드에서 예외가 발생하면 여기서 전파되어 DAG가 실패한다.
            results[wid] = future.result()
    return results


def run_aggregate_node(
    warehouse_ids: tuple[str, ...] = WAREHOUSE_NODES,
) -> dict:
    """통합 노드: 세 창고 중간 파일을 읽어 통합 결과를 산출한다.

    반드시 run_warehouse_nodes()가 모든 창고 노드를 완료한 뒤 호출해야 한다.
    """
    return inventory.aggregate(warehouse_ids)


def write_result_json(aggregated: dict, path: str = RESULT_JSON_PATH) -> str:
    """통합 결과를 출력형식.md 구조의 result.json으로 저장한다.

    low_stock_basis 값은 aggregate()가 채운 "warehouse_row"를 그대로 유지한다.
    반환: 기록한 파일 경로.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(aggregated, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return path


def render_report_md(aggregated: dict) -> str:
    """통합 결과를 사람이 읽을 수 있는 report.md 문자열로 렌더링한다.

    창고별 합계 / 품목별 총수량 / 저재고 목록을 표·목록으로 정리한다.
    """
    warehouse_totals: dict[str, int] = aggregated["warehouse_totals"]
    item_totals: dict[str, int] = aggregated["item_totals"]
    low_stock: list[dict] = aggregated["low_stock"]
    basis = aggregated.get("low_stock_basis", inventory.LOW_STOCK_BASIS)
    grand_total = aggregated.get("grand_total", sum(warehouse_totals.values()))

    lines: list[str] = []
    lines.append("# 창고 A·B·C 재고 집계 보고서")
    lines.append("")
    lines.append(
        f"- 저재고 판정 기준: 창고별 행(warehouse row) 수량 "
        f"< {inventory.LOW_STOCK_THRESHOLD} (`low_stock_basis = {basis}`)"
    )
    lines.append(f"- 전체 총합(grand_total): **{grand_total}**")
    lines.append("")

    # 창고별 합계
    lines.append("## 창고별 합계")
    lines.append("")
    lines.append("| 창고 | 합계 |")
    lines.append("| --- | ---: |")
    for wid, total in warehouse_totals.items():
        lines.append(f"| {wid} | {total} |")
    lines.append(f"| **합계** | **{grand_total}** |")
    lines.append("")

    # 품목별 총수량
    lines.append("## 품목별 총수량")
    lines.append("")
    lines.append("| 품목 | 총수량 |")
    lines.append("| --- | ---: |")
    for item, qty in item_totals.items():
        lines.append(f"| {item} | {qty} |")
    lines.append("")

    # 저재고 목록
    lines.append("## 저재고 목록")
    lines.append("")
    if low_stock:
        lines.append("| 창고 | 품목 | 수량 |")
        lines.append("| --- | --- | ---: |")
        for row in low_stock:
            lines.append(
                f"| {row['warehouse']} | {row['item']} | {row['quantity']} |"
            )
    else:
        lines.append("- (저재고 항목 없음)")
    lines.append("")

    return "\n".join(lines)


def write_report_md(aggregated: dict, path: str = REPORT_MD_PATH) -> str:
    """통합 결과를 report.md로 저장한다. 반환: 기록한 파일 경로."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_report_md(aggregated))
    return path


def write_outputs(aggregated: dict) -> dict[str, str]:
    """통합 결과를 result.json과 report.md로 함께 기록한다.

    반환: {"result_json": 경로, "report_md": 경로}
    """
    return {
        "result_json": write_result_json(aggregated),
        "report_md": write_report_md(aggregated),
    }


def run_dag(warehouse_ids: tuple[str, ...] = WAREHOUSE_NODES) -> dict:
    """DAG 전체를 실행한다.

    1) 창고 A·B·C 노드를 병렬 실행(독립 노드) → 각 중간 파일 생성
    2) 세 노드가 모두 완료된 후 통합 노드 실행

    반환: aggregate() 통합 결과 dict.
    """
    # --- 단계 1: 독립 창고 노드 병렬 실행 ---
    warehouse_results = run_warehouse_nodes(warehouse_ids)

    # 명시적 의존 게이트: 세 노드 결과가 모두 존재해야 통합 단계로 진입한다.
    missing = [wid for wid in warehouse_ids if wid not in warehouse_results]
    if missing:
        raise RuntimeError(f"창고 노드 미완료로 통합 단계 진입 불가: {missing}")

    # --- 단계 2: 세 노드 완료 후 통합 노드 실행 ---
    aggregated = run_aggregate_node(warehouse_ids)

    # --- 단계 3: 통합 결과를 result.json / report.md로 기록 ---
    write_outputs(aggregated)
    return aggregated


if __name__ == "__main__":
    result = run_dag()
    print("=== 통합 결과(result.json 내용) ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print()
    print(f"result.json → {RESULT_JSON_PATH}")
    print(f"report.md   → {REPORT_MD_PATH}")
