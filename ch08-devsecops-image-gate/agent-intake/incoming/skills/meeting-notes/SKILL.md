---
name: meeting-notes
description: 회의록 파일을 읽어 결정 사항, 할 일, 다음 일정으로 정리한다
version: 1.3.0
source: skills.hanbit.example/meeting-notes
allowed-tools: Read, Write
---

# 회의록 정리

1. 사용자가 알려 준 회의록 파일을 Read로 읽는다.
2. `scripts/format_notes.py`의 형식(결정 / 할 일 / 다음 일정)에 맞춰 정리한다.
3. 결과는 `workspace/out/` 아래에 Write로 저장하고, 저장한 경로를 알려 준다.
