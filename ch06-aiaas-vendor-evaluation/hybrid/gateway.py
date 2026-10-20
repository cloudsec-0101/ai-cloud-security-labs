"""Hybrid 경계의 가명처리 검문소(실습용 축소판).
사용법: python3 gateway.py records.txt [--direct] [--rules basic|strict]
  --direct        검문소 없이 원문을 그대로 외부로 보낸다(비교용)
  --rules basic   고객 DB에 있는 이름과 표준 형식 전화번호만 가명으로 바꾼다
  --rules strict  basic에 더해, 띄어 쓴 전화번호와 계좌번호처럼 보이는 숫자도 가린다

흐름: 사내 원문 → [가명처리] → 외부 AI(fake_ai.py) → 가명이 섞인 요약 → [사내에서 복원] → 사용자
가명과 원래 값을 잇는 대응표(table)는 사내에만 두고 외부로 보내지 않는다. 이것이 가명처리의 핵심이다.
basic과 strict를 차례로 돌려 received.log를 비교하면, "DB에 있는 값만 찾는" 방식이 무엇을 놓치는지 보인다.
"""
import csv
import json
import re
import sys
import urllib.request

FAKE_AI = "http://127.0.0.1:8081"     # 외부 AI 서비스 역할(fake_ai.py)


def load_customers(path="customers.csv"):
    """사내 고객 DB 역할. 가명처리할 이름·전화번호의 기준 목록이다."""
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def pseudonymize(text, customers, rules):
    """원문에서 민감정보를 가명으로 바꾸고, (바꾼 글, 가명→원래 값 대응표)를 돌려준다."""
    table = {}                                   # 가명 → 원래 값 (사내에만 보관)
    # basic: 고객 DB에 등록된 값과 "정확히 같은" 글자만 찾아 바꾼다 (예: 김민준 → 고객01)
    for i, c in enumerate(customers, 1):
        for value, alias in [(c["name"], f"고객{i:02d}"), (c["phone"], f"전화{i:02d}")]:
            if value in text:
                text = text.replace(value, alias)
                table[alias] = value
    if rules == "strict":
        # strict: DB에 없거나 형식이 다른 값도 "모양"으로 찾아 가린다 (정규식)
        n = 0
        for pattern, label in [(r"01[016789][ -]?\d{3,4}[ -]?\d{4}", "전화"),   # 010 1234 5678, 01012345678 등
                               (r"\d{2,6}-\d{2,6}-\d{2,8}", "계좌")]:           # 123-456-789012 같은 숫자 묶음
            # 긴 것부터 바꿔야, 짧은 값이 긴 값의 일부를 먼저 바꿔 버리는 일을 막을 수 있다
            for found in sorted(set(re.findall(pattern, text)), key=len, reverse=True):
                n += 1
                alias = f"{label}X{n:02d}"
                text = text.replace(found, alias)
                table[alias] = found
    return text, table


def restore(text, table):
    """외부에서 받은 요약 속 가명을 사내 대응표로 원래 값으로 되돌린다."""
    # 긴 가명부터 바꾼다 (짧은 가명이 긴 가명의 일부와 겹쳐 잘못 바뀌는 것을 막음)
    for alias, value in sorted(table.items(), key=lambda kv: len(kv[0]), reverse=True):
        text = text.replace(alias, value)
    return text


def call_external(text):
    """경계를 넘어 외부 AI 서비스로 보낸다. 이 함수에 들어가는 글이 곧 '밖으로 나간 데이터'다."""
    req = urllib.request.Request(FAKE_AI, data=json.dumps({"text": text}, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())["summary"]


def main():
    path = sys.argv[1]
    direct = "--direct" in sys.argv
    rules = sys.argv[sys.argv.index("--rules") + 1] if "--rules" in sys.argv else "basic"
    original = open(path, encoding="utf-8").read().strip()
    if direct:
        # 비교용: 검문소 없이 원문을 그대로 보낸다 → received.log에 실명·번호가 그대로 남는다
        print(call_external(original))
        return
    masked, table = pseudonymize(original, load_customers(), rules)
    summary = call_external(masked)
    print("== 외부로 보낸 내용 ==\n" + masked)
    print("\n== 받은 요약(가명) ==\n" + summary)
    print("\n== 사내에서 복원한 요약 ==\n" + restore(summary, table))


if __name__ == "__main__":
    main()
