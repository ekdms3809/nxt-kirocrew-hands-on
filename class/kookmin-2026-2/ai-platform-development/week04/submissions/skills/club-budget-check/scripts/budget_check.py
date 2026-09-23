# -*- coding: utf-8 -*-
"""
club-budget-check: 동아리 행사 예산 점검 스크립트

- data/ 의 CSV 3개(회계내역·구매계획·참가신청)를 전체 읽어 집계·검사한다.
- 원본은 절대 수정하지 않는다(읽기 전용). 표준 라이브러리만 사용(Python 3.9+).
- 판단은 하지 않고 SKILL.md에 고정된 규칙만 적용한다. 근거를 문서 ID·조항으로 남긴다.
- 스키마를 만족할 때만 저장한다. 아니면 사유를 출력하고 exit 1.

근거 문서:
  RULE-01(학교지원금 지침), RULE-02(공간·정원 규정),
  ACCOUNT-01(회계기준: 기초잔액·부호·순지출), APPROVAL-FUND-04(지원금 승인서),
  APPROVAL-SPACE-04(장소 승인, 최초 정원 160),
  CHANGE-SPACE-04(정원변경승인서: 승인 정원 160→180, 예산증액 아님)
"""
import argparse
import csv
import json
import os
import sys
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))

# ── ACCOUNT-01 제1조: 기초 잔액(전체 동아리 기준) ───────────────
BASE_BALANCE = {"학교지원금": 0, "동아리회비": 800_000}
# APPROVAL-FUND-04: 총 승인 한도 / 1차 실제 입금(T091)
FUND_APPROVED_LIMIT = 1_500_000
FUND_DISBURSED = 1_000_000
# CHANGE-SPACE-04: 승인 정원 160 → 180 (APPROVAL-SPACE-04 정원 조항 대체)
APPROVED_CAPACITY = 180

REQUIRED_ACC_COLS = {"거래_ID", "거래일", "행사_ID", "재원", "유형", "항목", "용도", "금액", "증빙", "원거래_ID"}
REQUIRED_PLAN_COLS = {"항목_ID", "물품", "수량기준", "계수", "단가", "예정재원", "용도"}


