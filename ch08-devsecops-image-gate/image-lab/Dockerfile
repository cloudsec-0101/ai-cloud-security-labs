# 지원 중인 베이스 이미지 + 갱신된 의존성 (v2)
# Dockerfile.old와 비교하면 바뀐 곳은 세 군데다: 베이스 이미지, requirements 파일, USER nobody
FROM python:3.12-slim
WORKDIR /app
# 의존성 목록을 먼저 복사해 설치한다 (코드만 바뀌었을 때는 이 단계를 캐시로 건너뛰어 빌드가 빨라진다)
COPY requirements.txt .
# --no-cache-dir: 설치 파일 캐시를 이미지에 남기지 않아 크기를 줄인다
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
# root가 아닌 사용자로 실행 → 앱이 뚫려도 컨테이너 안에서 할 수 있는 일이 줄어든다
USER nobody
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
