"""RAG 검색 단계의 문서 권한 실습(축소판).
실제 RAG는 문서를 벡터로 바꿔 Vector DB에 넣지만, 여기서는 글자 두 개씩 겹치는 정도로 "질문과 가까운 문서"를 찾는다.
보려는 것은 검색 기술이 아니라, 검색 결과(= 프롬프트에 들어갈 문서)가 누구의 권한으로 걸러지는가이다.

사용법:
  python3 rag.py index --no-acl     원본 문서의 권한 정보를 버리고 색인을 만든다(권한 상실)
  python3 rag.py index --acl        문서마다 원본 권한을 메타데이터로 함께 색인한다
  python3 rag.py ask <역할> "<질문>"  역할: employee(임직원) partner(협력사) hr(인사팀) finance(재무팀)

비교 포인트: --no-acl로 색인하면 협력사가 물어도 인사·재무 문서가 검색되어 AI 답변에 섞인다.
"AI에게 답하지 말라고 지시"하는 것이 아니라, AI에게 넘기기 전에 검색 단계에서 걸러야 한다.
"""
import json
import sys


def grams(text):
    """공백을 없앤 뒤 글자 두 개씩 잘라 집합으로 만든다. 예: "환불규정" → {"환불", "불규", "규정"}"""
    t = "".join(text.split())
    return {t[i:i + 2] for i in range(len(t) - 1)}


def build(with_acl):
    """docs.json(원본 문서 저장소 역할)을 읽어 index.json(Vector DB 역할)을 만든다."""
    docs = json.load(open("docs.json", encoding="utf-8"))
    index = []
    for d in docs:
        entry = {"id": d["id"], "title": d["title"], "text": d["text"]}
        if with_acl:
            entry["allowed"] = d["allowed"]          # 원본 권한을 그대로 따라가게 한다
        # with_acl이 아니면 본문만 복사된다 → 원본 시스템에 있던 접근 권한이 색인 과정에서 사라진다
        index.append(entry)
    json.dump(index, open("index.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"색인 {len(index)}건 생성 ({'권한 포함' if with_acl else '권한 정보 없음'})")


def ask(role, question, k=3):
    """질문과 가까운 문서를 최대 k개 찾는다. 이 결과가 실제 RAG라면 프롬프트에 붙어 모델에게 간다."""
    index = json.load(open("index.json", encoding="utf-8"))
    q = grams(question)
    hits = []
    for e in index:
        if "allowed" in e and role not in e["allowed"]:
            continue                                 # 검색 단계에서 사용자 권한으로 거른다(AI 바깥의 권한 검사)
        # 유사도 = 질문의 두 글자 조각 중 문서에도 있는 조각의 비율 (0~1)
        score = len(q & grams(e["title"] + e["text"])) / len(q)
        if score > 0.15:                             # 너무 관계없는 문서는 버린다
            hits.append((score, e))
    hits.sort(key=lambda h: -h[0])                   # 유사도가 높은 순
    print(f"[{role}] {question}")
    if not hits:
        print("  → 프롬프트에 넣을 문서 없음")
    for score, e in hits[:k]:
        print(f"  → {e['id']} {e['title']}  (유사도 {score:.2f})")


if __name__ == "__main__":
    if sys.argv[1] == "index":
        build("--acl" in sys.argv)
    else:
        ask(sys.argv[2], sys.argv[3])
