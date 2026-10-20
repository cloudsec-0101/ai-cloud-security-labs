# ④ 위험 탐지 계층: 접근 로그를 계속 읽어 사용자별 위험 점수를 계산하고, 정책 엔진에 되돌려 준다
# 동작: 3초마다 /logs/access.jsonl(pep.py가 쓰는 로그)을 읽고 → 사용자별 점수를 매기고
#       → 점수가 바뀐 사용자만 OPA의 data.risk에 써 넣는다. zt.rego는 다음 요청부터 이 점수를 본다.
# 실무의 UEBA·SIEM 상관분석을 아주 작게 줄인 것이다. 로그 확인: docker compose logs -f detector
import json, os, time, collections
import httpx

OPA_DATA = os.environ["OPA_DATA"]   # 예: http://opa:8181/v1/data/risk
LOG = "/logs/access.jsonl"
WINDOW = 300            # 최근 5분만 본다 (시간이 지나면 점수는 자연히 내려간다)

def score_users(events):
    """사용자별로 이벤트를 모아 위험 점수(0~100)와 그 이유를 계산한다."""
    by_user = collections.defaultdict(list)
    for e in events:
        if e.get("user"):                                       # 인증에 실패한 요청은 사용자를 알 수 없어 뺀다
            by_user[e["user"]].append(e)
    scores, why = {}, {}
    for user, evs in by_user.items():
        s, w = 0, []                                            # s: 점수, w: 점수를 준 이유
        countries = {e["country"] for e in evs}
        if len(countries) > 1:                                  # 불가능한 이동: 5분 안에 두 나라
            s += 50; w.append(f"5분 내 여러 국가 접속 {sorted(countries)}")
        denies = sum(e["decision"] == "DENY" for e in evs)
        if denies:                                              # 거부가 반복되면 정찰·무차별 시도로 본다
            s += min(denies * 15, 45); w.append(f"최근 거부 {denies}회")   # 1회당 15점, 최대 45점
        scores[user], why[user] = min(s, 100), w                # 합계는 100점을 넘지 않게
    return scores, why

last = {}                                                       # 직전에 OPA에 보낸 점수 (바뀐 것만 보내기 위해)
while True:
    now = time.time()
    events = []
    if os.path.exists(LOG):
        with open(LOG, encoding="utf-8") as f:
            # 한 줄에 JSON 하나. 5분(WINDOW)이 지난 기록은 버린다
            events = [e for e in map(json.loads, f) if now - e["time"] < WINDOW]
    scores, why = score_users(events)
    # 이번에 점수가 생긴 사용자 + 예전에 점수가 있던 사용자 모두 확인 (점수가 0으로 돌아간 경우도 반영)
    for user in set(last) | set(scores):
        s = scores.get(user, 0)
        if last.get(user) != s:
            httpx.put(f"{OPA_DATA}/{user}", json=s)            # ② 정책 엔진으로 피드백
            print(f"[detector] {user}: 위험 점수 {last.get(user, 0)} → {s}  {why.get(user, [])}")
            last[user] = s
    time.sleep(3)
