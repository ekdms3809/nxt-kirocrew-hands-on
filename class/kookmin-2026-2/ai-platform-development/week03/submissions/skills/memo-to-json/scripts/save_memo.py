#!/usr/bin/env python3
"""메모 정리 결과(JSON)를 검사하고 파일로 저장한다.

사진 판독은 AI가 하고, 이 프로그램은 판독 결과만 검사한다.
스키마를 만족할 때만 저장하며, 위반이 있으면 저장하지 않고 사유를 알린다.

항목(고정):
  - 메모 날짜   : "YYYY-MM-DD" 문자열 또는 null
  - 끝낸 일     : 문자열 목록 (빈 목록은 [])
  - 남은 일     : 문자열 목록
  - 변경한 내용 : 문자열 목록
  - 확인할 질문 : 문자열 목록

사용법:
  python3 save_memo.py <입력.json> [출력.json]
  echo '<json>' | python3 save_memo.py - [출력.json]
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

# 항목 이름과 순서를 고정한다.
DATE_FIELD = "메모 날짜"
LIST_FIELDS = ("끝낸 일", "남은 일", "변경한 내용", "확인할 질문")
FIELD_ORDER = (DATE_FIELD, *LIST_FIELDS)


class ValidationError(Exception):
    """스키마 위반. message에 사람이 읽을 사유 목록을 담는다."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


def _valid_date(value: str) -> bool:
    """YYYY-MM-DD 형식이며 실제 존재하는 날짜인지 검사한다."""
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        return False
    # fromisoformat은 "2026-1-1" 같은 형태도 통과하므로 자리수를 다시 확인한다.
    return len(value) == 10 and value[4] == "-" and value[7] == "-"


def validate(data: object) -> dict:
    """스키마를 검사한다. 통과하면 항목 순서를 고정한 dict를 돌려주고,
    위반이 있으면 ValidationError를 발생시킨다."""
    problems: list[str] = []

    if not isinstance(data, dict):
        raise ValidationError([f"최상위가 객체(JSON object)가 아니라 {type(data).__name__} 입니다."])

    allowed = set(FIELD_ORDER)
    present = set(data.keys())

    for missing in FIELD_ORDER:
        if missing not in present:
            problems.append(f"항목 누락: '{missing}'")
    for extra in sorted(present - allowed):
        problems.append(f"허용되지 않은 항목: '{extra}'")

    # 메모 날짜: 문자열(YYYY-MM-DD) 또는 null
    if DATE_FIELD in data:
        v = data[DATE_FIELD]
        if v is None:
            pass
        elif isinstance(v, str):
            if not _valid_date(v):
                problems.append(f"'{DATE_FIELD}'는 YYYY-MM-DD 형식이어야 합니다: {v!r}")
        else:
            problems.append(f"'{DATE_FIELD}'는 문자열 또는 null이어야 합니다: {type(v).__name__}")

    # 나머지: 문자열 목록
    for field in LIST_FIELDS:
        if field not in data:
            continue
        v = data[field]
        if not isinstance(v, list):
            problems.append(f"'{field}'는 목록(list)이어야 합니다: {type(v).__name__}")
            continue
        for i, item in enumerate(v):
            if not isinstance(item, str):
                problems.append(f"'{field}'[{i}] 는 문자열이어야 합니다: {type(item).__name__}")

    if problems:
        raise ValidationError(problems)

    # 항목 순서를 고정해 정규화한다.
    return {field: data[field] for field in FIELD_ORDER}


def _load(source: str) -> object:
    raw = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValidationError([f"JSON 파싱 실패: {e}"]) from e


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2

    source = argv[1]
    out_path = argv[2] if len(argv) > 2 else "memo.json"

    try:
        data = _load(source)
        cleaned = validate(data)
    except ValidationError as e:
        print("저장하지 않았습니다. 다음을 고쳐 주세요:", file=sys.stderr)
        for p in e.problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    Path(out_path).write_text(
        json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"검사 통과. 저장 완료: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
