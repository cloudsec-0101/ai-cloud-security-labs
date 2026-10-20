#!/usr/bin/env bash
# collect_linux.sh — Ubuntu 서버의 OS와 설치 SW 버전을 자동 수집한다 (9장 실습 2)
# 사용법: sudo ./collect_linux.sh [출력 폴더]   (Ubuntu 20.04/22.04/24.04에서 확인)
#
# 취약점 공지가 나왔을 때 "우리 서버 중 어디에 그 SW가 있나?"에 바로 답하려면 SW 목록이 먼저 있어야 한다.
# 이 스크립트는 서버 한 대의 목록을 JSON 파일 하나로 만든다. 여러 서버의 결과는 merge_report.py로 합친다.
# 수집 대상: ① OS·커널 ② dpkg·snap 패키지 ③ 업데이트 대기 패키지 ④ 패키지 관리자 밖 실행 파일
#           ④-2 WAS·언어별 라이브러리(Trivy가 있을 때) ⑤ 실행 중인 컨테이너 이미지
set -u                                   # 정의되지 않은 변수를 쓰면 오류로 멈춘다 (오타로 빈 값이 들어가는 것을 막음)
OUT_DIR="${1:-./inventories}"; mkdir -p "$OUT_DIR"
# 결과 파일 이름에 호스트명과 machine-id 앞 8자리를 함께 넣는다 (호스트명이 같은 서버끼리 덮어쓰지 않게)
HOST=$(hostname); MID=$(cut -c1-8 /etc/machine-id 2>/dev/null); OUT="$OUT_DIR/inventory-$HOST-$MID.json"
TMP=$(mktemp -d)                         # 중간 결과를 모아 둘 임시 폴더 (마지막에 지운다)

# 1) OS와 커널, 자산 식별자(machine-id)
. /etc/os-release                        # PRETTY_NAME, VERSION_ID 같은 변수를 불러온다
cat /etc/machine-id > "$TMP/machine_id" 2>/dev/null

# 2) 패키지 관리자로 설치된 SW (dpkg, snap)
#    결과는 "이름<탭>버전<탭>출처" 형식의 TSV로 모은다
dpkg-query -W -f='${Package}\t${Version}\tdpkg\n' > "$TMP/pkgs.tsv"
command -v snap >/dev/null && snap list 2>/dev/null | awk 'NR>1{print $1"\t"$2"\tsnap"}' >> "$TMP/pkgs.tsv"

# 3) 업데이트가 밀린 패키지 (apt 기준, 보안 저장소 여부 포함)
#    apt list 결과 예: openssl/jammy-security 3.0.2-0ubuntu1.18 amd64 [upgradable from: ...]
#    → 이름, 새 버전, 저장소(jammy-security면 보안 업데이트)를 뽑는다
apt list --upgradable 2>/dev/null | awk -F'[/ ]' 'NR>1{print $1"\t"$3"\t"$2}' > "$TMP/upgradable.tsv"

# 4) 패키지 관리자 밖에 설치된 실행 파일 (/opt, /usr/local/bin) — 운영자가 직접 설치한 SW
#    출처를 모르는 파일을 버전 확인용으로 실행하지 않는다(root로 실행하면 그 자체가 공격 경로가 된다).
#    경로, SHA-256, 수정 시각만 기록하고, 버전은 경로 이름에 들어 있을 때만 추출한다.
find /opt /usr/local/bin -maxdepth 3 -type f -perm -u+x 2>/dev/null | while read -r f; do
  dpkg -S "$f" >/dev/null 2>&1 && continue        # dpkg가 아는 파일(패키지 소속)이면 건너뛴다
  v=$(echo "$f" | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)*' | tail -1)   # 예: /opt/app-2.4.1/bin/run → 2.4.1
  printf '%s\t%s\tmanual\t%s\t%s\t%s\n' "$(basename "$f")" "${v:-확인 필요}" "$f" \
    "$(sha256sum "$f" | cut -c1-16)" "$(date -r "$f" +%F)" >> "$TMP/manual.tsv"
done

# 4-2) 웹 서버·WAS·언어별 패키지(pip, npm, Maven 등)처럼 OS 패키지 관리자 밖에 설치된 SW의 버전
#      Trivy가 있으면 후보 폴더를 파일 시스템 SBOM 스캔으로 검사한다. 실행하지 않고
#      JAR의 MANIFEST·pom.properties, Python의 dist-info, Node의 package.json, Go 빌드 정보를 읽는다.
if command -v trivy >/dev/null; then
  for d in /opt /srv /usr/local /var/www; do
    [ -d "$d" ] || continue                       # 없는 폴더는 건너뛴다
    trivy rootfs --quiet --list-all-pkgs --format json -o "$TMP/sbom-$(basename "$d").json" "$d" >/dev/null 2>&1
  done
