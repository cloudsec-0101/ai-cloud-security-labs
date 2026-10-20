"""eol_check.py — 클라우드 관리형 서비스의 버전을 지원 종료 일정과 자동으로 대조한다 (9장 실습 3)

사용법: python3 eol_check.py <조회 결과 폴더> [--today YYYY-MM-DD] [--days 180]
  조회 결과 폴더에는 AWS CLI가 낸 JSON을 그대로 넣는다 (collect_aws.sh 참고).
    rds.json          aws rds describe-db-instances --output json
    elasticache.json  aws elasticache describe-cache-clusters --output json
    lambda.json       aws lambda list-functions --output json
    eks.json          aws eks describe-cluster --name <클러스터> --output json 을 클러스터마다 이어 붙인 것
  지원 종료 일정은 endoflife.date 공개 API에서 받는다(계정·키 필요 없음).
  긴급·위험 판정이 하나라도 있으면 종료 코드 1을 돌려준다(예약 실행·파이프라인에서 쓰기 위해).

관리형 서비스는 "패치는 클라우드가 해 준다"고 생각하기 쉽지만, 메이저 버전 선택과 업그레이드는 고객 몫이다(1장 공동 책임).
지원이 끝난 버전은 보안 패치가 더 나오지 않고, 연장 지원 비용이 붙거나 강제 업그레이드가 일어난다.
판정: 긴급(이미 종료) / 위험(--days 이내 종료) / 주의(자동 마이너 업그레이드 꺼짐) / 확인 필요 / 양호
"""
import json, os, sys, unicodedata, urllib.request
from datetime import date

API = "https://endoflife.date/api/{}.json"
# AWS의 엔진 이름 → endoflife.date의 제품 이름
PRODUCT = {"postgres": "amazon-rds-postgresql", "mysql": "amazon-rds-mysql", "mariadb": "amazon-rds-mariadb",
           "redis": "amazon-elasticache-redis", "eks": "amazon-eks", "lambda": "aws-lambda"}

def load(path):
    """JSON 하나 또는 여러 개가 이어 붙은 파일을 모두 읽는다."""
    if not os.path.exists(path):
        return []
    # raw_decode는 JSON 하나를 읽고 "어디까지 읽었는지"를 알려 준다 → 그 다음부터 다시 읽기를 반복한다
    text, dec, objs, i = open(path, encoding="utf-8").read(), json.JSONDecoder(), [], 0
    while i < len(text):
        if text[i].isspace():
            i += 1; continue
        obj, i = dec.raw_decode(text, i)
        objs.append(obj)
    return objs

def resources(folder):
    """네 가지 조회 결과에서 (이름, 서비스, 엔진, 버전, 자동 마이너 업그레이드 여부)를 하나씩 꺼낸다."""
    for d in load(os.path.join(folder, "rds.json")):
        for x in d.get("DBInstances", []):
            yield x["DBInstanceIdentifier"], "RDS " + x["Engine"], x["Engine"], x["EngineVersion"], x.get("AutoMinorVersionUpgrade")
    for d in load(os.path.join(folder, "elasticache.json")):
        for x in d.get("CacheClusters", []):
            yield x["CacheClusterId"], "ElastiCache " + x["Engine"], x["Engine"], x["EngineVersion"], x.get("AutoMinorVersionUpgrade")
    for d in load(os.path.join(folder, "eks.json")):
        c = d.get("cluster", d)
        yield c["name"], "EKS", "eks", c["version"], None          # EKS는 자동 마이너 업그레이드 개념이 없다
    for d in load(os.path.join(folder, "lambda.json")):
        for x in d.get("Functions", []):
            # 컨테이너 이미지로 배포한 함수는 Runtime이 없다. 이미지 안의 런타임은 실습 2처럼 이미지를 스캔해 확인한다
            yield x["FunctionName"], "Lambda", "lambda", x.get("Runtime") or "(컨테이너 이미지)", None

_cache = {}
def cycles(product):
    """제품의 지원 일정 목록을 받아 {버전: 일정} 사전으로 만든다. 같은 제품은 한 번만 내려받는다."""
    if product not in _cache:
        with urllib.request.urlopen(API.format(product), timeout=30) as r:
            _cache[product] = {c["cycle"]: c for c in json.load(r)}
    return _cache[product]

def find_cycle(product, version):
    """버전에 맞는 지원 일정을 찾는다. 자세한 버전부터 찾고, 없으면 한 단계씩 줄여 간다."""
    cs = cycles(product)
    parts = version.split(".")
    for n in range(len(parts), 0, -1):          # 13.20 → "13.20", "13" 순서로 찾는다
        key = ".".join(parts[:n])
        if key in cs:
            return cs[key]
    return None

