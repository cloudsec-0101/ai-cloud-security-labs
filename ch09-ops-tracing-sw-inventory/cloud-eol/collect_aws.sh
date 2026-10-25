#!/usr/bin/env bash
# collect_aws.sh — 관리형 서비스의 버전 정보를 조회만 해서(describe, list) 폴더에 저장한다 (9장 실습 3)
# 사용법: ./collect_aws.sh [출력 폴더] [리전]   읽기 전용 권한(예: ReadOnlyAccess)으로 실행한다.
#
# RDS·ElastiCache·EKS·Lambda는 서버가 보이지 않아 collect_linux.sh 같은 방법으로는 버전을 모을 수 없다.
# 대신 클라우드 API로 "어떤 엔진의 몇 버전을 쓰는지"를 조회한다. 결과 폴더를 eol_check.py에 넘긴다.
# 조회(describe·list) 명령만 쓰므로 실행해도 계정의 자원은 바뀌지 않는다.
set -u
# 인자가 없으면 폴더는 my-account, 리전은 AWS CLI에 설정된 기본 리전을 쓴다
OUT="${1:-my-account}"; REGION="${2:-$(aws configure get region)}"; mkdir -p "$OUT"
A="aws --region $REGION --output json"            # 반복되는 공통 옵션을 묶어 둔다
$A rds describe-db-instances > "$OUT/rds.json"          # DB 엔진·버전, 자동 마이너 업그레이드 여부
$A elasticache describe-cache-clusters > "$OUT/elasticache.json"
$A lambda list-functions > "$OUT/lambda.json"           # 함수마다 런타임(python3.9 등)
# EKS는 클러스터 목록을 먼저 받고, 클러스터마다 상세 정보를 같은 파일에 이어 붙인다
: > "$OUT/eks.json"                                      # 빈 파일로 초기화
for c in $(aws --region "$REGION" eks list-clusters --query "clusters[]" --output text); do
  $A eks describe-cluster --name "$c" >> "$OUT/eks.json"
done
echo "저장: $OUT (리전 $REGION). 여러 리전을 쓴다면 리전마다 실행한다."
