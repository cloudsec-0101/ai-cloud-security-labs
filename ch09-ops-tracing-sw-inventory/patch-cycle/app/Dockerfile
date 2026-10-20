# 실습용 주문 조회 서비스 이미지. 같은 app.py로 버전만 바꿔 1.0·1.1·1.2 이미지를 만든다 (setup.sh 참고)
#   docker build --build-arg VERSION=1.1 -t lab-app:1.1 app
FROM python:3.12-slim
# 빌드할 때 받은 버전 값을 실행 중에도 읽을 수 있게 환경 변수로 넘긴다
ARG VERSION=1.0
ENV APP_VERSION=${VERSION}
COPY app.py /app/app.py
# root가 아닌 사용자로 실행
USER nobody
CMD ["python3", "/app/app.py"]
