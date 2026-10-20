"""patch_cycle.py — 패치 → 확인 → 롤백, 그리고 Workaround를 하나의 순환으로 관리한다 (9장 실습 4)

사용법:
  python3 patch_cycle.py status                        서버별 실행 버전·헬스·취약 여부, 외부 경로, 티켓, Workaround
  python3 patch_cycle.py workaround on [--days 7]      공지의 임시 조치를 프록시에 적용하고 효과를 확인
  python3 patch_cycle.py workaround off                조치 확인이 끝난 뒤 Workaround를 해제
  python3 patch_cycle.py patch <버전> [--forget appN]   Canary → 전체 배포, 실패하면 자동 롤백, 끝나면 재수집·재점검으로 확인
                                                       (--forget: 그 서버는 "작업 완료"로만 보고되고 실제로는 재시작되지 않은 상황을 흉내 냄)
  python3 patch_cycle.py report                        조치 시간, 롤백, 확인 실패, Workaround 지표
  (init은 setup.sh가 실행한다)

이 실습에서 보려는 것은 "패치했다"는 보고가 아니라 "고쳐졌음을 확인했다"는 증거다.
  - 확인은 서버에 직접 다시 묻는다: 실행 중인 버전(/version), 정상 동작(/health), 공격이 통하는지(/admin/export)
  - 확인에 실패한 서버가 하나라도 있으면 티켓을 닫지 않는다
  - Workaround는 기한을 두고, 티켓이 종결된 뒤에만 해제할 수 있다
모든 일은 state/history.jsonl에 기록되고, report가 이 기록으로 조치 지표를 계산한다.
"""
import json, math, os, subprocess, sys, time, urllib.error, urllib.request
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
ST = os.path.join(BASE, "state")                # 티켓·Workaround·이력 파일을 두는 폴더
ADV = json.load(open(os.path.join(BASE, "advisory.json"), encoding="utf-8"))   # 보안 공지: 영향 버전, 수정 버전, 임시 조치
SERVERS = ["app1", "app2", "app3"]            # app1이 Canary
PORT = {"app1": 8081, "app2": 8082, "app3": 8083}
PROXY = "http://127.0.0.1:8080"


def now():
    return datetime.now().replace(microsecond=0)