def as_date(v):
    """날짜 문자열이면 date로 바꾼다. endoflife.date는 날짜 대신 true/false를 줄 때도 있어 그때는 None."""
    return date.fromisoformat(v) if isinstance(v, str) else None

def main():
    args = sys.argv[1:]
    folder = args[0] if args and not args[0].startswith("--") else "sample"   # 폴더를 생략하면 예시 데이터(sample)
    today = as_date(args[args.index("--today") + 1]) if "--today" in args else date.today()   # 기준일을 바꿔 미래를 시험해 볼 수 있다
    window = int(args[args.index("--days") + 1]) if "--days" in args else 180                  # 며칠 이내 종료를 "위험"으로 볼지
    rows, bad = [], 0
    for name, service, engine, version, auto_minor in resources(folder):
        product = PRODUCT.get(engine)
        if version.startswith("("):
            rows.append((name, service, version, "-", "-", "-", "확인 필요", "이미지 안의 런타임은 이미지 스캔으로 확인(8장 실습 1)")); continue
        c = find_cycle(product, version) if product else None
        if not c:
            rows.append((name, service, version, "-", "-", "-", "확인 필요", "지원 일정을 찾지 못함")); continue
        # 보안 패치가 끝나는 날 = support와 eol 중 이른 날
        #   Lambda: support = 런타임 지원 중단(보안 패치 끝), eol = 함수 수정까지 막히는 날
        #   RDS MySQL: support = 이 마이너 버전의 지원 종료, eol = 메이저 버전의 표준 지원 종료
        sup, eol = as_date(c.get("support")), as_date(c.get("eol"))
        ends = [d for d in (sup, eol) if d]
        end = min(ends) if ends else None
        ext = as_date(c.get("extendedSupport"))                     # 연장 지원(유료) 종료일
        left = (end - today).days if end else None                  # 남은 일수 (음수면 이미 지남)
        notes = []
        what = "표준 지원"
        if sup and eol and sup < eol:
            what = "런타임 지원" if engine == "lambda" else "마이너 버전 지원"
        # 판정: 이미 지났으면 긴급, window일 안에 끝나면 위험, 그 밖은 양호
        if end is None:
            verdict = "양호"; notes.append("종료일 미정")
        elif left < 0:
            verdict = "긴급"; notes.append(f"{what} 종료")
        elif left <= window:
            verdict = "위험"; notes.append(f"{what} {window}일 이내 종료")
        else:
            verdict = "양호"
        # 조치 방법 안내: 무엇을 하면 해결되는지(또는 무엇이 곧 막히는지) 비고에 적는다
        if end and left <= window:
            if engine == "lambda" and eol and eol > end:
                notes.append(f"{eol}부터 함수 수정 차단")
            elif what == "마이너 버전 지원":
                notes.append("마이너 업그레이드로 해결")
            elif ext and ext >= today:
                notes.append(f"연장 지원(추가 비용) {ext}까지")
        if auto_minor is False and verdict == "양호":
            verdict = "주의"          # 지금은 괜찮지만 마이너 보안 패치가 저절로 들어가지 않는다
        bad += verdict in ("긴급", "위험")
        am = "-" if auto_minor is None else ("켜짐" if auto_minor else "꺼짐")
        rows.append((name, service, version, str(end or "-"), "-" if left is None else str(left), am, verdict, ", ".join(notes)))
    # 급한 것부터 보이도록 정렬하고, 한글 폭을 고려해 표 모양으로 출력한다
    order = {"긴급": 0, "위험": 1, "주의": 2, "확인 필요": 3, "양호": 4}
    rows.sort(key=lambda r: (order[r[6]], r[0]))
    print(f"기준일 {today}, 지원 종료 {window}일 이내를 위험으로 표시 (출처: endoflife.date)")
    head = ("리소스", "서비스", "버전", "지원 종료일", "남은 일수", "자동 마이너", "판정", "비고")
    width = lambda s: sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in str(s))   # 한글은 2칸
    w = [max(width(r[i]) for r in rows + [head]) for i in range(7)]   # 열마다 가장 긴 값에 맞춘 폭
    for r in [head] + rows:
        print("  ".join(str(r[i]) + " " * (w[i] - width(r[i])) for i in range(7)) + "  " + r[7])
    print(f"\n총 {len(rows)}개, 긴급·위험 {bad}개 → {'조치 필요' if bad else '이상 없음'}")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
