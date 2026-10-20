"""업무 앱: 상담 기록을 요약한다. 공급자나 모델 이름은 모른다. 아는 것은 Gateway 주소와 업무 이름뿐이다.

사용법: python3 app.py "요약할 상담 기록"   (인자를 생략하면 예시 문장을 요약한다)

이 앱의 핵심은 "무엇을 모르는가"이다. 공급자 주소·모델 이름·API 키가 코드에 없으므로,
공급자를 바꾸거나(Exit) 장애로 다른 공급자로 넘어가도 이 파일은 고칠 필요가 없다.
"""
import json
import sys
import urllib.request

GATEWAY = "http://127.0.0.1:4100/v1/chat/completions"   # 앱이 아는 유일한 주소 (gateway.py)
TASK = "summarizer"                                     # 모델 이름 대신 "업무 이름"으로 요청한다


def summarize(text):
    # OpenAI 호환 형식의 요청. model 칸에 실제 모델 대신 업무 이름을 넣는 것이 요점이다
    payload = {"model": TASK, "temperature": 0,          # temperature 0: 같은 입력에 최대한 같은 답 (평가 비교용)
               "messages": [{"role": "system", "content": "상담 기록을 한국어 한 문장으로 요약하라."},
                            {"role": "user", "content": text}]}
    req = urllib.request.Request(GATEWAY, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=180).read())   # 로컬 모델은 느릴 수 있어 넉넉히 기다린다
    # 요약문과 함께, Gateway가 실제로 어느 공급자·모델로 보냈는지(r["gateway"])를 돌려준다
    return r["choices"][0]["message"]["content"].strip(), r["gateway"]


if __name__ == "__main__":
    text = sys.argv[1] if len(sys.argv) > 1 else "고객이 주문한 운동화의 배송이 3일째 멈춰 있다고 문의함. 택배사 확인 후 내일 출고하기로 안내함."
    summary, via = summarize(text)
    print(f"[{via['provider']} / {via['model']}] {summary}")   # 예: [공급자 1 / qwen2.5:0.5b] 요약문
