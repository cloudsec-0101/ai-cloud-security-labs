# app.py — 실습용 "주문 조회" 서비스 (9장 실습 3). 버전에 따라 동작이 다르다.
#   1.0: 관리 기능(/admin/export)이 인증 없이 열려 있음 (실습용 가상 취약점 LAB-2026-0001)
#   1.1: 관리 기능에 인증 요구 (수정 버전)
#   1.2: 수정은 되었지만 시작 점검(/health)이 실패하는 고장 난 패치
# 버전은 이미지를 만들 때 정해진다 (Dockerfile의 VERSION → 환경 변수 APP_VERSION).
# patch_cycle.py는 아래 세 주소로 서버 상태를 확인한다:
#   /version       지금 실제로 실행 중인 버전 ("작업 완료" 보고가 아니라 실제 값을 확인하기 위해)
#   /health        정상 동작 여부 (패치 뒤 이 값이 실패면 자동 롤백)
#   /admin/export  취약점이 남아 있는지 (200이면 취약, 403이면 안전)
import json, os
from http.server import BaseHTTPRequestHandler, HTTPServer

VER = os.environ.get("APP_VERSION", "1.0")

class Handler(BaseHTTPRequestHandler):
    def send(self, code, obj):
        """상태 코드와 JSON 본문을 보낸다."""
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            if VER == "1.2":
                # 실제 장애에서 흔한 상황 흉내: 패치와 함께 설정 형식이 바뀌어 서비스가 뜨지 못한다
                return self.send(500, {"status": "error", "reason": "설정 파일 형식이 바뀌어 DB 연결 실패"})
            return self.send(200, {"status": "ok"})
        if self.path == "/version":
            return self.send(200, {"version": VER})
        if self.path.startswith("/admin/export"):
            if VER == "1.0":
                # 취약 버전: 누구나 고객 정보를 내려받을 수 있다 (가짜 데이터)
                return self.send(200, {"customers": [{"name": "고객A", "phone": "010-0000-0001"}],
                                       "note": "인증 없이 열린 관리 기능 (LAB-2026-0001)"})
            return self.send(403, {"error": "관리자 인증 필요"})
        return self.send(200, {"service": "주문 조회", "version": VER})

    def log_message(self, *args):
        pass                       # 접속 로그를 화면에 찍지 않는다

HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()   # 컨테이너 안에서는 모든 주소로 받아야 프록시가 닿는다
