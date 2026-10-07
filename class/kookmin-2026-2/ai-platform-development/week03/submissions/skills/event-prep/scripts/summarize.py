#!/usr/bin/env python3
"""참가신청 CSV를 행사안내 규칙대로 집계해 JSON으로 저장한다.

판단(불참 제외, 미응답 분리 등)은 사람이 실수하기 쉬우므로 이 프로그램이 규칙대로 계산한다.
CSV 헤더나 값이 규칙에 맞지 않으면 저장하지 않고 사유를 알린다.

CSV 헤더(고정): 신청번호, 이름, 학년, 참가 여부, 간식 선택

집계 규칙:
  - 참가 여부가 '참가'인 사람만 인원에 포함한다. '불참'은 제외한다.
  - 불참자는 간식을 선택했더라도 주문 수량에서 제외한다.
  - 간식은 참가자만 집계한다. '받지 않음'은 주문하지 않는다.
  - 참가자의 간식 선택이 빈칸이면 미응답 -> 확인할_사람에 남긴다.
  - 불참자의 빈칸은 확인하지 않는다.
  - 생수는 참가 인원수만큼 준비한다.
  - 참가 인원이 정원을 넘으면 정원_초과 = True.

사용법:
  python3 summarize.py <입력.csv> [출력.json] [--정원 N] [--행사명 "이름"]
  cat <입력.csv> | python3 summarize.py - [출력.json] [--정원 N] [--행사명 "이름"]
"""
from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

# CSV 헤더(고정)
REQUIRED_HEADER = ["신청번호", "이름", "학년", "참가 여부", "간식 선택"]

# 허용 값
ATTEND_YES = "참가"
ATTEND_NO = "불참"
VALID_ATTEND = {ATTEND_YES, ATTEND_NO}

SNACK_ITEMS = ("샌드위치", "주먹밥")
SNACK_NONE = "받지 않음"
VALID_SNACK = {*SNACK_ITEMS, SNACK_NONE, ""}  # 빈칸("")은 미응답으로 허용

# 출력 항목 순서(고정)
FIELD_ORDER = (
    "행사명",
    "참가_인원",
    "정원",
    "정원_초과",
    "간식_주문",
    "생수",
    "확인할_사람",
    "주문_확정_여부",
)


class ValidationError(Exception):
    """입력 위반. problems에 사람이 읽을 사유 목록을 담는다."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


def _read_rows(source: str) -> list[dict]:
    # 엑셀 등에서 저장한 CSV는 맨 앞에 BOM(\ufeff)이 붙는 경우가 있어 utf-8-sig로 읽어 자동 제거한다.
    raw = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))

    if reader.fieldnames is None:
        raise ValidationError(["CSV가 비어 있습니다."])

    header = [h.strip() for h in reader.fieldnames]
    if header != REQUIRED_HEADER:
        raise ValidationError(
            [f"CSV 헤더가 다릅니다. 기대: {REQUIRED_HEADER}, 실제: {header}"]
        )

    rows = []
    for r in reader:
        rows.append({k.strip(): (v or "").strip() for k, v in r.items()})
    return rows


def summarize(rows: list[dict], capacity: int | None, event_name: str | None) -> dict:
    """규칙대로 집계한다. 값 오류가 있으면 ValidationError를 발생시킨다."""
    problems: list[str] = []
    attend_count = 0
    snack_order = {item: 0 for item in SNACK_ITEMS}
    to_confirm: list[dict] = []

    for i, row in enumerate(rows, start=1):
        num = row.get("신청번호", "")
        name = row.get("이름", "")
        attend = row.get("참가 여부", "")
        snack = row.get("간식 선택", "")

        if attend not in VALID_ATTEND:
            problems.append(
                f"{i}행({num} {name}): 참가 여부 값이 올바르지 않습니다: {attend!r}"
            )
            continue
        if snack not in VALID_SNACK:
            problems.append(
                f"{i}행({num} {name}): 간식 선택 값이 올바르지 않습니다: {snack!r}"
            )
            continue

        if attend == ATTEND_NO:
            # 불참: 인원·간식·확인 모두 제외 (빈칸도 확인하지 않음)
            continue

        # 여기부터 참가자
        attend_count += 1
        if snack == "":
            to_confirm.append(
                {"신청번호": num, "이름": name, "사유": "참가이나 간식 선택 빈칸(미응답)"}
            )
        elif snack in snack_order:
            snack_order[snack] += 1
        # SNACK_NONE("받지 않음")은 주문하지 않으므로 아무것도 하지 않는다.

    if problems:
        raise ValidationError(problems)

    over = capacity is not None and attend_count > capacity

    return {
        "행사명": event_name,
        "참가_인원": attend_count,
        "정원": capacity,
        "정원_초과": bool(over),
        "간식_주문": {item: snack_order[item] for item in SNACK_ITEMS},
        "생수": attend_count,
        "확인할_사람": to_confirm,
        "주문_확정_여부": False,
    }


def _parse_args(argv: list[str]) -> tuple[str, str, int | None, str | None]:
    """위치 인자(source, out)와 옵션(--정원, --행사명)을 분리한다."""
    positional: list[str] = []
    capacity: int | None = None
    event_name: str | None = None

    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--정원":
            if i + 1 >= len(argv):
                raise ValidationError(["--정원 뒤에 숫자가 필요합니다."])
            try:
                capacity = int(argv[i + 1])
            except ValueError:
                raise ValidationError([f"--정원 값이 숫자가 아닙니다: {argv[i + 1]!r}"])
            i += 2
        elif a == "--행사명":
            if i + 1 >= len(argv):
                raise ValidationError(["--행사명 뒤에 이름이 필요합니다."])
            event_name = argv[i + 1]
            i += 2
        else:
            positional.append(a)
            i += 1

    if not positional:
        raise ValidationError(["입력 CSV 경로(또는 -)가 필요합니다."])

    source = positional[0]
    out_path = positional[1] if len(positional) > 1 else "event.json"
    return source, out_path, capacity, event_name


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2

    try:
        source, out_path, capacity, event_name = _parse_args(argv[1:])
        rows = _read_rows(source)
        result = summarize(rows, capacity, event_name)
    except ValidationError as e:
        print("저장하지 않았습니다. 다음을 고쳐 주세요:", file=sys.stderr)
        for p in e.problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    ordered = {field: result[field] for field in FIELD_ORDER}
    Path(out_path).write_text(
        json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"집계 완료. 저장: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
