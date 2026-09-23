#!/usr/bin/env python3
"""요약 JSON을 검사하고, 정해진 틀의 HTML 보고서로 렌더·저장한다.

data-to-html 스킬의 실행 스크립트. Python 3.9+, 표준 라이브러리만 사용.
판단은 하지 않는다. md·csv 읽기와 요약·표 선별은 AI가 끝낸 상태로 넘어온다.
스키마를 만족할 때만 저장하고, 항목 누락/추가나 자료형 오류가 있으면 저장하지 않고 사유를 알린다.
"""
import html
import json
import re
import sys

TOP_SCHEMA = {
    "제목": (str,),
    "생성일": (str, type(None)),
    "요약": (list,),
    "섹션": (list,),
}
GLE_SCHEMA = {"유형": (str,), "소제목": (str,), "출처": (str,), "내용": (list,)}
GLE_ITEM_SCHEMA = {"항목": (str,), "값": (str,), "근거": (str,)}
TABLE_SCHEMA = {"유형": (str,), "소제목": (str,), "출처": (str,), "열": (list,), "행": (list,)}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _check_keys(obj, schema, where):
    if not isinstance(obj, dict):
        return f"{where}: 객체가 아님"
    keys, expected = set(obj.keys()), set(schema.keys())
    if keys != expected:
        missing = sorted(expected - keys)
        extra = sorted(keys - expected)
        parts = []
        if missing:
            parts.append(f"누락: {missing}")
        if extra:
            parts.append(f"추가: {extra}")
        return f"{where} 항목 불일치 — " + ", ".join(parts)
    for key, types in schema.items():
        if not isinstance(obj[key], types):
            return f"{where}: '{key}' 자료형 오류 — {types} 기대, 실제 {type(obj[key])}"
    return None


def validate(data):
    err = _check_keys(data, TOP_SCHEMA, "최상위")
    if err:
        return err

    if data["생성일"] is not None and not DATE_RE.match(data["생성일"]):
        return "생성일 형식 오류 — 'YYYY-MM-DD' 또는 null 이어야 함"

    for i, s in enumerate(data["요약"]):
        if not isinstance(s, str):
            return f"요약[{i}] 자료형 오류 — 문자열이어야 함"

    for i, sec in enumerate(data["섹션"]):
        if not isinstance(sec, dict) or "유형" not in sec:
            return f"섹션[{i}]: '유형' 없음"
        유형 = sec["유형"]
        if 유형 == "글":
            err = _check_keys(sec, GLE_SCHEMA, f"섹션[{i}](글)")
            if err:
                return err
            if not sec["출처"].strip():
                return f"섹션[{i}](글): '출처'가 비어 있음 — 근거 문서를 채워야 함"
            for j, item in enumerate(sec["내용"]):
                err = _check_keys(item, GLE_ITEM_SCHEMA, f"섹션[{i}].내용[{j}]")
                if err:
                    return err
        elif 유형 == "표":
            err = _check_keys(sec, TABLE_SCHEMA, f"섹션[{i}](표)")
            if err:
                return err
            if not sec["출처"].strip():
                return f"섹션[{i}](표): '출처'가 비어 있음 — 근거 CSV·문서를 채워야 함"
            열 = sec["열"]
            if len(열) < 1:
                return f"섹션[{i}](표): '열'이 비어 있음"
            for j, c in enumerate(열):
                if not isinstance(c, str):
                    return f"섹션[{i}].열[{j}] 자료형 오류 — 문자열이어야 함"
            for r, row in enumerate(sec["행"]):
                if not isinstance(row, list):
                    return f"섹션[{i}].행[{r}] 자료형 오류 — 목록이어야 함"
                if len(row) != len(열):
                    return (f"섹션[{i}].행[{r}] 길이 불일치 — "
                            f"열 {len(열)}개, 행 {len(row)}개")
                for c, cell in enumerate(row):
                    if not isinstance(cell, str):
                        return f"섹션[{i}].행[{r}][{c}] 자료형 오류 — 문자열이어야 함"
        else:
            return f"섹션[{i}]: '유형' 값이 규칙에 없음 — '{유형}' (글/표만 허용)"
    return None


