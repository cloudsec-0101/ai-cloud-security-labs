"""Agent의 Tool 호출 실행기(실습용 축소판).
모델 대신 requests.json(Agent가 내놓은 Tool 호출 요청 목록)을 읽어 차례로 처리한다.
Tool은 모두 가짜다. 실제 파일을 읽거나 메일을 보내지 않고 "실행했다"는 결과만 돌려준다.

사용법:
  python3 runner.py --no-guard     검사 없이 요청을 그대로 실행한다(비교용)
  python3 runner.py                실행 전에 다섯 단계 검사를 거친다
긴급 중지: 같은 폴더에 STOP 파일을 만들면 그 뒤의 모든 호출을 멈춘다.

핵심 생각: 모델이 무엇을 "요청"하든, 실제 "실행"은 모델 바깥의 코드(이 파일)가 정책에 따라 결정한다.
프롬프트 인젝션으로 모델이 속더라도, 여기서 막히면 피해로 이어지지 않는다.
검사 규칙(허용 Tool, 인자 형식, 위험 등급, 한도)은 모두 policy.json에 있다.
"""
import json
import os
import posixpath
import sys
import uuid
from datetime import datetime

POLICY = json.load(open("policy.json", encoding="utf-8"))
TYPES = {"str": str, "list": list}                 # policy.json의 형식 이름 → 파이썬 자료형


def fake_tool(tool, args):
    return f"{tool} 실행됨"                        # 실제로는 아무 일도 하지 않는다


def check(req, history):
    """(판정, 사유) — 판정은 허용 / 사후 검토 / 승인 대기 / 거부 / 중지
    검사 순서가 중요하다: 멈춰야 할 상황을 가장 먼저 보고, 그다음 권한 → 형식 → 범위 → 위험도 순으로 좁혀 간다.
    """
    tool, args = req["tool"], req["args"]
    # 6) 긴급 중지와 한도 (원칙 6)
    #    번호는 본문의 원칙 번호를 따랐다. 실행 자체를 멈추는 검사라 맨 앞에 둔다.
    if os.path.exists("STOP"):
        return "중지", "긴급 중지(STOP 파일)"      # 사람이 언제든 끌 수 있는 스위치(Kill Switch)
    if len(history) >= POLICY["limits"]["max_calls"]:
        return "중지", "호출 횟수 한도 초과"
    if history.count(json.dumps(req, sort_keys=True)) >= POLICY["limits"]["max_same_call"]:
        return "중지", "같은 호출 반복 한도 초과(루프 의심)"   # Agent가 같은 일을 끝없이 반복하는 사고를 막는다
    # 1) 작업 단위 권한 (원칙 1)
    #    이 작업(회의록 요약 후 메일)에 필요한 Tool만 허용한다. delete_file·db_query는 존재하지만 쓸 수 없다.
    if tool not in POLICY["allowed_tools"]:
        return "거부", f"이 작업에 허용되지 않은 Tool: {tool}"
    # 2) 인자 스키마 (원칙 2)
    #    인자 이름이 정확히 일치하고, 형식(문자열/목록)도 맞아야 한다. 예상 밖의 인자는 공격의 통로가 된다.
    spec = POLICY["tools"][tool]["args"]
    if set(args) != set(spec):
        return "거부", "인자 이름이 스키마와 다름"
    for name, typ in spec.items():
        if not isinstance(args[name], TYPES[typ]):
            return "거부", f"인자 형식 오류: {name}은(는) {typ}여야 함"
    # 3) 허용 범위: 경로는 작업 폴더 안, 메일은 사내 도메인만 (원칙 2)
    if "path" in args:
        # normpath로 "workspace/../etc/passwd" 같은 경로를 "etc/passwd"로 정리한 뒤 검사한다 (경로 조작 방지)
        norm = posixpath.normpath(args["path"])
        if not (norm + "/").startswith(POLICY["workspace"]):
            return "거부", f"작업 폴더 밖 경로: {norm}"
    if tool == "send_mail":
        outside = [t for t in args["to"] if not t.endswith("@" + POLICY["mail_domain"])]
        if outside:
            return "거부", f"사외 수신자: {', '.join(outside)}"   # 데이터 유출 경로 차단
    # 4) 위험 등급별 처리 (원칙 3)
    #    여기까지 왔으면 "해도 되는 일"이다. 남은 것은 사람이 얼마나 개입할지 정하는 것이다.
    if tool == "send_mail" and len(args["to"]) > POLICY["approval_needed"]["send_mail_recipients_over"]:
        return "승인 대기", f"수신자 {len(args['to'])}명 대량 발송은 사람 승인 필요"
    risk = POLICY["tools"][tool]["risk"]
    if risk == "높음":
        return "승인 대기", "되돌릴 수 없는 작업은 사람 승인 필요"
    if risk == "중간":
        return "사후 검토", "실행하고 검토 목록에 기록"
    return "허용", "읽기 작업"


def main():
    guard = "--no-guard" not in sys.argv
    trace = uuid.uuid4().hex[:8]                   # 이번 실행의 추적 번호 (9장 실습 1의 Trace ID와 같은 개념)
    requests = json.load(open("requests.json", encoding="utf-8"))
    history, log = [], open("agent_trace.jsonl", "a", encoding="utf-8")
    print(f"작업: {POLICY['task']}  (trace {trace}, {'검사함' if guard else '검사 없음'})")
    for i, req in enumerate(requests, 1):
        verdict, reason = check(req, history) if guard else ("허용", "검사 없음")
        # 허용·사후 검토만 실제로 실행한다. 승인 대기·거부·중지는 실행하지 않는다
        result = fake_tool(req["tool"], req["args"]) if verdict in ("허용", "사후 검토") else "-"
        history.append(json.dumps(req, sort_keys=True))   # 반복 호출 검사를 위해 모든 요청을 기억한다
        short = json.dumps(req["args"], ensure_ascii=False)[:48]
        print(f"{i:2} {req['tool']:10} {verdict:5}  {reason}  {short}")
        # 모든 판정을 기록한다 → 사고가 나면 "Agent가 무엇을 하려 했고 무엇이 막혔는지" 되짚을 수 있다
        log.write(json.dumps({"time": datetime.now().isoformat(timespec="seconds"), "trace": trace, "n": i,
                              "tool": req["tool"], "verdict": verdict, "reason": reason}, ensure_ascii=False) + "\n")
        if verdict == "중지":
            print("   → 이후 호출을 모두 멈춤")
            break


if __name__ == "__main__":
    main()
