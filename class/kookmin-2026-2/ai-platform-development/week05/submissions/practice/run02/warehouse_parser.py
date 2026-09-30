"""창고 마크다운 파서 모듈.

창고 재고 마크다운 파일(표 또는 목록 형식)을 읽어
품목명 -> 수량 딕셔너리와 창고 합계를 반환한다.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Tuple


def _extract_pairs(text: str) -> Dict[str, int]:
    """마크다운 텍스트에서 (품목명 -> 정수 수량) 쌍을 추출한다.

    지원 형식:
    - 표: ``| 품목 | 수량 |`` 형태의 행
    - 목록: ``- 사과: 12`` / ``* 사과 12`` 형태의 행
    """
    items: Dict[str, int] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        name: str | None = None
        qty: int | None = None

        # 1) 마크다운 표 행: | 품목 | 수량 |
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < 2:
                continue
            candidate_name = cells[0]
            candidate_qty = cells[-1]
            # 헤더행/구분행 건너뛰기
            if not candidate_name or set(candidate_name) <= set("-: "):
                continue
            if not re.fullmatch(r"-?\d+", candidate_qty):
                # 헤더('수량') 등 숫자가 아니면 스킵
                continue
            name = candidate_name
            qty = int(candidate_qty)
        else:
            # 2) 목록 형식: "- 사과: 12", "* 사과 12", "사과 : 12"
            m = re.match(r"^[-*+]?\s*(.+?)\s*[:\t]\s*(-?\d+)\s*$", line)
            if not m:
                m = re.match(r"^[-*+]?\s*(.+?)\s+(-?\d+)\s*$", line)
            if not m:
                continue
            name = m.group(1).strip()
            qty = int(m.group(2))

        if name is None or qty is None:
            continue
        # 동일 품목이 여러 번 나오면 합산
        items[name] = items.get(name, 0) + qty

    return items


def parse_warehouse(path: str | Path) -> Tuple[Dict[str, int], int]:
    """창고 마크다운 파일을 파싱한다.

    Args:
        path: 창고 마크다운 파일 경로.

    Returns:
        (items, total) 튜플.
        - items: 품목명 -> 수량(int) 딕셔너리
        - total: 창고 전체 수량 합계
    """
    text = Path(path).read_text(encoding="utf-8")
    items = _extract_pairs(text)
    total = sum(items.values())
    return items, total


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else None
    if not target:
        print("usage: python warehouse_parser.py <warehouse.md>")
        raise SystemExit(1)
    parsed_items, parsed_total = parse_warehouse(target)
    print(f"items = {parsed_items}")
    print(f"total = {parsed_total}")
