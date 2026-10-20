"""Shadow AI 발견: 로그에 나타난 AI 사용을 AI 자산 등록 파일(허용 목록)과 대조합니다.

사용: python3 shadow_ai.py [--registry ../policy-as-code/registry/ai-assets.yaml]

읽는 것
  logs/proxy.csv          SASE·프록시가 남긴 웹 접속 기록 (tenant: 기업/개인 계정 구분)
  logs/mcp-gateway.jsonl  MCP Gateway를 지난 Agent의 Tool 호출 기록
  logs/db-access.csv      업무 DB 접근 기록
  catalog/ai-domains.csv  알려진 AI 서비스 도메인 (실무에서는 CASB·SASE의 AI 앱 카탈로그)
  cmdb/apps.csv           CMDB에 등록된 일반 업무 시스템
만드는 것
  out/shadow-report.md    발견 목록과 처리 제안 (처리 결정 칸은 담당자가 채움)
  out/candidates.yaml     등록 후보의 등록 파일 초안 (실습 1의 정책 검사로 이어짐)

Shadow AI = 회사가 승인·등록하지 않은 채 쓰이는 AI. 막는 것보다 "먼저 찾는 것"이 출발점이다.
세 가지 관측 지점에서 찾는다:
  ① 웹·SaaS   : 직원이 브라우저로 쓰는 AI 서비스 (개인 계정 사용, 대용량 업로드 포함)
  ② Agent·MCP : 등록되지 않은 Agent나 승인되지 않은 MCP Server 호출
  ③ 업무 DB   : CMDB에도 AI 자산 목록에도 없는 앱이 업무 DB에 붙어 있는 경우(현업이 만든 AI 앱)
"""
import argparse
import csv
import json
import os
import re
import unicodedata
from collections import defaultdict

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
# 카탈로그에 없는 주소라도, 경로가 LLM API의 모양(OpenAI·Anthropic·Ollama 형식)이면 AI 호출로 추정한다
LLM_API = re.compile(r"/v1/(chat/)?completions|/v1/messages|/api/(generate|chat)$")
BIG_UPLOAD = 1_000_000  # 1MB 이상 올렸으면 우선 확인


def load(args):
    """등록 파일(허용 목록), AI 도메인 카탈로그, CMDB 앱 목록을 읽는다."""
    reg = yaml.safe_load(open(args.registry, encoding="utf-8"))
    cat = list(csv.DictReader(open(os.path.join(HERE, "catalog/ai-domains.csv"), encoding="utf-8")))
    cmdb = {r["app_id"] for r in csv.DictReader(open(os.path.join(HERE, "cmdb/apps.csv"), encoding="utf-8"))}
    return reg, cat, cmdb


def match_catalog(host, cat):
    """접속한 호스트가 알려진 AI 서비스인지 찾는다. 하위 도메인도 포함(api.openai.com → openai.com)."""
    h = host.split(":")[0]                    # 포트 번호 제거
    for c in cat:
        if h == c["domain"] or h.endswith("." + c["domain"]):
            return c
    return None


def pad(s, width):
    """한글처럼 두 칸을 차지하는 글자를 세어 열을 맞춘다."""
    out, w = "", 0
    for ch in s:
        cw = 2 if unicodedata.east_asian_width(ch) in "WF" else 1
        if w + cw > width:
            break
        out += ch; w += cw
    return out + " " * (width - w)


def mb(n):
    """바이트 수를 읽기 쉬운 KB/MB로 바꾼다."""
    return f"{n / 1_000_000:.1f}MB" if n >= 100_000 else f"{n / 1000:.0f}KB"


