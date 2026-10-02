#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""notices.md 파싱 스크립트.

mission/data/notices.md의 공지 N01-N06을 코드로 읽어 각 공지의
ID·제목·게시시각·부서·업무/행사 ID·정정관계·모집 마감시각·링크를 구조화하고,
기준 시각 2026-09-14 09:00 (Asia/Seoul)을 기준으로 각 모집의 마감/접수중 상태를
판정한다. 원문에 명시되지 않은 값은 추측하지 않고 '확인 필요'로 표시한다.
결과는 stdout에 출력한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------
KST = ZoneInfo("Asia/Seoul")
# 판정 기준 시각: 2026-09-14 09:00 Asia/Seoul
REFERENCE_TIME = datetime(2026, 9, 14, 9, 0, tzinfo=KST)

# notices.md는 이 스크립트와 같은 week05/mission 트리의 data/ 아래에 있다.
# CWD에 의존하지 않도록 스크립트 위치 기준으로 경로를 해석한다.
SCRIPT_DIR = Path(__file__).resolve().parent
NOTICES_PATH = SCRIPT_DIR / "data" / "notices.md"

UNKNOWN = "확인 필요"  # 원문에 없는 정보 표시값

# 날짜/시각 패턴 (YYYY-MM-DD, 선택적 HH:MM)
_DT_FULL = re.compile(r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})")
_DATE_ONLY = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


@dataclass
class Notice:
    nid: str
    title: str
    posted_at_raw: str = UNKNOWN          # 게시 시각 원문
    department: str = UNKNOWN             # 게시 부서
    work_id: str = UNKNOWN                # 업무 ID / 행사 ID
    correction_target: str | None = None  # 정정 대상 공지 ID
    deadline_raw: str = UNKNOWN           # 모집/신청 마감 원문 표현
    deadline_dt: datetime | None = None   # 파싱된 마감 datetime (시각까지 명시된 경우만)
    deadline_date: date | None = None     # 날짜만 명시되고 시각은 원문에 없는 경우
    is_recruitment: bool = False          # 모집/신청이 포함된 공지인가
    link: str = UNKNOWN                   # 링크(원문에 URL 없음)
    body: str = ""                        # 본문 전체
    schedule_lines: list[str] = field(default_factory=list)


def read_notices_text(path: Path = NOTICES_PATH) -> str:
    """notices.md 원문을 읽어 반환한다."""
    return path.read_text(encoding="utf-8")


