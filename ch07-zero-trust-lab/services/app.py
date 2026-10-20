# 보호 대상 앱 (ERP, AI 챗봇 역할). PEP가 붙여 준 사용자 정보만 믿는다.
# 이 앱에는 로그인 기능이 없다. 내부망(back)에만 있어 PEP를 거친 요청만 들어오기 때문이다.
# 받은 요청을 그대로 되돌려 주므로, "누가(X-Verified-User) 어떤 경로로 들어왔는지"를 확인하는 데 쓴다.
import os
from fastapi import FastAPI, Request

app = FastAPI()
NAME = os.environ.get("APP_NAME", "app")   # docker-compose.yml에서 앱 이름을 넣어 준다 (같은 코드로 ERP와 챗봇을 흉내)

# 모든 경로(/{path:path})의 GET·POST 요청을 이 함수 하나가 받는다
@app.api_route("/{path:path}", methods=["GET", "POST"])
async def handle(path: str, request: Request):
    return {"app": NAME, "path": "/" + path, "method": request.method,
            "user": request.headers.get("X-Verified-User")}   # PEP가 토큰을 검증한 뒤 붙여 준 사용자 이름