def scan(reg, cat, cmdb):
    """세 가지 로그를 허용 목록과 대조해 발견 목록을 만든다. 각 발견에는 상태(승인/미등록 등)가 붙는다."""
    assets = [a for a in reg["assets"] if a.get("status") == "운영"]
    # 허용 목록을 빨리 찾을 수 있게 도메인·앱 ID·Agent ID별 사전으로 만들어 둔다
    by_domain = {d: a for a in assets for d in a.get("domains", [])}
    by_app = {a["app_id"]: a for a in assets if a.get("app_id")}
    by_agent = {a["agent_id"]: a for a in assets if a.get("agent_id")}
    mcp_ok = {m["host"]: m for m in reg.get("mcp_servers", []) if m.get("status") == "승인"}
    approved_categories = defaultdict(list)   # 용도별 승인 서비스 (미등록 AI를 쓰는 사람에게 "대신 이것을 쓰라"고 안내하기 위해)
    found = []

    # 1) 웹·SaaS (프록시 로그)
    groups = defaultdict(lambda: {"users": set(), "reqs": 0, "out": 0, "depts": set(), "domain": ""})
    total = ai = 0
    for r in csv.DictReader(open(os.path.join(HERE, "logs/proxy.csv"), encoding="utf-8")):
        total += 1
        c = match_catalog(r["host"], cat)
        if c is None and not LLM_API.search(r["path"]):
            continue                              # AI와 관계없는 접속은 건너뛴다
        ai += 1
        if c:
            dom = next((d for d in by_domain if r["host"] == d or r["host"].endswith("." + d)), None)
            asset = by_domain.get(dom)
            if asset and r["tenant"] == "개인":
                # 승인된 서비스라도 개인 계정이면 기업 계정의 보호(학습 제외, 감사 로그)가 적용되지 않는다
                status = "승인 서비스·개인 계정"
            elif asset:
                status = "승인"
                approved_categories[c["category"]].append(asset)
            else:
                status = "미등록 AI"
            # 승인된 사용은 서비스별로, 나머지는 부서별로 묶는다
            key = (status, c["service"], c["category"], "" if status == "승인" else r["dept"], asset["id"] if asset else "")
        else:
            key = ("카탈로그 밖 AI API", r["host"], "AI API(추정)", r["dept"], "")
        g = groups[key]
        g["users"].add(r["user"]); g["reqs"] += 1; g["out"] += int(r["bytes_out"]); g["depts"].add(r["dept"])
        g["domain"] = c["domain"] if c else ""
    for (status, svc, category, dept, aid), g in groups.items():
        found.append({"src": "웹·SaaS", "status": status, "what": svc + (f" ({aid})" if aid else ""), "category": category,
                      "dept": dept or (next(iter(g["depts"])) if len(g["depts"]) == 1 else f"{len(g['depts'])}개 부서"), "domain": g["domain"],
                      "asset": aid, "users": len(g["users"]), "reqs": g["reqs"], "out": g["out"]})

    # 2) Agent·MCP (MCP Gateway 로그)
    calls = defaultdict(lambda: {"reqs": 0, "tools": set(), "dept": ""})
    for line in open(os.path.join(HERE, "logs/mcp-gateway.jsonl"), encoding="utf-8"):
        x = json.loads(line)
        k = (x["agent_id"], x["mcp_host"])   # "어떤 Agent가 어떤 MCP Server를" 쌍으로 묶는다
        calls[k]["reqs"] += 1; calls[k]["tools"].add(x["tool"]); calls[k]["dept"] = x["dept"]
    for (agent, host), c in calls.items():
        a = by_agent.get(agent)
        if a and host in mcp_ok:
            status = "승인"
        elif a:
            status = "승인 Agent·미승인 MCP"
        else:
            status = "미등록 Agent" + ("" if host in mcp_ok else "·미승인 MCP")
        found.append({"src": "Agent·MCP", "status": status, "what": f"{agent} → {host}", "category": ", ".join(sorted(c["tools"])),
                      "dept": c["dept"], "asset": a["id"] if a else "", "users": 1, "reqs": c["reqs"], "out": 0})

    # 3) 업무 DB 연결 (DB 접근 로그)
    conns = defaultdict(lambda: {"reqs": 0, "accounts": set(), "dbs": set(), "src": set()})
    for r in csv.DictReader(open(os.path.join(HERE, "logs/db-access.csv"), encoding="utf-8")):
        k = r["client_app"]
        conns[k]["reqs"] += 1; conns[k]["accounts"].add(r["account"]); conns[k]["dbs"].add(r["db"]); conns[k]["src"].add(r["src_ip"])
    for app, c in conns.items():
        if app in cmdb:
            continue  # 일반 업무 시스템
        a = by_app.get(app)
        status = "승인" if a else "미등록 현업 앱"
        found.append({"src": "업무 DB", "status": status, "what": app, "category": "DB " + ",".join(sorted(c["dbs"])) + " / 계정 " + ",".join(sorted(c["accounts"])),
                      "dept": a["owner_dept"] if a else "확인 필요 " + ",".join(sorted(c["src"])), "asset": a["id"] if a else "", "users": 1, "reqs": c["reqs"], "out": 0})
    return found, total, ai, approved_categories


