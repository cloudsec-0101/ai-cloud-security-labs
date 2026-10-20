# 실습용 "AI 서빙" 앱: 모델 대신 간단한 규칙으로 답한다 (이미지 빌드·스캔 실습용)
# 앱 코드는 v1(Dockerfile.old)과 v2(Dockerfile)가 똑같다. 달라지는 것은 베이스 이미지와 의존성 버전뿐이다.
# → 같은 코드라도 "무엇 위에서, 어떤 라이브러리와 함께" 돌리느냐에 따라 취약점 수가 크게 달라진다.
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Ask(BaseModel):          # 요청 본문 형식: {"question": "..."} (형식이 다르면 FastAPI가 422로 거절)
    question: str

@app.post("/v1/ask")
def ask(q: Ask):
    return {"answer": f"'{q.question}'에 대한 답변은 준비 중입니다.", "model": "rule-0.1"}
