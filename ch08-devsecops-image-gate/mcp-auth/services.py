"""MCP가 MCP를 부르는 구조에서 호출받는 쪽이 호출자를 확인하는 실습(실습용 축소판). 표준 라이브러리만 쓴다.

  사용자 김대리 ─▶ Agent(report-agent) ─▶ MCP A(docs-hub) ─▶ MCP B(crm-mcp)
                                          A는 B를 부르는 MCP Client이기도 하다

- 인가 서버(AS): Client가 자기 키로 신원을 증명하면(client assertion) 토큰을 발급하고, 토큰 교환(RFC 8693)을 해 준다
- MCP A: search_docs, crm_summary(안에서 MCP B의 crm_read를 부른다)
- MCP B: crm_read

MCP Server(A, B)의 검사 수준은 MODE로 바꾼다(lab.py가 정한다).
  bearer  토큰의 서명·만료와 범위만 본다. "누가 내민 토큰인가"는 보지 않는다. A는 받은 토큰을 B에 그대로 넘긴다
  secure  호출받는 쪽이 부른 Client까지 확인한다
          ① 대상(aud)이 나인가 ② 토큰을 받은 Client가 직접 보냈는가(소유 증명)
          ③ 그 Client가 나를 부르도록 승인되었는가 ④ 범위(scope)
          A는 B를 부를 때 자기 신원으로 토큰을 교환하므로, 위임 경로(act)가 B용 토큰에 남는다

실습을 위한 단순화: 모든 서명이 HMAC(HS256)이라 Client 키를 등록부(CLIENT_KEYS)에 함께 둔다.
실제로는 각 Client가 개인키를 혼자 갖고 공개키만 등록하며(private_key_jwt),
소유 증명은 DPoP(RFC 9449)나 mTLS 인증서에 토큰을 묶는 방식(RFC 8705)을 쓴다.
MCP의 initialize 같은 연결 절차도 생략하고 tools/call만 흉내 낸다.
"""
import base64
import hashlib
import hmac
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import error, parse, request

AS_KEY = b"lab-as-signing-key"                     # 인가 서버의 토큰 서명 키
CLIENT_KEYS = {                                    # Client 등록부: 인가 서버에 등록된 Client와 그 키
    "report-agent": b"key-report-agent",           # 보고서 작성 Agent. MCP A를 부르도록 승인됨
    "shadow-agent": b"key-shadow-agent",           # 인가 서버에 등록은 됐지만 MCP A에는 승인되지 않은 Agent
    "docs-hub":     b"key-docs-hub",               # MCP A 자신. B를 부를 때 이 신원을 쓴다
}
USERS = {"kim": "docs:read crm:read crm:write"}    # 사용자에게 허락된 범위

HOST = "127.0.0.1"
AS_URL, A_URL, B_URL = (f"http://{HOST}:{p}" for p in (18080, 18081, 18082))
# 토큰의 aud(이 토큰을 받을 대상)에 넣는 식별자. MCP 사양은 MCP Server의 정식 URI를 쓰게 한다
A_RESOURCE = "https://docs-hub.hanbit.example/mcp"
B_RESOURCE = "https://crm-mcp.hanbit.example/mcp"
SERVER_CLIENT = {A_RESOURCE: "docs-hub"}           # 이 MCP Server가 다른 곳을 부를 때 쓰는 Client 신원
TOKEN_EXCHANGE = "urn:ietf:params:oauth:grant-type:token-exchange"
MODE = "secure"


def now():
    return int(time.time())


# ---------- 토큰(JWT) ----------

def b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign(claims, key):
    head = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = b64(json.dumps(claims, ensure_ascii=False).encode())
    sig = b64(hmac.new(key, f"{head}.{body}".encode(), hashlib.sha256).digest())
    return f"{head}.{body}.{sig}"


def peek(token):
    """서명을 확인하기 전에 내용만 읽는다(누구의 키로 확인할지 정할 때만 쓴다)"""
    try:
        return json.loads(unb64(token.split(".")[1]))
    except (IndexError, ValueError):
        raise ValueError("토큰 형식 오류")