def suggest(f, approved_categories):
    """발견 하나에 (우선순위, 처리 제안)을 붙인다. 최종 결정은 담당자가 보고서의 '처리 결정' 칸에 적는다.
    처리 방향은 네 가지: 등록(정식 자산으로) / 대체(승인된 서비스로 안내) / 폐기·차단 / 예외(기한 지정)"""
    s = f["status"]
    if s == "승인":
        return "", ""
    if s == "승인 서비스·개인 계정":
        pri = "우선" if f["out"] >= BIG_UPLOAD else "보통"
        return pri, "대체: 기업 계정으로 전환 안내, 개인 계정 업로드는 DLP로 차단(10-3)" + (". 올린 내용 확인" if pri == "우선" else "")
    if s == "미등록 AI":
        alt = approved_categories.get(f["category"])
        if f["out"] >= BIG_UPLOAD:
            return "우선", f"올린 내용부터 확인(유출 여부), 그다음 {'승인된 ' + alt[0]['id'] + '로 대체' if alt else '등록 검토'}"
        if f["category"] == "모델 저장소":
            return "보통", "등록 검토: 내려받은 모델의 출처·서명 확인(7-3)"
        if alt:
            return "보통", f"대체: 같은 용도의 승인된 {alt[0]['id']} 안내"
        return "보통", "등록 검토: 업무에 필요하면 등록 후보로"
    if s == "카탈로그 밖 AI API":
        return "우선", "확인: 보안성 검토 없이 운영되는 AI 시스템. 담당자를 찾아 등록 후보로(9-2)"
    if s.startswith("미등록 Agent"):
        return "우선", "차단 후 등록 검토: MCP Gateway에서 차단, 담당 부서 확인"
    if s == "승인 Agent·미승인 MCP":
        return "우선", "차단: Tool 허용 목록 위반(실습 1의 [Tool] 위반과 같은 문제)"
    if s == "미등록 현업 앱":
        pri = "우선" if any(k in f["category"] for k in ("admin", "root")) else "보통"
        return pri, "등록 의무: 소유자 지정, 전용 계정·최소 권한(표 10-3)" + (", 공용 관리자 계정 회수" if pri == "우선" else "")
    return "보통", ""