fi

# 5) 실행 중인 컨테이너 이미지 (Docker가 있는 경우)
command -v docker >/dev/null && docker ps --format '{{.Image}}' 2>/dev/null | sort -u > "$TMP/containers.txt"

# 6) 위에서 모은 TSV·JSON을 Python으로 합쳐 JSON 결과 파일 하나로 만든다
#    인자: 임시 폴더, 결과 파일, 호스트명, OS 이름, OS 버전, 커널 버전
python3 - "$TMP" "$OUT" "$HOST" "$PRETTY_NAME" "$VERSION_ID" "$(uname -r)" <<'PY'
import json, sys, os, datetime
tmp, out, host, pretty, ver, kernel = sys.argv[1:7]
def tsv(name):
    """임시 폴더의 TSV 파일을 줄마다 탭으로 나눠 읽는다. 파일이 없으면 빈 목록."""
    p = os.path.join(tmp, name)
    return [l.rstrip('\n').split('\t') for l in open(p)] if os.path.exists(p) else []
# 패키지 관리자(dpkg·snap) 목록 + 직접 설치한 실행 파일 목록
pk = [{"name": a[0], "version": a[1], "source": a[2]} for a in tsv("pkgs.tsv")]
pk += [{"name": a[0], "version": a[1], "source": "manual", "path": a[3], "sha256": a[4], "modified": a[5]} for a in tsv("manual.tsv")]
import glob
# Trivy SBOM 결과에서 패키지를 꺼낸다 (source 예: sbom-jar, sbom-python-pkg)
for f in glob.glob(os.path.join(tmp, "sbom-*.json")):
    for r in json.load(open(f)).get("Results", []):
        for p in r.get("Packages") or []:
            pk.append({"name": p["Name"], "version": p.get("Version") or "확인 필요", "source": "sbom-" + r.get("Type", ""),
                       "path": p.get("FilePath") or r.get("Target", "")})
# SBOM으로 버전이 확인된 설치 폴더(예: /opt/tomcat) 안의 실행 파일은 그 SW의 일부이므로 따로 세지 않는다
roots = set()
for f in glob.glob(os.path.join(tmp, "sbom-*.json")):
    base = "/" + os.path.basename(f)[5:-5]          # 파일 이름 sbom-opt.json → 스캔한 폴더 /opt
    for r in json.load(open(f)).get("Results", []):
        for p in r.get("Packages") or []:
            fp = p.get("FilePath") or ""
            if fp:
                roots.add(os.path.join(base, fp.split("/")[0]))   # 예: /opt + tomcat/lib/... → /opt/tomcat
pk = [p for p in pk if not (p["source"] == "manual" and any(p["path"].startswith(r + "/") for r in roots))]
cont = open(os.path.join(tmp, "containers.txt")).read().split() if os.path.exists(os.path.join(tmp, "containers.txt")) else []
up = [{"name": a[0], "candidate": a[1], "repo": a[2]} for a in tsv("upgradable.tsv")]
mid = open(os.path.join(tmp, "machine_id")).read().strip() if os.path.exists(os.path.join(tmp, "machine_id")) else ""
data = {"host": host, "machine_id": mid, "collected_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "os": {"name": pretty, "version": ver, "kernel": kernel},
        "packages": pk, "upgradable": up, "containers": cont}
json.dump(data, open(out, "w"), ensure_ascii=False, indent=1)
# 화면에는 출처별 개수만 요약해 보여 준다
n = lambda s: sum(1 for p in pk if p["source"] == s)
print(f"수집 완료: {host} | {pretty} (커널 {kernel})")
sb = sum(1 for p in pk if p["source"].startswith("sbom-"))
print(f"  dpkg {n('dpkg')}개 | snap {n('snap')}개 | 패키지 관리자 밖 실행 파일 {n('manual')}개 | SBOM 스캔(WAS·pip 등) {sb}개")
print(f"  업데이트 대기 {len(up)}개 | 컨테이너 {len(cont)}개")
print(f"  결과 파일: {out}")
PY
rm -rf "$TMP"                            # 임시 폴더 정리
