#!/usr/bin/env bash
# 사용법: ./try.sh <사용자> <기기ID> <앱> [국가] [메서드]
#   예) ./try.sh kim LAPTOP-KIM-01 erp
#   예) ./try.sh kim LAPTOP-KIM-01 erp US        (해외 접속 흉내 → 위험 점수 변화 확인)
#   예) ./try.sh lee LAPTOP-LEE-01 aichat KR POST   (패치 미적용 기기의 쓰기 요청 → 차단 확인)
# 사용자·기기는 keycloak/realm-zt.json(kim=임직원, lee=협력사)과 devices.json에 정의되어 있다.
# 하는 일: ① Keycloak에서 토큰을 받고 ② 그 토큰과 기기·국가 정보를 붙여 PEP에 요청한 뒤 ③ 결과를 보기 좋게 출력한다.

# 인자를 변수에 담는다. 국가와 메서드는 생략하면 KR, GET
USER_ID=$1; DEVICE=$2; APP=$3; COUNTRY=${4:-KR}; METHOD=${5:-GET}

# ① 토큰 발급: 실습 편의를 위해 아이디·비밀번호로 바로 토큰을 받는 방식(password grant)을 쓴다
#    (운영에서는 브라우저 로그인 방식을 쓰고, 이 방식은 쓰지 않는다). 실습 사용자 비밀번호는 모두 Passw0rd!
TOKEN=$(curl -s -d "client_id=zt-lab" -d "grant_type=password" \
  -d "username=$USER_ID" -d "password=Passw0rd!" \
  http://localhost:8080/realms/zt/protocol/openid-connect/token | python3 -c 'import sys,json;print(json.load(sys.stdin).get("access_token",""))')

# ② PEP에 요청: 토큰(신원) + X-Device-Id(기기) + X-Country(접속 위치)를 함께 보낸다
# ③ 응답 JSON을 한글이 보이게 정렬해서 출력한다
curl -s -X "$METHOD" "http://localhost:8000/$APP/home" \
  -H "Authorization: Bearer $TOKEN" -H "X-Device-Id: $DEVICE" -H "X-Country: $COUNTRY" \
  | python3 -m json.tool --no-ensure-ascii
