#!/usr/bin/env bash
# AI 자산 등록 파일을 정책(Rego)으로 검사합니다. 위반이 하나라도 있으면 종료 코드 1을 돌려줍니다.
# 사용: ./check.sh [등록 파일]    (기준일을 바꾸려면 TODAY=2026-10-20 ./check.sh)
#
# Policy as Code: "AI 자산은 책임자가 있어야 한다", "매우 높음 등급은 Kill Switch가 있어야 한다" 같은
# 규정을 문서가 아니라 코드(policy/ai_assets.rego)로 써 두고, 등록 파일이 바뀔 때마다 자동으로 검사합니다.
# 사람이 표를 눈으로 대조하는 대신, 기계가 매번 같은 기준으로 확인합니다.
set -euo pipefail                        # 오류·미정의 변수·파이프 중간 실패 시 바로 멈춘다
cd "$(dirname "$0")"
REGISTRY="${1:-registry/ai-assets.yaml}"
TODAY="${TODAY:-$(date +%F)}"            # 재평가 주기 계산의 기준일 (기본: 오늘)

# opa가 설치되어 있으면 그대로, 없으면 Docker 이미지로 실행
if command -v opa >/dev/null 2>&1; then
  run_opa() { opa "$@"; }
else
  run_opa() { docker run --rm -i -v "$PWD":/work -w /work openpolicyagent/opa:1.0.0 "$@"; }
fi

# OPA에 물을 질문: deny(위반 메시지 집합)를 정렬해 한 줄에 하나씩 이어 붙여라
query='concat("\n", sort(data.aigov.deny))'
# -d policy/ : 정책 파일, -d 등록 파일 : 검사할 데이터(data.assets, data.mcp_servers), 입력(input)에는 기준일만 넣는다
result=$(echo "{\"today\":\"$TODAY\"}" | run_opa eval --stdin-input -d policy/ -d "$REGISTRY" -f raw "$query")
total=$(echo "{}" | run_opa eval --stdin-input -d "$REGISTRY" -f raw 'count(data.assets)')   # 전체 자산 수

echo "AI 자산 정책 검사 (기준일 $TODAY, 등록 파일 $REGISTRY, 자산 ${total}개)"
if [ -z "$result" ]; then
  echo "위반 없음"
  exit 0
fi
echo "$result" | sed 's/^/  /'           # 위반 메시지마다 두 칸 들여쓰기
# 위반 건수와, 위반이 있는 자산 수(메시지 첫 단어 = 자산 ID의 중복 제거)를 센다
echo "위반 $(echo "$result" | wc -l)건, 자산 $(echo "$result" | cut -d' ' -f1 | sort -u | wc -l)개 → 배포·운영 승인 불가 (종료 코드 1)"
exit 1
