"""회의록 정리 형식. 표준 입력의 줄을 결정 / 할 일 / 다음 일정으로 나눈다."""
import sys

SECTIONS = {"결정": [], "할 일": [], "다음 일정": []}
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    key = "다음 일정" if "회의" in line and "다음" in line else "할 일" if "예정" in line or "까지" in line else "결정"
    SECTIONS[key].append(line)
for key, lines in SECTIONS.items():
    print(f"## {key}")
    print("\n".join(f"- {l}" for l in lines) or "- 없음")
