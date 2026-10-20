# gate.py — 사용법: python3 gate.py scan-v1.json
# Trivy 스캔 결과(JSON)를 받아 "배포해도 되는가"를 판정하는 배포 게이트.
#   먼저: trivy image --quiet --severity HIGH,CRITICAL --format json -o scan-v1.json ai-serving:v1
#
# 왜 필요한가: 스캔하면 취약점이 수십~수백 건 나온다. 전부 막으면 배포를 할 수 없고, 전부 넘기면 스캔하는 의미가 없다.
# 그래서 "심각도(CVSS)"만 보지 않고 "실제로 악용되고 있는가(KEV)", "곧 악용될 가능성(EPSS)"을 함께 보고
# 정말 위험한 것만 차단한다.
#   KEV : 미국 CISA가 "실제 공격에 쓰인 것이 확인된" 취약점을 모은 목록
#   EPSS: FIRST가 매일 계산하는 "앞으로 30일 안에 악용될 확률"(0~1)
# 종료 코드: 차단할 것이 있으면 1, 없으면 0 → CI 파이프라인이 이 값을 보고 배포를 멈춘다.
import json, sys, urllib.request

KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
EPSS_URL = "https://api.first.org/data/v1/epss?cve="

def get_json(url):
    """URL에서 JSON을 받아 온다 (KEV 목록, EPSS 점수)."""
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)

# 1) Trivy 결과에서 취약점만 모은다
#    Results는 대상별(OS 패키지, Python 패키지 등) 묶음이고, 각 묶음 안에 Vulnerabilities 목록이 있다
scan = json.load(open(sys.argv[1], encoding="utf-8"))
vulns = {}
for res in scan.get("Results", []):
    for v in res.get("Vulnerabilities", []) or []:     # 취약점이 없는 묶음은 null이라 "or []"로 처리
        vulns[v["VulnerabilityID"]] = v          # 같은 CVE 중복 제거

# 2) KEV 목록을 받아 CVE 번호 집합으로 만든다
kev = {k["cveID"] for k in get_json(KEV_URL)["vulnerabilities"]}

# 3) EPSS 점수를 받아 온다
# EPSS는 한 번에 여러 CVE 조회 가능 (100개씩)
ids = [c for c in vulns if c.startswith("CVE-")]   # GHSA- 같은 다른 번호 체계는 EPSS에 없으므로 뺀다
epss = {}
for i in range(0, len(ids), 100):
    for row in get_json(EPSS_URL + ",".join(ids[i:i+100]))["data"]:
        epss[row["cve"]] = float(row["epss"])

def decide(cve, v):
    """취약점 하나의 판정과 이유를 돌려준다. 위에서부터 차례로 검사해 처음 맞는 판정을 쓴다."""
    fixed = bool(v.get("FixedVersion"))
    if cve in kev:
        return "차단", "KEV 등재 (실제 악용 확인)"           # 심각도와 관계없이 무조건 막는다
    if v["Severity"] == "CRITICAL" and epss.get(cve, 0) >= 0.1:
        return "차단", "CRITICAL + EPSS 높음"                # 치명적이고 악용 확률도 10% 이상
    if not fixed:
        # 고칠 버전이 아직 없으면 막아도 해결되지 않는다 → 영향 여부를 VEX로 기록하고 운영 단계에서 지켜본다
        return "통과(VEX)", "수정 버전 없음 — VEX 작성, 9-3 모니터링으로 인계"
    return "경고", "수정 버전 있음 — 다음 릴리스까지 조치"

rows = []
for cve, v in vulns.items():
    verdict, reason = decide(cve, v)
    # 출력 열: 판정 | CVE | 심각도 | EPSS | KEV 여부 | 패키지 | 설치 버전 | 수정 버전 | 이유
    rows.append((verdict, cve, v["Severity"], round(epss.get(cve, 0), 3), cve in kev,
                 v["PkgName"], v.get("InstalledVersion"), v.get("FixedVersion", "-"), reason))

# 차단 → 경고 → 통과 순서로, 같은 판정 안에서는 EPSS가 높은 것부터 보여 준다
order = {"차단": 0, "경고": 1, "통과(VEX)": 2}
for r in sorted(rows, key=lambda r: (order[r[0]], -r[3])):
    print(" | ".join(str(x) for x in r))

blocked = sum(1 for r in rows if r[0] == "차단")
print(f"\n총 {len(rows)}건, 차단 {blocked}건 → 배포 {'불가' if blocked else '가능'}")
sys.exit(1 if blocked else 0)
