"""merge_report.py — 여러 서버의 수집 결과를 하나로 합치고, 기준 버전 목록과 대조한다 (9장 실습 2)
사용법: python3 merge_report.py [수집 폴더] [기준 목록 CSV]

입력: inventories/inventory-*.json (collect_linux.sh, collect_windows.ps1의 결과)
      watchlist.csv (열: name_regex, min_version, reason — "이 SW는 이 버전 이상이어야 한다"는 기준)
출력: inventory-all.csv (모든 서버의 SW 목록을 한 표로. 엑셀로 열어 필터·검색할 수 있다)
      화면에 기준 버전 미달 목록
"""
import csv, glob, json, os, re, sys

inv_dir = sys.argv[1] if len(sys.argv) > 1 else "inventories"
watch = list(csv.DictReader(open(sys.argv[2] if len(sys.argv) > 2 else "watchlist.csv", encoding="utf-8")))


def vkey(v):
    """버전 문자열을 비교할 수 있는 숫자 목록으로 바꾼다 (예: 1:9.6p1-3ubuntu13.14 → [1,9,6,1,3,13,14])
    문자열 그대로 비교하면 "10.0" < "9.0"이 되어 버리므로 숫자끼리 비교해야 한다.
    배포판마다 버전 표기가 달라 완벽하지는 않다. 실무에서는 판정 결과를 사람이 한 번 더 확인한다."""
    return [int(x) for x in re.findall(r"\d+", v or "")]


rows, findings, hosts = [], [], {}       # rows: 통합 표, findings: 기준 미달, hosts: 호스트명 → machine_id 목록
for f in sorted(glob.glob(os.path.join(inv_dir, "inventory-*.json"))):
    d = json.load(open(f, encoding="utf-8-sig"))   # utf-8-sig: Windows PowerShell이 붙이는 BOM도 처리
    host, osname = d["host"], d["os"]["name"]
    hosts.setdefault(host, []).append(d.get("machine_id", "")[:8])
    pk = d.get("packages", [])
    up = {u["name"] for u in d.get("upgradable", [])}   # 업데이트 대기 패키지 이름 집합
    for p in pk:
        rows.append([host, d.get("machine_id", ""), osname, p["name"], p.get("version", ""), p.get("source", ""), "Y" if p["name"] in up else ""])
    # 기준 목록과 대조: 이름이 정규식에 맞고, 버전이 기준보다 낮으면 기록한다
    for w in watch:
        for p in pk:
            if re.search(w["name_regex"], p["name"], re.I) and p.get("version") and vkey(p["version"]) < vkey(w["min_version"]):
                findings.append((host, p["name"], p["version"], w["min_version"], w["reason"]))
    # 패키지 관리자 밖 SW와 그중 버전을 알 수 없는 것(숫자가 하나도 없는 버전)을 센다
    manual = [p for p in pk if p.get("source") in ("manual", "listening-process") or p.get("source", "").startswith("sbom-")]
    unknown = [p for p in manual if not re.search(r"\d", p.get("version") or "")]
    print(f"[{host} / {d.get('machine_id', '')[:8]}] {osname}")
    print(f"    SW {len(pk)}개 | 패키지 관리자 밖 {len(manual)}개(버전 확인 필요 {len(unknown)}개) | 업데이트 대기 {len(up)}개")

# 복제한 VM처럼 호스트명이 같은 서버가 여러 대면 알려 준다 (호스트명만으로 자산을 구분하면 안 되는 이유)
for h, ids in hosts.items():
    if len(ids) > 1:
        print(f"\n주의: 호스트명 {h}가 {len(ids)}대에서 겹칩니다 → machine_id({', '.join(ids)})로 구분합니다")

# utf-8-sig로 저장해야 엑셀에서 열 때 한글이 깨지지 않는다
with open("inventory-all.csv", "w", newline="", encoding="utf-8-sig") as fo:
    w = csv.writer(fo)
    w.writerow(["host", "machine_id", "os", "software", "version", "source", "upgradable"])
    w.writerows(rows)
print(f"\n통합 목록: inventory-all.csv ({len(rows)}행)")
print(f"기준 버전 미달: {len(findings)}건")
for h, n, v, m, r in findings:
    print(f"  - {h} | {n} {v} < {m} | {r}")
