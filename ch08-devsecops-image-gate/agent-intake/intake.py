"""Agent 구성요소(Skill, MCP Server) 반입 검사와 하네스 Drift 탐지(실습용 축소판).

사용법:
  python3 intake.py scan [폴더...]                          들여올 Skill·MCP Server를 검사해 차단/검토/통과 판정
  python3 intake.py lock 이름... --approved-by 사람          승인한 구성요소와 하네스를 해시로 고정(agent-lock.json)하고 AI-BOM(aibom.json)을 만든다
  python3 intake.py verify                                  지금 상태를 잠금 파일과 비교해 바뀐 것을 찾는다
차단 항목이 있거나(scan) 승인 뒤 바뀐 것이 있으면(verify) 종료 코드 1을 돌려준다 → 파이프라인이 멈출 수 있다(실습 1의 gate.py와 같다).

핵심 생각: Skill과 MCP Server는 "코드"이면서 동시에 모델이 읽는 "지시문"이다.
그래서 스크립트가 하는 일과 함께, 모델에게 보이는 글(SKILL.md 본문, Tool 설명)에 숨은 지시가 없는지도 본다.
검사 기준(승인 출처, 허용 Tool·네트워크·파일·환경변수)은 모두 intake-policy.json에 있다.
"""
import argparse
import difflib
import glob
import hashlib
import json
import os
import re
import sys
from datetime import datetime

POLICY = json.load(open("intake-policy.json", encoding="utf-8"))
LOCK = "agent-lock.json"

# 모델에게 보이는 글에서 찾을 "지시문" 모양. 정상 설명에는 잘 나오지 않는 표현들이다
INSTRUCTION = [r"(AI|비서|assistant|모델)에게", r"<IMPORTANT>", r"(사용자|user)에게(는)?.{0,12}(말하지|알리지|보여주지)",
               r"승인을 받을 필요가 없", r"(?i)ignore (all|previous)", r"이전 지시", r"함께 넣는다|넣어라"]
INVISIBLE = re.compile("[​-‏‪-‮⁠-⁤⁦-⁩﻿\U000e0000-\U000e007f]")
SECRET = r"~/\.ssh|~/\.aws|id_rsa|credentials|\.env\b|mcp\.json|최근에 연 파일"
NETWORK = r"\b(curl|wget|nc)\b|requests\.(get|post)|urllib"


def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


# ── 구성요소 읽기 ─────────────────────────────────────────────
def load(path):
    """Skill 폴더나 MCP Server 설명 파일을 같은 모양의 dict로 읽는다."""
    if os.path.isdir(path):                      # Skill: SKILL.md 앞머리(frontmatter) + 본문 + 스크립트
        md = open(os.path.join(path, "SKILL.md"), encoding="utf-8").read()
        front = dict(re.findall(r"^([\w-]+):\s*(.+)$", md.split("---")[1], re.M))
        files = sorted(f for f in glob.glob(os.path.join(path, "**", "*"), recursive=True) if os.path.isfile(f))
        return {"kind": "skill", "path": path, "name": front["name"], "version": front.get("version", "?"),
                "source": front.get("source", "?"), "prompt": md.split("---", 2)[2],
                "tools_req": [t.strip() for t in front.get("allowed-tools", "").split(",") if t.strip()],
                "scripts": {os.path.relpath(f, path): open(f, encoding="utf-8").read() for f in files if "scripts" in f},
                "files": {os.path.relpath(f, path).replace(os.sep, "/"): sha(open(f, "rb").read()) for f in files},
                "tools": {}, "permissions": {}}
    m = json.load(open(path, encoding="utf-8"))  # MCP Server: 출처, 요구 권한, tools/list가 돌려줄 Tool 목록
    return {"kind": "mcp-server", "path": path, "name": m["name"], "version": m["version"], "source": m["source"],
            "prompt": "\n".join(t["description"] for t in m["tools"]), "tools_req": [], "scripts": {},
            "files": {os.path.basename(path): sha(open(path, "rb").read())},
            "tools": {t["name"]: {"hash": sha(json.dumps([t["description"], t["inputSchema"]], ensure_ascii=False, sort_keys=True)),
                                  "description": t["description"]} for t in m["tools"]},
            "permissions": m["permissions"]}


