#!/usr/bin/env bash
# garak 실행 기록(.log)에서 probe·detector별 결과 줄만 뽑아 보여 준다
# 사용법: ./summarize.sh qwen-1 qwen-2 llama-1   (qwen-1.log, qwen-2.log, llama-1.log를 읽음)
# 결과 예: grandma.Win10 productkey.Win5x5: PASS ok on 18/ 18
#          (probe 이름, 검사기(detector) 이름, 판정, 전체 답 중 안전했던 답의 수)
for f in "$@"; do                     # 인자로 받은 이름마다 반복
  echo "== $f"
  # 1) sed: 화면 색을 바꾸는 제어 문자(ESC[...m)를 지운다
  # 2) tr: 진행 막대가 쓰는 줄 되돌림(\r)을 줄바꿈으로 바꿔 한 줄씩 나눈다
  # 3) grep: "이름 이름: PASS|FAIL ..." 모양의 결과 줄만 뽑는다 (-a: 이진 문자가 섞여도 글자로 취급)
  # 4) sed: 여러 칸 공백을 한 칸으로 줄여 보기 좋게 한다
  sed 's/\x1b\[[0-9;]*[A-Za-z]//g' "$f.log" | tr '\r' '\n' \
    | grep -aoE "[A-Za-z0-9_.]+ +[A-Za-z0-9_.]+: (PASS|FAIL) .*" | sed 's/  */ /g'
done
