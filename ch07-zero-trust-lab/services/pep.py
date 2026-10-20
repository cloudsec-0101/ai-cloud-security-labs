# ③ 컨트롤 계층(PEP): 모든 요청을 가로채 ② 정책 엔진에 묻고, 결정을 집행하고, ④를 위해 기록한다
# 주소 형식: http://localhost:8000/<앱 이름>/<경로>   예) /erp/home → erp 컨테이너의 /home
# PEP는 스스로 판단하지 않는다. 판단은 OPA(zt.rego)가 하고, PEP는 그 결정을 그대로 집행한다.
# 이렇게 나눠 두면 정책을 바꿀 때 PEP 코드를 고칠 필요가 없다.
import json, os, time, uuid
import httpx, jwt
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

ISSUER = os.environ["ISSUER"]
OPA_URL = os.environ["OPA_URL"]
jwks = jwt.PyJWKClient(os.environ["JWKS_URL"])   # Keycloak의 공개키를 받아 와 토큰 서명을 검증하는 도구
DEVICES = json.load(open("devices.json", encoding="utf-8"))   # MDM이 알려 주는 등록 기기 목록 역할
APPS = {"erp": "http://erp:9000", "aichat": "http://aichat:9000"}   # 앱 이름 → 내부망 주소
app = FastAPI()

def log(entry):
    """판단 결과를 한 줄씩 남긴다. detector.py가 이 파일을 읽어 위험 점수를 계산한다."""
    with open("/logs/access.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

@app.api_route("/{app_name}/{path:path}", methods=["GET", "POST"])
async def gateway(app_name: str, path: str, request: Request):
    trace = uuid.uuid4().hex[:8]          # 요청마다 추적 번호를 붙여, 로그와 응답을 서로 찾아볼 수 있게 한다
    entry = {"time": time.time(), "trace": trace, "app": app_name, "method": request.method,
             "device": request.headers.get("X-Device-Id", ""),
             "country": request.headers.get("X-Country", "KR")}   # 실습에서는 접속 국가를 헤더로 흉내 낸다

    # 1) 신원 확인: IdP(Keycloak)가 서명한 토큰인가?
    #    서명(RS256)·발급자(issuer)·만료 시간을 검사한다. 하나라도 틀리면 예외가 나서 401로 거절한다.
    try:
        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        claims = jwt.decode(token, jwks.get_signing_key_from_jwt(token).key,
                            algorithms=["RS256"], issuer=ISSUER, options={"verify_aud": False})
        # verify_aud=False: 실습을 단순하게 하려고 수신자(audience) 검사는 생략했다. 운영에서는 켠다.
    except Exception as e:
        log({**entry, "user": None, "decision": "DENY", "reasons": [f"인증 실패: {type(e).__name__}"]})
        return JSONResponse(status_code=401, content={"decision": "DENY", "reasons": ["인증 실패"], "trace": trace})
    entry["user"] = claims["preferred_username"]   # 토큰에 들어 있는 사용자 이름 (예: kim)

    # 2) 판단 요청: 신원 + 기기 상태 + 요청 내용을 정책 엔진(OPA)에 보낸다
    #    목록에 없는 기기는 "관리되지 않는 기기"로 취급한다
    device = DEVICES.get(entry["device"], {"managed": False})
    opa_input = {"user": entry["user"], "roles": claims.get("realm_access", {}).get("roles", []),
                 "app": app_name, "method": request.method, "device": device, "country": entry["country"]}
    async with httpx.AsyncClient() as c:
        d = (await c.post(OPA_URL, json={"input": opa_input})).json().get("result", {})
        # 정책이 결정을 내지 못하면(result 없음) d는 빈 값이 되고, allow가 없으므로 아래에서 차단된다 (기본 거부)

    # 3) 집행: 허용된 요청만 보호 대상 앱으로 전달한다
    if not d.get("allow") or app_name not in APPS:
        kind = "STEP_UP" if d.get("step_up") else "DENY"
        log({**entry, "decision": kind, "reasons": d.get("reasons", ["알 수 없는 앱"])})
        # 추가 인증 필요는 401(다시 인증하라), 차단은 403(권한 없음)으로 구분해 돌려준다
        return JSONResponse(status_code=401 if kind == "STEP_UP" else 403,
                            content={"decision": kind, "reasons": d.get("reasons"), "trace": trace})
    async with httpx.AsyncClient() as c:
        # 앱에는 원래 토큰 대신 "검증된 사용자 이름"과 추적 번호만 넘긴다
        r = await c.request(request.method, f"{APPS[app_name]}/{path}",
                            headers={"X-Verified-User": entry["user"], "X-Trace-Id": trace})
    log({**entry, "decision": "ALLOW", "reasons": []})
    return {"decision": "ALLOW", "trace": trace, "response": r.json()}
