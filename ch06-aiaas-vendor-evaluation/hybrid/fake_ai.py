"""외부 AI 서비스 흉내: 받은 내용을 그대로 기록하고, 간단한 '요약'을 돌려준다.
경계를 넘어 실제로 무엇이 나갔는지는 received.log에서 확인한다.

사용법: python3 fake_ai.py   (켜 둔 채로 다른 터미널에서 gateway.py를 실행한다)
실제 외부 AI 서비스에서는 공급자 쪽에 무엇이 저장되는지 우리가 직접 볼 수 없다.
이 흉내 서버는 그 "보이지 않는 쪽"을 received.log로 보여 주는 역할을 한다.
"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        text = json.loads(self.rfile.read(int(self.headers["Content-Length"])))["text"]
        # 1) 받은 원문을 그대로 기록한다 → 가명처리가 제대로 되었는지 이 파일로 확인한다
        with open("received.log", "a", encoding="utf-8") as f:
            f.write(text + "\n")
        # 2) "요약" 흉내: 각 줄에서 "]" 뒤의 내용을 "문의함/요청함/싶다고" 앞까지 잘라 40자만 남긴다
        #    (진짜 모델 대신 규칙으로 답하지만, 받은 이름·번호가 답에 그대로 섞여 돌아오는 점은 실제와 같다)
        summary = [line.split("]", 1)[1].split("문의함")[0].split("요청함")[0].split("싶다고")[0].strip()[:40] + " …"
                   for line in text.splitlines() if "]" in line]
        body = json.dumps({"summary": "\n".join(summary)}, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass                       # 기본 접속 로그는 화면에 찍지 않는다


print("외부 AI 서비스(흉내) 대기 중: http://127.0.0.1:8081")
HTTPServer(("127.0.0.1", 8081), Handler).serve_forever()
