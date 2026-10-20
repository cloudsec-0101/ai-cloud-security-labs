# pep, erp, aichat, detector가 함께 쓰는 이미지. 실행할 파일은 docker-compose.yml의 command가 정한다.
FROM python:3.12-slim
WORKDIR /app
# 라이브러리 버전을 모두 고정해, 언제 빌드해도 같은 결과가 나오게 한다
#   fastapi·uvicorn: 웹 서버 / httpx: OPA·앱 호출 / pyjwt[crypto]: 토큰 서명 검증
RUN pip install --no-cache-dir fastapi==0.115.6 uvicorn==0.34.0 httpx==0.28.1 "pyjwt[crypto]==2.10.1"
COPY *.py /app/