def candidate(f, n):
    """발견 내용으로 등록 파일 항목의 초안을 만든다. 모르는 칸(책임자, 등급 등)은 비워 두어 정책 검사에서 드러나게 한다."""
    base = {"id": f"NEW-{n}", "name": "", "type": "", "status": "운영", "owner_dept": "", "accountable": "",
            "declared_grade": "", "data": {}, "controls": {}}
    if f["src"] == "웹·SaaS":
        if f["status"] == "카탈로그 밖 AI API":
            base.update(name=f"{f['dept']} 자체 모델 API", type="AI 서비스", owner_dept=f["dept"], endpoint=f["what"])
        else:
            base.update(name=f"{f['what']} ({f['dept']})", type=f["category"], owner_dept=f["dept"], domains=[f["domain"]])
    elif f["src"] == "Agent·MCP":
        base.update(name=f["what"].split(" → ")[0], type="Agent", owner_dept=f["dept"], agent_id=f["what"].split(" → ")[0])
    else:
        base.update(name=f["what"], type="현업 앱", app_id=f["what"])
    return base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", default=os.path.join(HERE, "../policy-as-code/registry/ai-assets.yaml"))
    args = ap.parse_args()
    reg, cat, cmdb = load(args)
    found, total, ai, approved_categories = scan(reg, cat, cmdb)
    order = {"웹·SaaS": 0, "Agent·MCP": 1, "업무 DB": 2}
    # 출처별로, 그 안에서는 승인 → 미승인, 업로드가 큰 순서로 정렬
    found.sort(key=lambda f: (order[f["src"]], f["status"] != "승인", -f["out"], f["what"]))
    for f in found:
        f["priority"], f["action"] = suggest(f, approved_categories)

    print(f"Shadow AI 발견 결과 (프록시 {total}건 중 AI {ai}건, 등록 자산 {len(reg['assets'])}개와 대조)")
    src = None
    for f in found:
        if f["src"] != src:
            src = f["src"]; print(f"\n[{src}]")
        size = f" 업로드 {mb(f['out'])}" if f["out"] else ""
        who = f"{f['users']}명 " if f["src"] == "웹·SaaS" else ""
        mark = "" if f["status"] == "승인" else ("  ◀ " + f["priority"])
        print(f"  {pad(f['status'], 24)} {pad(f['what'], 40)} {pad(f['dept'], 22)} {who}{f['reqs']}건{size}{mark}")
    shadow = [f for f in found if f["status"] != "승인"]
    print(f"\n허용 목록 밖 사용 {len(shadow)}건 (우선 {sum(f['priority'] == '우선' for f in shadow)}건) — 표 10-11 '미등록 AI·Agent 발견 건수'")

    # 보고서: 허용 목록 밖 사용만 표로 정리한다 (담당자가 처리 결정 칸을 채워 이력으로 남긴다)
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    with open(os.path.join(HERE, "out/shadow-report.md"), "w", encoding="utf-8") as w:
        w.write("# Shadow AI 발견과 처리\n\n| 우선 | 출처 | 상태 | 대상 | 부서 | 사용 | 처리 제안 | 처리 결정 (등록/대체/폐기·차단/예외+기한) |\n|---|---|---|---|---|---|---|---|\n")
        for f in shadow:
            use = f"{f['users']}명 {f['reqs']}건" + (f", 업로드 {mb(f['out'])}" if f["out"] else "")
            w.write(f"| {f['priority']} | {f['src']} | {f['status']} | {f['what']} | {f['dept']} | {use} | {f['action']} | |\n")
    # 등록 후보: 처리 제안이 "등록·확인·차단 후 등록 검토"인 것만 초안으로 만든다 (대체 대상은 등록하지 않는다)
    cands = [candidate(f, i + 1) for i, f in enumerate(x for x in shadow if x["action"].startswith(("등록", "확인", "차단 후")))]
    with open(os.path.join(HERE, "out/candidates.yaml"), "w", encoding="utf-8") as w:
        w.write("# 등록 후보 초안. 담당 부서와 함께 빈칸을 채운 뒤 등록 파일(assets:)에 옮기고 실습 1의 check.sh로 검사합니다.\n")
        yaml.safe_dump(cands, w, allow_unicode=True, sort_keys=False, default_flow_style=None)
    print("보고서 out/shadow-report.md, 등록 후보 초안 out/candidates.yaml " + f"({len(cands)}건)")


if __name__ == "__main__":
    main()