def verify(token, key):
    """서명과 만료를 확인하고 클레임을 돌려준다. 대상·Client·범위는 받는 쪽이 따로 확인해야 한다"""
    claims = peek(token)
    head, body, sig = token.split(".")
    good = b64(hmac.new(key, f"{head}.{body}".encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, good):
        raise ValueError("서명 불일치")
    if claims["exp"] < now():
        raise ValueError("만료")
    return claims


def path(claims):
    """토큰의 위임 경로: 사용자 → 첫 Client → … → 지금 부르는 Client"""
    actors, act = [], claims.get("act")
    while act:                                     # act는 바깥쪽이 지금 부르는 쪽, 안쪽으로 갈수록 앞선 쪽
        actors.append(act["sub"])
        act = act.get("act")
    return [claims["sub"]] + (list(reversed(actors)) or [claims["azp"]])


# ---------- HTTP 공통 ----------

def http(url, data, headers=None, form=False):
    """POST를 보내고 (상태 코드, JSON 본문)을 돌려준다"""
    headers = dict(headers or {})
    if form:
        body, headers["Content-Type"] = parse.urlencode(data).encode(), "application/x-www-form-urlencoded"
    else:
        body, headers["Content-Type"] = json.dumps(data).encode(), "application/json"
    try:
        with request.urlopen(request.Request(url, data=body, headers=headers), timeout=5) as r:
            return r.status, json.loads(r.read())
    except error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def send_json(handler, status, obj, headers=None):
    body = json.dumps(obj, ensure_ascii=False).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    for k, v in (headers or {}).items():
        handler.send_header(k, v)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Quiet(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass                                       # 서버 콘솔 출력을 끈다

    def read_body(self):
        return self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()

    def bearer(self):
        auth = self.headers.get("Authorization", "")
        return auth[7:] if auth.startswith("Bearer ") else None


# ---------- MCP Client 쪽 동작 ----------

class Client:
    """MCP Client: 자기 키로 신원을 증명하고, 토큰을 받아 Tool을 부른다. Agent도, B를 부르는 A도 Client다"""

    def __init__(self, cid):
        self.cid, self.key = cid, CLIENT_KEYS[cid]

    def assertion(self):
        # 인가 서버에 "나는 cid다"를 증명하는 1분짜리 JWT. 비밀번호(client_secret)를 보내지 않는다
        return sign({"iss": self.cid, "sub": self.cid, "aud": AS_URL + "/token",
                     "exp": now() + 60, "jti": uuid.uuid4().hex}, self.key)

    def proof(self, url):
        # 요청마다 새로 만드는 소유 증명: "이 토큰을 받은 Client가 지금 이 주소로 보낸다"
        return sign({"htm": "POST", "htu": url, "exp": now() + 60, "jti": uuid.uuid4().hex}, self.key)

    def get_token(self, sub, aud, scope):
        return http(AS_URL + "/token", {"grant_type": "lab_issue", "client_assertion": self.assertion(),
                                        "sub": sub, "aud": aud, "scope": scope}, form=True)

    def exchange(self, subject_token, aud, scope):
        return http(AS_URL + "/token", {"grant_type": TOKEN_EXCHANGE, "client_assertion": self.assertion(),
                                        "subject_token": subject_token, "audience": aud, "scope": scope}, form=True)

    def call(self, url, token, tool, prove=True):
        headers = {"Authorization": "Bearer " + token}
        if prove:
            headers["DPoP"] = self.proof(url)
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tool, "arguments": {}}}
        return http(url, msg, headers)


# ---------- 인가 서버 ----------

class AuthServer(Quiet):
    def do_POST(self):
        f = {k: v[0] for k, v in parse.parse_qs(self.read_body()).items()}
        try:
            cid = self.client_id(f.get("client_assertion", ""))
        except (ValueError, KeyError) as e:
            return send_json(self, 401, {"error": "invalid_client", "error_description": str(e)})
        if f.get("grant_type") == "lab_issue":
            # 실습용: 사용자가 이 Client로 로그인해 동의한 결과라고 가정한다(실제로는 Authorization Code + PKCE)
            scope = set(f["scope"].split()) & set(USERS[f["sub"]].split())
            return self.issue({"sub": f["sub"], "aud": f["aud"], "azp": cid, "scope": " ".join(sorted(scope))}, cid)
        if f.get("grant_type") == TOKEN_EXCHANGE:
            try:
                subject = verify(f["subject_token"], AS_KEY)
            except ValueError as e:
                return send_json(self, 400, {"error": "invalid_grant", "error_description": str(e)})
            if SERVER_CLIENT.get(subject["aud"]) != cid:   # 자기에게 온 토큰만 바꿀 수 있다
                return send_json(self, 400, {"error": "invalid_grant", "error_description": "이 Client가 받은 토큰이 아님"})
            scope = set(f["scope"].split()) & set(subject["scope"].split())   # 위임할 때마다 범위는 좁아지기만 한다
            if not scope:
                return send_json(self, 400, {"error": "invalid_scope", "error_description": "받은 토큰에 없는 범위"})
            # 위임 경로를 쌓는다: 지금 부르는 쪽(cid)이 바깥, 앞서 부른 쪽이 안쪽
            prev = {"sub": subject["azp"], **({"act": subject["act"]} if "act" in subject else {})}
            return self.issue({"sub": subject["sub"], "aud": f["audience"], "azp": cid,
                               "scope": " ".join(sorted(scope)), "act": {"sub": cid, "act": prev}}, cid)
        send_json(self, 400, {"error": "unsupported_grant_type"})

    def client_id(self, assertion):
        cid = peek(assertion)["iss"]                 # 누구라고 주장하는지 읽고, 그 Client의 키로 확인한다
        claims = verify(assertion, CLIENT_KEYS[cid])
        if claims["aud"] != AS_URL + "/token":
            raise ValueError("다른 곳에 쓰려던 assertion")
        return cid

    def issue(self, claims, cid):
        # cnf: 이 토큰은 cid의 키를 가진 쪽만 쓸 수 있다(소유 증명과 짝을 이룬다)
        claims.update({"cnf": {"kid": cid}, "iat": now(), "exp": now() + 300})
        send_json(self, 200, {"access_token": sign(claims, AS_KEY), "token_type": "DPoP"})


