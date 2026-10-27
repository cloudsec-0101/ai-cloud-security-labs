#!/usr/bin/env bash
# setup.sh — 실습 환경 만들기 (9장 실습 3): 서비스 이미지 3개 버전, 서버 3대(1.0), 앞단 프록시
# 몇 번을 다시 실행해도 같은 처음 상태로 돌아간다 (기존 컨테이너·기록을 지우고 새로 만든다).
#
#   외부 요청 → proxy(127.0.0.1:8080) ─┬─▶ app1 (127.0.0.1:8081)  ← Canary(먼저 패치해 보는 서버)
#                                      ├─▶ app2 (127.0.0.1:8082)
#                                      └─▶ app3 (127.0.0.1:8083)
set -e                                   # 명령 하나라도 실패하면 바로 멈춘다
cd "$(dirname "$0")"                     # 어디서 실행하든 이 스크립트가 있는 폴더 기준으로 동작
# 컨테이너끼리 이름(app1 등)으로 부를 수 있는 전용 네트워크 (이미 있으면 그냥 넘어간다)
docker network create patchlab >/dev/null 2>&1 || true
# 1) 같은 app.py로 버전만 다른 이미지 3개를 만든다: 1.0(취약), 1.1(수정), 1.2(고장 난 패치)
for v in 1.0 1.1 1.2; do
  docker build -q --build-arg VERSION=$v -t lab-app:$v app >/dev/null
done
# 2) 서버 3대를 모두 취약한 1.0으로 띄운다
for i in 1 2 3; do
  docker rm -f app$i >/dev/null 2>&1 || true
  docker run -d --name app$i --network patchlab -p 127.0.0.1:808$i:8000 lab-app:1.0 >/dev/null
done
# 3) 앞단 프록시: Workaround 규칙 파일은 처음에는 비워 둔다
: > proxy/workaround.conf
docker rm -f proxy >/dev/null 2>&1 || true
docker run -d --name proxy --network patchlab -p 127.0.0.1:8080:80 \
  -v "$PWD/proxy/nginx.conf:/etc/nginx/conf.d/default.conf:ro" \
  -v "$PWD/proxy/workaround.conf:/etc/nginx/workaround.conf:ro" nginx:1.27-alpine >/dev/null
# 4) 이전 실습 기록을 지우고, 보안 공지를 받아 패치 티켓을 여는 것부터 시작한다
rm -rf state
python3 patch_cycle.py init