def split_notices(text: str) -> list[tuple[str, str, str]]:
    """`## N0x · 제목` 헤더로 공지 블록을 분리한다.

    반환: [(nid, title, block_text), ...]
    """
    results: list[tuple[str, str, str]] = []
    # 각 공지 헤더: "## N01 · 제목"
    pattern = re.compile(r"^##\s+(N\d{2})\s*·\s*(.+?)\s*$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    for i, m in enumerate(matches):
        nid = m.group(1)
        title = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        results.append((nid, title, block))
    return results


def _parse_dt(s: str) -> datetime | None:
    """문자열에서 'YYYY-MM-DD HH:MM'만 KST datetime으로 변환한다.

    시각이 명시되지 않은 'YYYY-MM-DD까지'는 정확한 마감 시각을 원문에서 알 수
    없으므로 추측(예: 23:59)하지 않고 None을 돌려준다(처리 규칙 4: 원문에 없는
    마감 시각은 추측하지 않는다). 날짜만 아는 경우의 상태 판정은 호출부에서
    따로 처리한다.
    """
    m = _DT_FULL.search(s)
    if m:
        y, mo, d, h, mi = (int(x) for x in m.groups())
        return datetime(y, mo, d, h, mi, tzinfo=KST)
    return None


def _parse_date_only(s: str) -> date | None:
    """시각 없는 'YYYY-MM-DD'를 date로. 시각은 포함하지 않는다."""
    m = _DATE_ONLY.search(s)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        return date(y, mo, d)
    return None


def parse_block(nid: str, title: str, block: str) -> Notice:
    """공지 블록 하나를 구조화한다. 원문에 없는 값은 UNKNOWN으로 둔다."""
    notice = Notice(nid=nid, title=title, body=block)

    for line in block.splitlines():
        line = line.strip()
        if line.startswith("- 게시:"):
            notice.posted_at_raw = line.split(":", 1)[1].strip()
        elif line.startswith("- 게시 부서:"):
            notice.department = line.split(":", 1)[1].strip()
        elif line.startswith("- 업무 ID:") or line.startswith("- 행사 ID:"):
            notice.work_id = line.split(":", 1)[1].strip()
        elif line.startswith("- 정정 대상:"):
            notice.correction_target = line.split(":", 1)[1].strip()

    # 모집/신청 마감 판정: 본문에 '모집' 또는 '신청' + 마감 표현이 있을 때만.
    paragraph = " ".join(
        l.strip() for l in block.splitlines() if not l.strip().startswith("-")
    )

    # '별도 신청 없이/없습니다'처럼 신청을 부정하는 안내는 모집이 아니다.
    negated = ("별도 신청은 없습니다", "별도 신청 없이", "별도 신청없이", "신청 없이 참석")
    has_negation = any(neg in paragraph for neg in negated)
    recruitment_kw = ("모집", "접수", "신청서", "신청을", "신청은", "신청합니다", "신청받")
    notice.is_recruitment = (
        any(kw in paragraph for kw in recruitment_kw) and not has_negation
    )

    # 마감 표현 추출: "YYYY-MM-DD HH:MM까지" / "YYYY-MM-DD까지"
    deadline_dt = None
    deadline_date = None
    deadline_raw = UNKNOWN
    # 우선 'HH:MM까지' 형태를 찾는다.
    m_full = re.search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*까지", paragraph)
    m_date = re.search(r"(\d{4}-\d{2}-\d{2})\s*까지", paragraph)
    if m_full:
        deadline_raw = m_full.group(1) + "까지"
        deadline_dt = _parse_dt(m_full.group(1))
    elif m_date:
        # 시각 없는 '…까지' → 날짜만 명시, 정확한 마감 시각은 원문에 없음.
        # 시각을 추측하지 않는다(처리 규칙 4).
        deadline_raw = m_date.group(1) + "까지 (시각 미명시)"
        deadline_date = _parse_date_only(m_date.group(1))

    if notice.is_recruitment:
        notice.deadline_raw = deadline_raw
        notice.deadline_dt = deadline_dt
        notice.deadline_date = deadline_date
    else:
        # 모집/신청이 아닌 안내 공지는 마감 개념이 없음
        notice.deadline_raw = "해당 없음(모집/신청 아님)"

    # 일정(행사/운영 기간) 라인 수집 (참고용)
    for raw in block.splitlines():
        if _DATE_ONLY.search(raw) and not raw.strip().startswith("- 게시"):
            notice.schedule_lines.append(raw.strip())

    # 링크: 원문에 URL 형태가 없으므로 UNKNOWN 유지
    url_m = re.search(r"https?://\S+", block)
    if url_m:
        notice.link = url_m.group(0)

    return notice


def classify_status(notice: Notice, ref: datetime = REFERENCE_TIME) -> str:
    """기준 시각 대비 모집 상태를 판정한다."""
    if not notice.is_recruitment:
        return "모집/신청 아님 (상태 판정 대상 아님)"
    # 1) 시각까지 명시된 마감: 정확히 비교한다.
    if notice.deadline_dt is not None:
        if notice.deadline_dt < ref:
            return f"마감 (마감 {notice.deadline_dt:%Y-%m-%d %H:%M} < 기준 {ref:%Y-%m-%d %H:%M})"
        return f"접수중 (마감 {notice.deadline_dt:%Y-%m-%d %H:%M} ≥ 기준 {ref:%Y-%m-%d %H:%M})"
    # 2) 날짜만 명시되고 시각은 원문에 없는 마감.
    if notice.deadline_date is not None:
        ref_date = ref.date()
        if notice.deadline_date > ref_date:
            return f"접수중 (마감일 {notice.deadline_date} > 기준일 {ref_date}, 마감 시각 무관)"
        if notice.deadline_date < ref_date:
            return f"마감 (마감일 {notice.deadline_date} < 기준일 {ref_date}, 마감 시각 무관)"
        # 같은 날: 정확한 마감 시각이 원문에 없어 접수중/마감을 단정할 수 없음.
        return (
            f"{UNKNOWN} (마감일 {notice.deadline_date} = 기준일 {ref_date}, "
            f"마감 시각 미명시로 상태 단정 불가)"
        )
    return f"{UNKNOWN} (마감시각 원문 미확인)"


def build_notices(text: str) -> list[Notice]:
    return [parse_block(nid, title, block) for nid, title, block in split_notices(text)]


def main() -> None:
    text = read_notices_text()
    notices = build_notices(text)

    print("=" * 72)
    print(f"notices.md 파싱 결과")
    print(f"입력 파일 : {NOTICES_PATH}")
    print(f"기준 시각 : {REFERENCE_TIME:%Y-%m-%d %H:%M} ({REFERENCE_TIME.tzinfo})")
    print(f"공지 수   : {len(notices)}건")
    print("=" * 72)

    # 정정 관계 매핑: 어떤 공지가 어떤 공지를 정정했는가
    corrected_by: dict[str, str] = {}
    for n in notices:
        if n.correction_target:
            corrected_by[n.correction_target] = n.nid

    for n in notices:
        print()
        print(f"[{n.nid}] {n.title}")
        print(f"  게시      : {n.posted_at_raw}")
        print(f"  부서      : {n.department}")
        print(f"  업무/행사 ID : {n.work_id}")
        if n.correction_target:
            print(f"  정정 대상 : {n.correction_target} (이 공지가 {n.correction_target}를 정정함)")
        if n.nid in corrected_by:
            print(f"  정정됨    : {corrected_by[n.nid]}에 의해 정정됨 → 기존 일정은 단독 안내 금지")
        print(f"  모집/신청 : {'예' if n.is_recruitment else '아니오'}")
        print(f"  마감 원문 : {n.deadline_raw}")
        print(f"  링크      : {n.link}")
        print(f"  상태 판정 : {classify_status(n)}")

    print()
    print("=" * 72)
    print("요약 (기준 시각 2026-09-14 09:00 KST)")
    print("-" * 72)
    for n in notices:
        print(f"  {n.nid}: {classify_status(n)}")
    print("=" * 72)


if __name__ == "__main__":
    main()