def _esc(s):
    return html.escape(str(s), quote=True)


def render_html(data):
    parts = []
    title = _esc(data["제목"])
    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="ko">')
    parts.append("<head>")
    parts.append('<meta charset="utf-8">')
    parts.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    parts.append(f"<title>{title}</title>")
    parts.append("<style>")
    parts.append(
        "body{font-family:system-ui,'Apple SD Gothic Neo',sans-serif;"
        "max-width:820px;margin:2rem auto;padding:0 1rem;line-height:1.6;color:#1a1a1a}"
        "h1{border-bottom:2px solid #333;padding-bottom:.4rem}"
        ".meta{color:#666;font-size:.9rem;margin-bottom:1.5rem}"
        ".summary{background:#f6f8fa;border-radius:8px;padding:1rem 1.2rem;margin-bottom:1.5rem}"
        "h2{margin-top:2rem}"
        "table{border-collapse:collapse;width:100%;margin:.5rem 0}"
        "th,td{border:1px solid #ccc;padding:.5rem .7rem;text-align:left}"
        "th{background:#eef1f4}"
        "tr:nth-child(even) td{background:#fafbfc}"
        ".src{color:#557;font-size:.82rem;margin:.2rem 0 .4rem;font-style:italic}"
    )
    parts.append("</style>")
    parts.append("</head>")
    parts.append("<body>")
    parts.append(f"<h1>{title}</h1>")

    if data["생성일"]:
        parts.append(f'<p class="meta">생성일: {_esc(data["생성일"])}</p>')

    if data["요약"]:
        parts.append('<div class="summary"><strong>요약</strong><ul>')
        for line in data["요약"]:
            parts.append(f"<li>{_esc(line)}</li>")
        parts.append("</ul></div>")

    for sec in data["섹션"]:
        parts.append(f"<h2>{_esc(sec['소제목'])}</h2>")
        parts.append(f'<p class="src">출처: {_esc(sec["출처"])}</p>')
        if sec["유형"] == "글":
            if sec["내용"]:
                parts.append("<table><thead><tr>"
                             "<th>항목</th><th>값</th><th>근거</th>"
                             "</tr></thead><tbody>")
                for item in sec["내용"]:
                    parts.append(
                        "<tr>"
                        f"<td>{_esc(item['항목'])}</td>"
                        f"<td>{_esc(item['값'])}</td>"
                        f"<td>{_esc(item['근거'])}</td>"
                        "</tr>"
                    )
                parts.append("</tbody></table>")
        else:  # 표
            parts.append("<table><thead><tr>")
            for col in sec["열"]:
                parts.append(f"<th>{_esc(col)}</th>")
            parts.append("</tr></thead><tbody>")
            for row in sec["행"]:
                parts.append("<tr>")
                for cell in row:
                    parts.append(f"<td>{_esc(cell)}</td>")
                parts.append("</tr>")
            parts.append("</tbody></table>")

    parts.append("</body></html>")
    return "\n".join(parts) + "\n"


def main(argv):
    if len(argv) < 2:
        print("사용법: python3 render.py <입력.json|-> [출력.html]", file=sys.stderr)
        return 2
    source = argv[1]
    out = argv[2] if len(argv) > 2 else "report.html"

    try:
        text = sys.stdin.read() if source == "-" else open(source, encoding="utf-8").read()
        data = json.loads(text)
    except (OSError, json.JSONDecodeError) as e:
        print(f"저장하지 않음 — 입력 오류: {e}", file=sys.stderr)
        return 1

    err = validate(data)
    if err:
        print(f"저장하지 않음 — 스키마 검사 실패: {err}", file=sys.stderr)
        return 1

    with open(out, "w", encoding="utf-8") as f:
        f.write(render_html(data))
    print(f"저장 완료: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