def find(paths):
    out = []
    for p in paths:
        if os.path.isfile(p):                    # MCP Server 설명 파일 하나를 바로 줄 수도 있다
            out.append(p)
            continue
        out +=[os.path.dirname(f) for f in sorted(glob.glob(os.path.join(p, "**", "SKILL.md"), recursive=True))]
        out += sorted(glob.glob(os.path.join(p, "**", "*.json"), recursive=True))
    return out


# ── 검사 ─────────────────────────────────────────────────────
def check(c):
    """[(등급, 사유)] — 등급은 차단 / 검토. 아무것도 없으면 통과."""
    found = []
    # 1) 출처: 사내 레지스트리에 등록된 것만 (본문 "승인된 출처에서만")
    if not any(c["source"].startswith(s) for s in POLICY["approved_sources"]):
        found.append(("차단", f"승인되지 않은 출처: {c['source']}"))
    # 2) 모델에게 보이는 글에 숨은 지시문 (표 8-9 Tool Poisoning)
    if INVISIBLE.search(c["prompt"]):
        found.append(("차단", "보이지 않는 유니코드 문자"))
    for comment in re.findall(r"<!--(.*?)-->", c["prompt"], re.S):
        found.append(("검토", "HTML 주석(화면에는 안 보이고 모델에게는 보임)"))
        if any(re.search(p, comment) for p in INSTRUCTION):
            found.append(("차단", f"주석 속 지시문: {comment.strip()[:40]}…"))
    for name, t in c["tools"].items():
        hits = [p for p in INSTRUCTION if re.search(p, t["description"])]
        if hits:
            found.append(("차단", f"Tool 설명 속 지시문({name}): {re.search(hits[0], t['description']).group(0)}"))
    if re.search(SECRET, c["prompt"]):
        found.append(("차단", f"모델에게 비밀 파일을 읽게 함: {re.search(SECRET, c['prompt']).group(0)}"))
    # 3) 스크립트가 실제로 하는 일
    for f, code in c["scripts"].items():
        net, sec = re.search(NETWORK, code), re.search(SECRET, code)
        if net and sec:
            found.append(("차단", f"{f}: 비밀 파일({sec.group(0)})을 읽어 외부로 보냄({net.group(0)})"))
        elif net:
            found.append(("검토", f"{f}: 외부 통신({net.group(0)})"))
    # 4) 요구 권한이 허용 범위를 넘는가 (본문 "요구 권한 확인")
    extra = [t for t in c["tools_req"] if t not in POLICY["skill_allowed_tools"]]
    if extra:
        found.append(("검토", f"허용 범위 밖 Tool 요구: {', '.join(extra)}"))
    p = c["permissions"]
    for kind, allow in (("network", "network_allowlist"), ("files", "file_allowlist"), ("env", "env_allowlist")):
        extra = [v for v in p.get(kind, []) if v not in POLICY[allow]]
        if extra:
            found.append(("검토", f"허용 범위 밖 권한 {kind}: {', '.join(extra)}"))
    return found


def verdict(found):
    return "차단" if any(g == "차단" for g, _ in found) else "검토" if found else "통과"


def cmd_scan(paths):
    worst = 0
    for path in find(paths or ["incoming"]):
        c = load(path)
        found = check(c)
        v = verdict(found)
        worst = max(worst, ["통과", "검토", "차단"].index(v))
        print(f"{v:3}  {c['kind']:10} {c['name']} {c['version']}  ({c['source']})")
        for g, why in found:
            print(f"       - [{g}] {why}")
    return 1 if worst == 2 else 0


