# sanitize.py — HTML에서 주석과 숨김 텍스트를 제거하고 본문만 추출
# 사용법: python3 sanitize.py samples/notes-a.html
#
# 왜 필요한가: 웹 페이지에는 사람 눈에는 안 보이지만 AI는 그대로 읽는 글이 숨어 있을 수 있다
# (HTML 주석, 흰 바탕의 흰 글씨, 0px 글꼴 등). 공격자는 이곳에 "이전 지시를 무시하라" 같은
# 간접 프롬프트 인젝션 문장을 넣는다. 그래서 AI에게 넘기기 전에 이런 부분을 먼저 걷어 낸다.
# 단, 이 방법은 알려진 숨김 기법만 막는 "1차 필터"일 뿐이며 모든 인젝션을 막지는 못한다.
import re, sys
from bs4 import BeautifulSoup, Comment   # pip install beautifulsoup4

html = open(sys.argv[1], encoding="utf-8").read()   # 명령줄에서 받은 HTML 파일을 읽는다
soup = BeautifulSoup(html, "html.parser")          # HTML을 태그 단위로 다룰 수 있게 해석한다

# 1) HTML 주석 제거
#    <!-- ... --> 안의 글은 화면에 나오지 않지만 AI에게는 그대로 전달된다
for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
    c.extract()

# 2) 흰 글씨·아주 작은 글꼴·숨김 처리된 요소 제거
#    style 속성에 아래 패턴 중 하나라도 있으면 그 태그를 통째로 지운다
#      color: #fff / #ffffff / white   → 흰 바탕에서 안 보이는 글씨
#      font-size: 0~2px                → 너무 작아 읽을 수 없는 글씨
#      display: none                   → 화면에 아예 표시하지 않는 요소
hidden = re.compile(r"color\s*:\s*#?(fff|ffffff|white)|font-size\s*:\s*[0-2]px|display\s*:\s*none", re.I)
for tag in soup.find_all(style=hidden):
    tag.decompose()

# 3) 남은 본문만 줄 단위로 출력한다 (이 결과를 AI에게 넘긴다)
print(soup.get_text("\n", strip=True))
