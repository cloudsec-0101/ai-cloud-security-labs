"""실습용 축소판 AI Gateway.
업무 앱은 "summarizer" 같은 업무 이름만 알고, 실제로 어느 공급자의 어떤 모델을 부를지는 routes.json이 정한다.
- 요청마다 routes.json을 다시 읽으므로, 파일만 고치면 앱을 건드리지 않고 공급자가 바뀐다.
- primary가 실패하면 fallback으로 자동 전환한다.
- 모든 호출을 gateway.log에 남긴다(어느 공급자·모델로 갔는지, 걸린 시간, 성공 여부).
운영에서는 LiteLLM 같은 AI Gateway가 같은 역할을 한다(10장 실습 2).

사용법: python3 gateway.py   (켜 둔 채로 다른 터미널에서 app.py·eval.py를 실행한다)
routes.json 구조 (업무 이름 → primary/fallback 대상):
  {"summarizer": {"primary":  {"provider": "공급자 1", "base_url": "http://127.0.0.1:11434/v1", "model": "qwen2.5:0.5b"},
                  "fallback": {"provider": "공급자 2", "base_url": "http://127.0.0.1:11434/v1", "model": "llama3.2:1b"}}}
"""
import json
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer


def call(target, payload):
    """공급자 한 곳에 요청을 보낸다. 앱이 보낸 업무 이름(model)을 실제 모델 이름으로 바꿔 끼운다."""
    body = dict(payload, model=target["model"])
    req = urllib.request.Request(target["base_url"] + "/chat/completions",
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=120).read())


def log(entry):
    """호출 기록을 한 줄에 JSON 하나씩(JSON Lines) 덧붙인다. 공급자 전환·장애의 증거가 된다."""
    with open("gateway.log", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        # 요청이 올 때마다 라우팅 표를 새로 읽는다 → 서버를 재시작하지 않아도 공급자 변경이 바로 반영된다
        routes = json.load(open("routes.json", encoding="utf-8"))
        route = routes.get(payload.get("model"))
        if route is None:
            # 표에 없는 업무 이름은 거절한다 (아무 모델이나 마음대로 부르는 것을 막는 허용 목록 역할)
            return self.reply(404, {"error": f"등록되지 않은 업무 이름: {payload.get('model')}"})
        # primary → fallback 순서로 시도하고, 처음 성공한 응답을 돌려준다
        for role in ("primary", "fallback"):
            target = route.get(role)
            if not target:
                continue
            start = time.time()
            try:
                result = call(target, payload)
                log({"route": payload["model"], "role": role, "provider": target["provider"],
                     "model": target["model"], "ok": True, "sec": round(time.time() - start, 2)})
                # 응답에 "실제로 누가 답했는지"를 덧붙여 앱과 평가 스크립트가 확인할 수 있게 한다
                result["gateway"] = {"provider": target["provider"], "model": target["model"], "role": role}
                return self.reply(200, result)
            except Exception as e:
                # 실패해도 멈추지 않고 기록만 남긴 뒤 다음 대상(fallback)으로 넘어간다
                log({"route": payload["model"], "role": role, "provider": target["provider"],
                     "model": target["model"], "ok": False, "error": str(e)[:80]})
        return self.reply(502, {"error": "모든 공급자 호출 실패"})

    def reply(self, code, obj):
        """JSON 응답을 보낸다. ensure_ascii=False로 한글이 \\uXXXX로 깨지지 않게 한다."""
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass                       # 기본 접속 로그를 화면에 찍지 않는다 (gateway.log에 따로 남기므로)


print("AI Gateway 대기 중: http://127.0.0.1:4100/v1/chat/completions")
HTTPServer(("127.0.0.1", 4100), Handler).serve_forever()   # 127.0.0.1: 내 PC에서만 접속 가능