def load(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows


def won(v):
    return int(str(v).strip() or 0)


def build(data_dir, event):
    p_acc = os.path.join(data_dir, "회계내역.csv")
    p_plan = os.path.join(data_dir, "구매계획.csv")
    p_part = os.path.join(data_dir, "참가신청.csv")

    acc = load(p_acc)
    plan = load(p_plan)
    part = load(p_part)

    # 헤더 검사 (판단 아님, 스키마 검증)
    if acc and not REQUIRED_ACC_COLS.issubset(acc[0].keys()):
        raise ValueError(f"회계내역.csv 헤더 불일치: {sorted(acc[0].keys())}")
    if plan and not REQUIRED_PLAN_COLS.issubset(plan[0].keys()):
        raise ValueError(f"구매계획.csv 헤더 불일치: {sorted(plan[0].keys())}")

    read_counts = {
        "회계내역.csv": len(acc),
        "구매계획.csv": len(plan),
        "참가신청.csv": len(part),
    }

    # ── 1) 참가 상태별 인원 ──
    status = {}
    for r in part:
        status[r["신청상태"]] = status.get(r["신청상태"], 0) + 1
    n_confirmed = status.get("확정", 0)

    # 이 행사 거래만
    ev = [r for r in acc if r["행사_ID"] == event]

    def flow(rows, fund):
        income = refund_in = expense = refund_out = 0
        for r in rows:
            if r["재원"] != fund:
                continue
            amt = won(r["금액"])
            t = r["유형"]
            if t == "수입":
                income += amt
            elif t == "환불입금":     # (+)
                refund_in += amt
            elif t == "지출":         # (-)
                expense += amt
            elif t == "환불지급":     # (-)
                refund_out += amt
        return income, refund_in, expense, refund_out

    # ── 2) 학교지원금 (ACCOUNT-01 제3조 / RULE-01 제5조) ──
    f_income, f_refund_in, f_expense, f_refund_out = flow(ev, "학교지원금")
    fund_net_expense = f_expense + f_refund_out - f_refund_in
    # 현재 잔액은 실제 입금(1차) 기준. 미입금 잔여는 현금 아님.
    fund_balance = (BASE_BALANCE["학교지원금"] + FUND_DISBURSED
                    + f_refund_in - f_expense - f_refund_out)

    # 확인 필요 지출(RULE-01 제3·4조)
    holds = []
    for r in ev:
        if r["재원"] != "학교지원금" or r["유형"] != "지출":
            continue
        reasons = []
        if not str(r["용도"]).strip():
            reasons.append("용도 빈칸(RULE-01 제4조)")
        if r["증빙"] == "없음":
            reasons.append("증빙 없음(RULE-01 제4조)")
        excl = ("기념품", "선물", "주류", "개인장비")
        if any(k in str(r["항목"]) for k in excl) or any(k in str(r["용도"]) for k in ("기념", "선물", "열쇠고리")):
            reasons.append("지원 제외 대상(RULE-01 제3조)")
        if reasons:
            holds.append({
                "거래_ID": r["거래_ID"], "항목": r["항목"], "용도": r["용도"],
                "금액": won(r["금액"]), "증빙": r["증빙"], "사유": reasons,
            })

    fund = {
        "기초잔액": BASE_BALANCE["학교지원금"],
        "총_승인_한도": FUND_APPROVED_LIMIT,
        "실제_입금": FUND_DISBURSED,
        "미입금_잔여": FUND_APPROVED_LIMIT - FUND_DISBURSED,
        "지출": f_expense,
        "환불입금": f_refund_in,
        "순지출": fund_net_expense,
        "현재_잔액": fund_balance,
        "확인_필요_지출": holds,
        "근거": "APPROVAL-FUND-04, ACCOUNT-01 제3조, RULE-01 제3·4·5조",
    }

    # ── 3) 동아리회비 (ACCOUNT-01 제3조) ──
    c_income, c_refund_in, c_expense, c_refund_out = flow(ev, "동아리회비")
    club_net_expense = c_expense + c_refund_out - c_refund_in
    club_balance = (BASE_BALANCE["동아리회비"] + c_income
                    + c_refund_in - c_expense - c_refund_out)
    club = {
        "기초잔액": BASE_BALANCE["동아리회비"],
        "수입": c_income,
        "환불입금": c_refund_in,
        "지출": c_expense,
        "순지출": club_net_expense,
        "현재_잔액": club_balance,
        "근거": "ACCOUNT-01 제1·3조",
    }

    # ── 4) 행사 순지출(전체 재원) ──
    total_expense = f_expense + c_expense
    total_refund_in = f_refund_in + c_refund_in
    total_refund_out = f_refund_out + c_refund_out
    ev_net = {
        "총_지출": total_expense,
        "총_환불입금": total_refund_in,
        "순지출": total_expense + total_refund_out - total_refund_in,
        "학교지원금_순지출": fund_net_expense,
        "회비_순지출": club_net_expense,
        "근거": "ACCOUNT-01 제3조(순지출=지출+환불지급-환불입금, 수입 제외)",
    }

    # ── 5) 정원 (CHANGE-SPACE-04) ──
    capacity = {
        "승인_정원": APPROVED_CAPACITY,
        "확정_인원": n_confirmed,
        "정원_초과": n_confirmed > APPROVED_CAPACITY,
        "근거": "CHANGE-SPACE-04(160→180 대체), RULE-02",
        "참고": "CHANGE-SPACE-04는 예산 증액이 아니며 신청자 상태를 자동 변경하지 않는다. 확정 인원은 참가신청 CSV 그대로.",
    }

    # ── 6) 구매계획 시나리오 (ACCOUNT-01 제5조) ──
    def plan_cost(headcount):
        by_fund = {}
        lines = []
        for r in plan:
            coef = int(r["계수"])
            unit = int(r["단가"])
            base = headcount if r["수량기준"] == "참가자" else 1
            qty = base * coef
            cost = qty * unit
            by_fund[r["예정재원"]] = by_fund.get(r["예정재원"], 0) + cost
            lines.append({
                "항목_ID": r["항목_ID"], "물품": r["물품"], "수량기준": r["수량기준"],
                "수량": qty, "단가": unit, "비용": cost, "예정재원": r["예정재원"],
            })
        return {"인원": headcount, "재원별_합계": by_fund,
                "총_비용": sum(by_fund.values()), "라인": lines}

    scenarios = {
        "140명_확정인원": plan_cost(140),
        "160명_최초승인": plan_cost(160),
        "180명_현재승인정원": plan_cost(APPROVED_CAPACITY),
    }

    return {
        "행사": event,
        "생성일": date.today().isoformat(),
        "읽은_행수": read_counts,
        "참가상태별_인원": status,
        "정원": capacity,
        "학교지원금": fund,
        "회비": club,
        "행사_순지출": ev_net,
        "구매계획_시나리오": scenarios,
        "근거문서": {
            "RULE-01": "학교지원금 지침(지원대상·제외·증빙·자금구분)",
            "RULE-02": "공간·참가정원 규정",
            "ACCOUNT-01": "회계기준(기초잔액·부호·순지출 공식)",
            "APPROVAL-FUND-04": "지원금 승인서(한도 1.5M, 1차 1M=T091)",
            "APPROVAL-SPACE-04": "장소 사용 승인서(최초 정원 160)",
            "CHANGE-SPACE-04": "정원변경승인서(승인 정원 160→180, 예산증액 아님)",
        },
    }


def validate(res):
    """고정 스키마 검사. 실패 시 사유 문자열 반환, 통과 시 None."""
    top = ["행사", "생성일", "읽은_행수", "참가상태별_인원", "정원",
           "학교지원금", "회비", "행사_순지출", "구매계획_시나리오", "근거문서"]
    missing = [k for k in top if k not in res]
    if missing:
        return f"최상위 항목 누락: {missing}"
    extra = [k for k in res if k not in top]
    if extra:
        return f"허용되지 않은 항목: {extra}"
    for k in ("승인_정원", "확정_인원", "정원_초과"):
        if k not in res["정원"]:
            return f"정원.{k} 누락"
    if not isinstance(res["정원"]["정원_초과"], bool):
        return "정원.정원_초과 는 불리언이어야 함"
    for h in res["학교지원금"]["확인_필요_지출"]:
        if not isinstance(h.get("사유"), list):
            return "확인_필요_지출.사유 는 문자열 목록이어야 함"
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="동아리 행사 예산 점검")
    ap.add_argument("--event", default="E04", help="집계할 행사 ID (기본 E04)")
    ap.add_argument("--data", default=os.path.normpath(os.path.join(BASE, "..", "data")),
                    help="CSV 3개가 있는 폴더")
    ap.add_argument("--out", default=None, help="출력 JSON 경로 (기본 submissions/<행사>예산점검.json)")
    args = ap.parse_args(argv)

    try:
        res = build(args.data, args.event)
    except (OSError, ValueError, KeyError) as e:
        print(f"[실패] 입력/스키마 오류: {e}", file=sys.stderr)
        return 1

    reason = validate(res)
    if reason:
        print(f"[실패] 스키마 검사: {reason}", file=sys.stderr)
        return 1

    out = args.out or os.path.normpath(
        os.path.join(BASE, "..", "..", "submissions", f"{args.event}예산점검.json"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print("저장:", out)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