# ---------- MCP Server ----------

SEEN_PROOFS = set()                                # 한 번 쓴 소유 증명은 다시 받지 않는다


class McpServer(Quiet):
    url = resource = None
    allowed_clients, tools = set(), {}

    def do_POST(self):
        msg = json.loads(self.read_body())
        tool = msg["params"]["name"]
        claims, err = self.authenticate(self.tools[tool][0])
        if err:
            status, challenge, reason = err
            return send_json(self, status, {"error": reason}, {"WWW-Authenticate": challenge})
        text, ok = self.tools[tool][1](self, claims)
        send_json(self, 200, {"jsonrpc": "2.0", "id": msg.get("id"),
                              "result": {"content": [{"type": "text", "text": text}], "isError": not ok}})

    def authenticate(self, need):
        """(클레임, None) 또는 (None, (상태 코드, WWW-Authenticate, 사유))"""
        token = self.bearer()
        if not token:
            return None, (401, f'Bearer resource_metadata="{self.url}/.well-known/oauth-protected-resource"', "토큰 없음")
        try:
            c = verify(token, AS_KEY)
        except ValueError as e:
            return None, (401, 'Bearer error="invalid_token"', f"토큰 {e}")
        if MODE == "secure":
            # ① 대상: 다른 Server용으로 발급된 토큰은 서명이 맞아도 받지 않는다
            if c["aud"] != self.resource:
                return None, (401, 'Bearer error="invalid_token"', f"이 Server용 토큰이 아님(aud={c['aud']})")
            # ② 소유 증명: 토큰이 묶인 Client(cnf)의 키로 이 요청에 서명한 증명이 함께 와야 한다
            proof = self.headers.get("DPoP")
            if not proof:
                return None, (401, 'DPoP error="invalid_dpop_proof"', "소유 증명 없음(토큰만 가진 쪽)")
            try:
                p = verify(proof, CLIENT_KEYS[c["cnf"]["kid"]])
            except ValueError:
                return None, (401, 'DPoP error="invalid_dpop_proof"', "소유 증명이 토큰의 Client와 다름")
            if p["htu"] != self.url or p["jti"] in SEEN_PROOFS:
                return None, (401, 'DPoP error="invalid_dpop_proof"', "다른 주소용이거나 재사용된 증명")
            SEEN_PROOFS.add(p["jti"])
            # ③ 호출 Client: 토큰을 받은 Client(azp)가 이 Server를 부르도록 승인되었는가
            if c["azp"] not in self.allowed_clients:
                return None, (403, 'Bearer error="insufficient_scope"', f"이 Server에 승인되지 않은 Client: {c['azp']}")
        # ④ 범위: 이 Tool에 필요한 권한이 토큰에 있는가
        if need not in c["scope"].split():
            return None, (403, f'Bearer error="insufficient_scope", scope="{need}"', f"범위 부족(필요: {need})")
        return c, None


def search_docs(server, c):
    return f"사내 문서 검색 실행됨(사용자: {c['sub']})", True


def crm_summary(server, c):
    """MCP A가 MCP Client가 되어 MCP B를 부른다. 어떤 토큰으로 부르는지가 두 모드의 차이다"""
    hub, token = Client("docs-hub"), server.bearer()
    if MODE == "secure":
        # 받은 토큰을 넘기지 않고, A 자신의 신원으로 B 전용·읽기 전용 토큰을 새로 받는다
        status, body = hub.exchange(token, B_RESOURCE, "crm:read")
        if status != 200:
            return f"토큰 교환 거부: {body['error_description']}", False
        token = body["access_token"]
    status, body = hub.call(B_URL + "/mcp", token, "crm_read", prove=(MODE == "secure"))
    if status != 200:
        return f"MCP B 거부({status}): {body['error']}", False
    return "MCP B 응답 ▶ " + body["result"]["content"][0]["text"], True


def crm_read(server, c):
    route = " → ".join(path(c)) if MODE == "secure" else f"{c['sub']} → (확인 안 함)"
    return f"고객 3명 조회. B가 확인한 경로: {route}, scope={c['scope']}", True


class McpA(McpServer):
    url, resource = A_URL + "/mcp", A_RESOURCE
    allowed_clients = {"report-agent"}
    tools = {"search_docs": ("docs:read", search_docs), "crm_summary": ("crm:read", crm_summary)}


class McpB(McpServer):
    url, resource = B_URL + "/mcp", B_RESOURCE
    allowed_clients = {"docs-hub"}                 # B는 A를 거쳐서만 부를 수 있다
    tools = {"crm_read": ("crm:read", crm_read)}


def start():
    servers = [ThreadingHTTPServer((HOST, int(url.rsplit(":", 1)[1])), handler)
               for url, handler in ((AS_URL, AuthServer), (A_URL, McpA), (B_URL, McpB))]
    for s in servers:
        threading.Thread(target=s.serve_forever, daemon=True).start()
    return servers