# ── 잠금과 AI-BOM ─────────────────────────────────────────────
def cmd_lock(names, approver):
    comps = {c["name"]: c for c in map(load, find(["incoming"]))}
    lock = {"locked_at": datetime.now().isoformat(timespec="seconds"), "components": {}, "harness": {}}
    for n in names:
        c = comps[n]
        found = check(c)
        if verdict(found) == "차단":
            print(f"잠금 거부: {n}은(는) 차단 판정입니다")
            return 1
        lock["components"][n] = {k: c[k] for k in ("kind", "path", "version", "source", "files", "tools", "permissions")}
        lock["components"][n].update(verdict=verdict(found), approved_by=approver)
        print(f"잠금: {c['kind']:10} {n} {c['version']}  (판정 {verdict(found)}, 승인 {approver})")
    for f in POLICY["harness_files"]:          # 하네스는 내용까지 저장해 두었다가 바뀐 줄을 보여 준다
        lock["harness"][f] = {"sha256": sha(open(f, "rb").read()), "text": open(f, encoding="utf-8").read()}
        print(f"잠금: {'harness':10} {f}")
    json.dump(lock, open(LOCK, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # AI-BOM: CycloneDX 형식으로 "이 Agent가 무엇으로 이루어졌나"를 남긴다(8-6)
    bom = {"bomFormat": "CycloneDX", "specVersion": "1.6",
           "metadata": {"timestamp": lock["locked_at"], "component": {"type": "application", "name": "업무 비서 Agent"}},
           "components": [{"type": "application", "name": n, "version": c["version"],
                           "hashes": [{"alg": "SHA-256", "content": sha(json.dumps(c["files"], sort_keys=True))}],
                           "externalReferences": [{"type": "distribution", "url": "https://" + c["source"]}],
                           "properties": [{"name": "aibom:kind", "value": c["kind"]},
                                          {"name": "aibom:approved-by", "value": c["approved_by"]},
                                          *({"name": "aibom:tool", "value": t} for t in c["tools"])]}
                          for n, c in lock["components"].items()]}
    json.dump(bom, open("aibom.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"→ {LOCK}, aibom.json 저장")
    return 0


def cmd_verify():
    lock = json.load(open(LOCK, encoding="utf-8"))
    changed = 0
    for n, old in lock["components"].items():
        if not os.path.exists(old["path"]):
            print(f"사라짐  {n}")
            changed += 1
            continue
        new, diffs = load(old["path"]), []
        for f in sorted(set(old["files"]) | set(new["files"])):
            if old["files"].get(f) != new["files"].get(f):
                diffs.append(f"파일 변경: {f}")
        for t in sorted(set(old["tools"]) | set(new["tools"])):
            if t not in old["tools"]:
                diffs.append(f"Tool 추가: {t}")
            elif t not in new["tools"]:
                diffs.append(f"Tool 삭제: {t}")
            elif old["tools"][t]["hash"] != new["tools"][t]["hash"]:
                diffs.append(f"Tool 설명·스키마 변경({t}): {new['tools'][t]['description'][:60]}…")
        for kind, vals in new["permissions"].items():
            extra = [v for v in vals if v not in old["permissions"].get(kind, [])]
            if extra:
                diffs.append(f"권한 추가 {kind}: {', '.join(extra)}")
        if diffs and new["version"] == old["version"]:
            diffs.append(f"버전은 그대로({old['version']})인데 내용이 바뀜 → 승인 뒤 몰래 바뀐 것(rug pull) 의심")
        print(f"{'변경' if diffs else '같음'}  {old['kind']:10} {n} {new['version']}")
        for d in diffs:
            print(f"       - {d}")
        changed += bool(diffs)
    for f, old in lock["harness"].items():
        text = open(f, encoding="utf-8").read()
        same = sha(text) == old["sha256"]
        print(f"{'같음' if same else '변경'}  {'harness':10} {f}")
        if not same:
            changed += 1
            for line in difflib.unified_diff(old["text"].splitlines(), text.splitlines(), lineterm="", n=0):
                if line[:1] in "+-" and line[:3] not in ("+++", "---"):
                    print(f"       {line}")
    # 하네스가 연결한 구성요소가 모두 잠금 파일에 있는가
    tools = json.load(open("harness/tools.json", encoding="utf-8"))
    for n in tools["skills"] + tools["mcp_servers"]:
        if n not in lock["components"]:
            print(f"미승인  {n}: 하네스에 연결되었지만 승인(잠금)된 적 없음")
            changed += 1
    print(f"\n결과: 승인된 상태와 다른 항목 {changed}개" + (" → 재승인 전까지 Agent 실행 중단" if changed else ""))
    return 1 if changed else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["scan", "lock", "verify"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--approved-by", default="")
    a = ap.parse_args()
    if a.cmd == "scan":
        sys.exit(cmd_scan(a.args))
    if a.cmd == "lock":
        if not a.approved_by:
            sys.exit("--approved-by로 승인한 사람을 적어야 합니다")
        sys.exit(cmd_lock(a.args, a.approved_by))
    sys.exit(cmd_verify())


if __name__ == "__main__":
    main()