def load(name, default):
    p = os.path.join(ST, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default


def save(name, obj):
    os.makedirs(ST, exist_ok=True)
    json.dump(obj, open(os.path.join(ST, name), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def log(event, **kw):
    os.makedirs(ST, exist_ok=True)
    with open(os.path.join(ST, "history.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"time": now().isoformat(), "event": event, **kw}, ensure_ascii=False) + "\n")


def get(url):
    """HTTP GET을 보내 (상태 코드, JSON)을 돌려준다. 서버가 꺼져 있으면 상태 코드는 None."""
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return None, {"error": type(e).__name__}


def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def inspect(s):
    """서버 하나를 다시 수집(실행 중인 버전)하고 다시 점검(공격 요청이 통하는지)한다."""
    base = f"http://127.0.0.1:{PORT[s]}"
    _, v = get(base + "/version")
    return {"version": v.get("version", "?"),
            "health": get(base + "/health")[0] == 200,
            "vulnerable": get(base + "/admin/export")[0] == 200}


def external_exposed():
    """외부(프록시)에서 공격 요청을 여러 번 보내, 한 번이라도 통하면 노출로 본다.
    프록시가 서버 3대에 번갈아 보내므로, 한 번만 보내면 안전한 서버에 걸려 노출을 놓칠 수 있다."""
    return any(get(PROXY + "/admin/export")[0] == 200 for _ in range(6))


def reload_proxy():
    """nginx 설정을 다시 읽게 한다 (Workaround 규칙 반영, 바뀐 서버 주소 반영)."""
    sh("docker", "exec", "proxy", "nginx", "-s", "reload")
    time.sleep(1)


def deploy(s, version):
    """서버 하나를 지정 버전으로 교체한다 (기존 컨테이너를 지우고 새 이미지로 다시 띄움)."""
    sh("docker", "rm", "-f", s)
    r = sh("docker", "run", "-d", "--name", s, "--network", "patchlab",
           "-p", f"127.0.0.1:{PORT[s]}:8000", f"lab-app:{version}")
    if r.returncode:
        sys.exit(r.stderr)
    for _ in range(20):                       # 새 컨테이너가 응답할 때까지 최대 10초 기다린다
        if get(f"http://127.0.0.1:{PORT[s]}/version")[0] == 200:
            break
        time.sleep(0.5)
    reload_proxy()


def health_ok(s):
    """헬스체크를 3번까지 시도한다 (막 뜬 서버가 잠깐 응답하지 못하는 경우를 실패로 오판하지 않게)."""
    for _ in range(3):
        if get(f"http://127.0.0.1:{PORT[s]}/health")[0] == 200:
            return True
        time.sleep(1)
    return False


def set_ticket(state, note=""):
    """패치 티켓의 상태를 바꾸고 이력에 남긴다."""
    t = load("ticket.json", {})
    t.update({"state": state, "updated": now().isoformat()})
    if note:
        t["note"] = note
    save("ticket.json", t)
    log("ticket", state=state, note=note)


def fixed(info):
    """조치 완료의 조건: 영향 버전이 아니고, 공격이 통하지 않고, 정상 동작한다. 셋 다 맞아야 한다."""
    return info["version"] not in ADV["affected"] and not info["vulnerable"] and info["health"]


# ---------- 명령 ----------
def cmd_init():
    """보안 공지를 받았다고 보고 패치 티켓을 연다. 이 시각이 조치 시간 측정의 출발점이다."""
    t = {"id": "T-0001", "advisory": ADV["id"], "title": ADV["title"], "target": ADV["fixed"],
         "opened": now().isoformat(), "state": "열림"}
    save("ticket.json", t)
    save("workarounds.json", [])
    log("advisory", id=ADV["id"])
    print(f"보안 공지 수신: {ADV['id']} {ADV['title']}")
    print(f"  영향 버전 {', '.join(ADV['affected'])}, 수정 버전 {ADV['fixed']}, 실제 악용 {'확인' if ADV['exploited'] else '미확인'}")
    print(f"  → 패치 티켓 {t['id']} 생성")


def cmd_status():
    """지금 상태를 한눈에: 서버별 실제 버전·헬스·취약 여부, 외부 노출, 티켓, Workaround 기한."""
    print("서버   실행 중 버전  헬스  내부 점검")
    for s in SERVERS:
        i = inspect(s)
        print(f"{s}   {i['version']:<12}  {'정상' if i['health'] else '실패'}  {'취약' if i['vulnerable'] else '안전'}")
    print(f"외부 경로(프록시): {'노출 — 공격 요청이 통함' if external_exposed() else '차단 — 공격 요청이 막힘'}")
    t = load("ticket.json", {})
    print(f"티켓 {t.get('id')}: {t.get('state')}")
    for w in load("workarounds.json", []):
        if w["released"]:
            print(f"Workaround {w['id']}: 해제됨 ({w['released'][11:]})")
        else:
            left = datetime.fromisoformat(w["expires"]) - now()
            print(f"Workaround {w['id']}: 적용 중, 만료 {w['expires'][:10]} ({'만료됨' if left.total_seconds() < 0 else f'{math.ceil(left.total_seconds() / 86400)}일 남음'})")


def cmd_workaround(args):
    """on: 공지의 임시 조치를 프록시에 넣고 효과를 확인한다 / off: 티켓 종결 뒤에만 해제한다."""
    ws = load("workarounds.json", [])
    if args[0] == "on":
        days = int(args[args.index("--days") + 1]) if "--days" in args else 7   # 임시 조치의 유효 기한
        # 공지에 적힌 nginx 차단 규칙을 workaround.conf에 쓰고 프록시를 다시 읽게 한다
        open(os.path.join(BASE, "proxy", "workaround.conf"), "w").write(ADV["workaround"]["nginx"] + "\n")
        reload_proxy()
        ok = not external_exposed()          # 적용만 하고 끝내지 않는다: 외부에서 실제로 막히는지 확인
        w = {"id": f"W-{len(ws) + 1:04d}", "ticket": "T-0001", "rule": ADV["workaround"]["description"],
             "applied": now().isoformat(), "expires": (now() + timedelta(days=days)).isoformat(),
             "verified": ok, "released": None}
        ws.append(w); save("workarounds.json", ws)
        log("workaround_on", id=w["id"], verified=ok)
        print(f"Workaround {w['id']} 적용: {w['rule']}")
        print(f"  효과 확인: 외부에서 공격 요청 → {'차단됨' if ok else '여전히 통함 (규칙을 다시 확인)'}")
        inner = [s for s in SERVERS if inspect(s)["vulnerable"]]
        print(f"  내부 점검: 서버 {len(inner)}대는 여전히 취약 ({', '.join(inner) or '없음'}) — 취약점 자체는 그대로")
        print(f"  기한: {w['expires'][:10]}까지 (패치 확인 뒤 해제)")
        if ok:
            set_ticket("Workaround 적용: 외부 경로 차단, 패치 대기")
    else:
        t = load("ticket.json", {})
        # 패치 확인 전에 임시 조치를 풀면 다시 노출된다 → 티켓이 종결된 경우에만 해제 허용
        if not t.get("state", "").startswith("종결"):
            sys.exit("패치 조치가 확인되기 전에는 Workaround를 해제할 수 없습니다.")
        open(os.path.join(BASE, "proxy", "workaround.conf"), "w").write("")
        reload_proxy()
        exposed = external_exposed()
        for w in ws:
            if not w["released"]:
                w["released"] = now().isoformat()
        save("workarounds.json", ws)
        log("workaround_off", exposed=exposed)
        print("Workaround 해제")
        print(f"  해제 뒤 외부에서 공격 요청 → {'통함! 다시 적용 필요' if exposed else '차단됨 (패치로 막힘)'}")


def cmd_patch(args):
    """Canary(app1)부터 한 대씩 배포 → 헬스체크 실패 시 롤백하고 중단 → 끝나면 모든 서버를 다시 점검."""
    ver = args[0]
    forget = args[args.index("--forget") + 1] if "--forget" in args else None
    before = {s: inspect(s)["version"] for s in SERVERS}   # 롤백할 때 되돌아갈 버전을 미리 기억
    log("patch_start", version=ver)
    print(f"패치 {ver} 배포 (Canary: {SERVERS[0]} → 나머지)")
    for s in SERVERS:
        if before[s] == ver:
            print(f"  {s}: 이미 {ver}, 건너뜀")
            continue
        if s == forget:
            # 실습용 상황: 담당자는 완료라고 보고했지만 실제로는 바뀌지 않았다 → 아래 확인 단계에서 드러난다
            print(f"  {s}: 작업 완료로 보고됨")
            log("deploy_reported", server=s, version=ver)
            continue
        deploy(s, ver)
        if health_ok(s):
            print(f"  {s}: {before[s]} → {ver} 배포, 헬스체크 통과")
            log("deploy", server=s, version=ver)
        else:
            print(f"  {s}: {ver} 배포 뒤 헬스체크 실패 → 자동 롤백")
            deploy(s, before[s])
            log("rollback", server=s, version=ver, back=before[s])
            print(f"  {s}: {before[s]}(으)로 되돌림, 헬스체크 {'통과' if health_ok(s) else '실패'}")
            print("  → 나머지 서버에는 배포하지 않음")   # Canary의 목적: 고장 난 패치가 전체로 퍼지기 전에 멈춘다
            set_ticket("롤백됨: 원인 확인 필요", f"{ver} 헬스체크 실패")
            print(f"티켓 T-0001: 롤백됨, 담당자에게 원인 확인 요청")
            return
    # 배포가 끝나도 바로 티켓을 닫지 않는다. 모든 서버에 다시 물어 실제 상태를 확인한다
    print("조치 결과 확인 (재수집·재점검)")
    fails = []
    for s in SERVERS:
        i = inspect(s)
        ok = fixed(i)
        if not ok:
            fails.append(s)
        print(f"  {s}: 실행 중 {i['version']}, 내부 점검 {'취약' if i['vulnerable'] else '안전'} → {'확인' if ok else '실패'}")
    log("verify", fails=fails)
    if fails:
        set_ticket("조치 미완료: 확인 실패 " + ", ".join(fails))
        print(f"티켓 T-0001: 닫지 않음 — 확인 실패 {', '.join(fails)}를 담당자에게 다시 배정")
    else:
        set_ticket("종결: 확인 완료")
        print("티켓 T-0001: 종결 (모든 서버 확인 완료). 이제 Workaround를 해제할 수 있음")


def cmd_report():
    """이력(history.jsonl)으로 조치 지표를 계산한다. 경영진·감사에 보고할 숫자가 여기서 나온다."""
    ev = [json.loads(l) for l in open(os.path.join(ST, "history.jsonl"), encoding="utf-8")]
    t = lambda e: datetime.fromisoformat(e["time"])
    # first: 조건에 맞는 첫 이벤트를 찾는다 (예: 처음으로 효과가 확인된 Workaround)
    first = lambda name, **kw: next((e for e in ev if e["event"] == name and all(e.get(k) == v for k, v in kw.items())), None)
    t0 = t(first("advisory"))
    wa = first("workaround_on", verified=True)
    closed = first("ticket", state="종결: 확인 완료")
    tries = [e for e in ev if e["event"] == "patch_start"]
    rolls = [e for e in ev if e["event"] == "rollback"]
    vfail = [e for e in ev if e["event"] == "verify" and e["fails"]]
    reported = sorted({e["server"] for e in ev if e["event"] == "deploy_reported"})
    ws = load("workarounds.json", [])
    open_ws = [w for w in ws if not w["released"]]
    expired = [w for w in open_ws if datetime.fromisoformat(w["expires"]) < now()]
    sec = lambda a, b: f"{int((b - a).total_seconds())}초"
    print("조치 지표 (이 실습은 초 단위로 진행했지만, 실무에서는 시간·일 단위로 잰다)")
    print(f"  공지 → Workaround 적용·효과 확인: {sec(t0, t(wa)) if wa else '없음'}")
    print(f"  공지 → 조치 확인 완료(티켓 종결): {sec(t0, t(closed)) if closed else '미완료'}")
    print(f"  패치 시도 {len(tries)}회, 자동 롤백 {len(rolls)}회")
    print(f"  확인 실패로 티켓을 닫지 못한 횟수: {len(vfail)}회 (완료 보고와 실제가 달랐던 서버: {', '.join(reported) or '없음'})")
    print(f"  해제되지 않은 Workaround: {len(open_ws)}건, 그중 기한이 지난 것: {len(expired)}건")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)              # 명령 없이 실행하면 맨 위의 사용법을 보여 준다
    # 첫 인자(명령 이름)에 맞는 함수를 골라 실행한다
    {"init": lambda: cmd_init(), "status": lambda: cmd_status(), "report": lambda: cmd_report(),
     "workaround": lambda: cmd_workaround(a[1:]), "patch": lambda: cmd_patch(a[1:])}[a[0]]()
