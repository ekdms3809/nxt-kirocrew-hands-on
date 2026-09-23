# -*- coding: utf-8 -*-
"""
E04(빛담 가을사진전) 집계 스크립트
- data/ 의 CSV 3개(참가신청·구매계획·회계내역)를 전체 읽어 집계한다.
- 원본은 절대 수정하지 않는다(읽기 전용).
- 결과를 submissions/E04집계.json 으로 저장한다.
- 표준 라이브러리만 사용. 판단 근거를 문서 ID·조항으로 남긴다.

근거 문서:
  RULE-01(학교지원금 지침), RULE-02(공간·정원 규정),
  CLUB-01(동아리 운영 규칙), APPROVAL-FUND-04(E04 지원금 승인서),
  APPROVAL-SPACE-04(E04 장소 사용 승인서)
"""
import csv
import json
import os
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(BASE, "..", "data"))
OUT = os.path.join(BASE, "E04집계.json")
EVENT = "E04"  # RULE-01 제1조/제5조: 행사 범위는 E04로 한정, 타 행사 자금 전용 금지


def load(name):
    path = os.path.join(DATA, name)
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows, path


def won(v):
    return int(str(v).strip() or 0)


def main():
    part, p_part = load("참가신청.csv")
    plan, p_plan = load("구매계획.csv")
    acc, p_acc = load("회계내역.csv")

    read_counts = {
        "참가신청.csv": len(part),
        "구매계획.csv": len(plan),
        "회계내역.csv": len(acc),
    }

    # ---------- 1) 참가 상태별 인원 ----------
    # CLUB-01 제1조: 상태=확정/대기/취소. 물품 기본 인원은 확정 인원.
    status = {}
    for r in part:
        status[r["신청상태"]] = status.get(r["신청상태"], 0) + 1
    confirmed = [r for r in part if r["신청상태"] == "확정"]
    n_confirmed = status.get("확정", 0)

    # ---------- 2) 확정자의 선택 ----------
    # 물품/식음료 기본 인원은 확정 인원 기준(CLUB-01 제1조)
    inhwa_yes = sum(1 for r in confirmed if r["인화체험"] == "신청")
    food_yes = sum(1 for r in confirmed if r["식음료"] == "신청")
    choices = {
        "확정_인원": n_confirmed,
        "인화체험_신청": inhwa_yes,
        "인화체험_미신청": n_confirmed - inhwa_yes,
        "식음료_신청": food_yes,
        "식음료_받지않음": n_confirmed - food_yes,
    }

    # ---------- 3) 회계: E04 범위만, 기초잔액·환불부호 적용 ----------
    # RULE-01 제1조/제5조: 행사 범위 = E04. 다른 행사 자금 전용 금지.
    # 부호 규칙: 수입/환불입금 = (+), 지출 = (-).
    e04 = [r for r in acc if r["행사_ID"] == EVENT]

    def flow(rows, fund):
        income = ref = expense = 0
        for r in rows:
            if r["재원"] != fund:
                continue
            amt = won(r["금액"])
            if r["유형"] == "수입":
                income += amt
            elif r["유형"] == "환불입금":  # 환불은 (+)로 현금 복원
                ref += amt
            elif r["유형"] == "지출":       # 지출은 (-)
                expense += amt
        return income, ref, expense

    # ---------- 학교지원금 (E04) ----------
    # APPROVAL-FUND-04: 총 승인 1,500,000 / 1차 지급 1,000,000(T091) /
    #   잔여 500,000은 미입금 → 현금에 더하지 않음(RULE-01 제5조).
    fund_income, fund_refund, fund_expense = flow(e04, "학교지원금")
    approved_limit = 1_500_000       # 지출 한도(APPROVAL-FUND-04, RULE-01 제5조)
    disbursed = 1_000_000            # 실제 입금(T091)
    # 학교지원금 순지출 = 지출 - 환불입금
    fund_net_expense = fund_expense - fund_refund

    # 확인 필요 지출(학교지원금)
    #  RULE-01 제4조: 용도 불명확/증빙 없음 → 확인 필요 보류
    #  RULE-01 제3조: 기념품·개인 선물 지원 제외
    holds = []
    for r in e04:
        if r["재원"] != "학교지원금" or r["유형"] != "지출":
            continue
        reasons = []
        if not str(r["용도"]).strip():
            reasons.append("용도 빈칸(RULE-01 제4조)")
        if r["증빙"] == "없음":
            reasons.append("증빙 없음(RULE-01 제4조)")
        if r["항목"] in ("기념품",) or "열쇠고리" in str(r["용도"]) or "기념" in str(r["항목"]):
            reasons.append("기념품 지원 제외(RULE-01 제3조)")
        if reasons:
            holds.append({
                "거래_ID": r["거래_ID"], "항목": r["항목"], "용도": r["용도"],
                "금액": won(r["금액"]), "증빙": r["증빙"], "사유": reasons,
            })

    fund = {
        "총_승인_한도": approved_limit,
        "실제_입금_1차": disbursed,
        "미입금_잔여": approved_limit - disbursed,  # 현금 아님(RULE-01 제5조)
        "총_지출": fund_expense,
        "환불입금": fund_refund,
        "순지출": fund_net_expense,
        "가용현금_잔액": disbursed + fund_refund - fund_expense,  # 입금분 기준
        "확인_필요_지출": holds,
        "근거": "APPROVAL-FUND-04, RULE-01 제3·4·5조",
    }

    # ---------- 4) 회비 현재 잔액 (E04) ----------
    # CLUB-01 제2조/제4조. 기초잔액=이번 집계 범위 E04만 계산(요청: 행사 범위 적용).
    # 부호: 수입/환불입금(+), 지출(-).
    club_income, club_refund, club_expense = flow(e04, "동아리회비")
    club = {
        "기초잔액_E04범위": 0,  # E04 범위 한정 집계(이월 잔액은 CSV에 없음 → 0에서 시작)
        "수입_회비배정": club_income,
        "환불입금": club_refund,
        "지출": club_expense,
        "현재_잔액": 0 + club_income + club_refund - club_expense,
        "근거": "CLUB-01 제2·4조 / 행사 범위 E04 한정",
        "참고": "CSV에 E04 이월 기초잔액 항목이 없어 기초 0으로 계산. 전체 회비 잔액이 필요하면 확인 필요.",
    }

    # ---------- 5) E04 순지출(전체 재원 합산) ----------
    # 순지출 = 모든 지출 - 모든 환불입금 (수입은 지출이 아니므로 제외)
    total_expense = fund_expense + club_expense
    total_refund = fund_refund + club_refund
    e04_net = {
        "총_지출": total_expense,
        "총_환불입금": total_refund,
        "순지출": total_expense - total_refund,
        "학교지원금_순지출": fund_net_expense,
        "회비_순지출": club_expense - club_refund,
        "근거": "회계내역 E04, 환불입금 (+) 부호 적용",
    }

    # ---------- 6) 140/160/180명 구매계획 수량·비용 ----------
    # 구매계획.csv: 수량기준=참가자 → 인원 비례, 고정 → 계수 그대로.
    # 수량 = (참가자면 인원, 고정이면 1) * 계수 ; 비용 = 수량 * 단가.
    # RULE-02 제1조: 승인 정원=160(APPROVAL-SPACE-04). 140=확정 인원. 180=홍보물(미승인).
    def plan_cost(headcount):
        by_fund = {"학교지원금": 0, "동아리회비": 0}
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
        "160명_승인정원": plan_cost(160),
        "180명_홍보물_미승인": plan_cost(180),
    }
    capacity = {
        "승인_정원": 160,
        "홍보_안내": 180,
        "확정_인원": n_confirmed,
        "차이_홍보_대_승인": 180 - 160,
        "판단": "홍보물 180명은 승인 조건과 불일치. RULE-02 제2조에 따라 유효한 변경 승인서 없이는 160명 유지. 180명 시나리오는 참고용.",
        "근거": "APPROVAL-SPACE-04, RULE-02 제1·2조",
    }

    result = {
        "행사": EVENT,
        "생성일": date.today().isoformat(),
        "읽은_행수": read_counts,
        "참가상태별_인원": status,
        "확정자_선택": choices,
        "정원": capacity,
        "학교지원금": fund,
        "회비": club,
        "E04_순지출": e04_net,
        "구매계획_시나리오": scenarios,
        "근거문서": {
            "RULE-01": "학교지원금 지침(지원대상·제외·증빙·자금구분)",
            "RULE-02": "공간·참가정원 규정",
            "CLUB-01": "동아리 운영규칙(확정/대기/취소·회비·대기전환·기록)",
            "APPROVAL-FUND-04": "E04 지원금 승인서(한도 1.5M, 1차 1M=T091)",
            "APPROVAL-SPACE-04": "E04 장소 사용 승인서(승인 정원 160)",
        },
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result, OUT


if __name__ == "__main__":
    res, out = main()
    print("저장:", out)
    print(json.dumps(res, ensure_ascii=False, indent=2))
