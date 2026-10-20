# trace_app.py — Trace ID 기반 추적 실습 서버 (9장 실습 1)
# 실행: uvicorn trace_app:app --port 8000        마스킹 끄기(비교용): LOG_MASK=off uvicorn trace_app:app --port 8000
#
# AI 서비스 요청 하나는 Gateway → RAG 검색 → Agent 계획 → Tool 실행 → 모델 호출처럼 여러 단계를 지난다.
# 요청이 동시에 여러 개 들어오면 로그가 뒤섞여 "이 줄이 어느 요청의 것인지" 알 수 없게 된다.
# 그래서 요청마다 Trace ID를 하나 정하고, 모든 단계의 로그에 같은 ID를 자동으로 붙인다.
# 결과 확인: grep <Trace ID> app-log.jsonl  → 요청 하나의 전체 흐름만 모아 볼 수 있다.
import asyncio, contextvars, json, logging, os, random, re, time, uuid
from fastapi import FastAPI, Request

# contextvars: 동시에 처리 중인 요청마다 따로 값을 기억하는 변수 (요청끼리 Trace ID가 섞이지 않는다)
trace_id_var = contextvars.ContextVar("trace_id", default="-")
MASK = os.environ.get("LOG_MASK", "on") != "off"

# 로그로 넘기기 전에 가리는 정형 민감정보 (9-2 "저장 전 마스킹")
# 각 줄: (찾을 정규식, 바꿀 모양). \1, \2는 괄호로 묶어 남겨 둘 부분이다
PATTERNS = [
    # 한국어는 숫자 바로 뒤에 조사가 붙으므로(예: 5678로) \b 대신 "앞뒤가 숫자가 아님"으로 경계를 정한다
    (re.compile(r"(?<!\d)(\d{6})-?([1-4])\d{6}(?!\d)"), r"\1-\2******"),                # 주민등록번호: 뒷자리 첫 숫자만 남김
    (re.compile(r"(?<!\d)(\d{4})-?\d{4}-?\d{4}-?(\d{4})(?!\d)"), r"\1-****-****-\2"),    # 카드번호: 앞뒤 4자리만 남김
    (re.compile(r"(?<!\d)(01[016789])-?\d{3,4}-?(\d{4})(?!\d)"), r"\1-****-\2"),         # 휴대전화: 가운데를 가림
    (re.compile(r"(?<![\w.%+-])([A-Za-z0-9])[A-Za-z0-9._%+-]*@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)"), r"\1***@\2"),  # 이메일
]

def mask(text):
    """정해 둔 패턴을 차례로 적용해 민감정보를 가린다."""
    for pattern, repl in PATTERNS:
        text = pattern.sub(repl, text)
    return text

class JsonFormatter(logging.Formatter):
    """로그 한 줄을 JSON으로 만든다. 사람이 읽기보다 SIEM 같은 도구가 검색·집계하기 쉽다."""
    def format(self, record):
        msg = record.getMessage()
        return json.dumps({
            "time": time.strftime("%H:%M:%S"),
            "trace_id": trace_id_var.get(),          # 모든 로그에 자동으로 붙음
            "step": record.name,                     # 어느 단계의 로그인가 (gateway, rag, model, agent, tool)
            "msg": mask(msg) if MASK else msg,       # 원문은 모델 호출에만 쓰고, 로그에는 가린 값만 남김
        }, ensure_ascii=False)

# 다섯 단계의 로거가 모두 같은 파일(app-log.jsonl)에 같은 형식으로 기록하게 한다
handler = logging.FileHandler("app-log.jsonl", encoding="utf-8")
handler.setFormatter(JsonFormatter())
for name in ["gateway", "rag", "model", "agent", "tool"]:
    lg = logging.getLogger(name); lg.setLevel(logging.INFO); lg.addHandler(handler)

app = FastAPI()

# 미들웨어: 모든 요청이 처리되기 전과 후에 반드시 거치는 함수
@app.middleware("http")
async def add_trace_id(request: Request, call_next):
    # 앞단(다른 서비스)에서 받은 Trace ID가 있으면 이어 쓰고, 없으면 새로 만든다
    tid = request.headers.get("X-Trace-Id") or uuid.uuid4().hex[:12]
    trace_id_var.set(tid)
    response = await call_next(request)
    response.headers["X-Trace-Id"] = tid     # 응답에도 돌려주어, 사용자가 문의할 때 이 번호로 찾을 수 있게 한다
    return response

# 검색 대상 문서 (키워드 → 문서 위치). 실제로는 Vector DB 검색이다
DOCS = {"환불": "환불규정.pdf#p3", "교환": "교환정책.pdf#p2", "배송": "배송안내.pdf#p1"}

# 아래 세 함수는 RAG 검색·모델 호출·Tool 실행을 흉내 낸다. 일부러 무작위로 기다려 요청들의 로그가 섞이게 한다
async def search_docs(q):
    await asyncio.sleep(random.uniform(0.05, 0.2))      # 동시 요청이 섞이도록 지연
    docs = [d for k, d in DOCS.items() if k in q] or ["자주묻는질문.pdf#p1"]
    logging.getLogger("rag").info(f"검색어='{q}' 결과={docs}")
    return docs

async def call_model(prompt):
    await asyncio.sleep(random.uniform(0.1, 0.3))
    # 프롬프트 원문 대신 길이·토큰 수만 남긴다 (원문을 남기면 로그가 민감정보 저장소가 된다)
    logging.getLogger("model").info(f"모델 호출 prompt_chars={len(prompt)} tokens=152")
    return "문의하신 내용은 첨부한 규정에 따라 처리됩니다."

async def run_tool(name, arg):
    await asyncio.sleep(random.uniform(0.05, 0.2))
    logging.getLogger("tool").info(f"Tool 실행 name={name} arg={arg}")
    return {"order": arg, "status": "배송완료"}

# 요청 예: curl -X POST localhost:8000/ask -H "Content-Type: application/json" \
#            -d '{"user":"kim","question":"환불 문의, 연락처 010-1234-5678로"}'
@app.post("/ask")
async def ask(body: dict):
    user, q = body.get("user"), body.get("question")
    logging.getLogger("gateway").info(f"요청 수신 user={user} question='{q}'")   # 질문 속 전화번호는 로그에서 가려진다
    docs = await search_docs(q)
    logging.getLogger("agent").info("계획: 문서 검색 → 주문 조회 Tool → 답변 생성")
    order = await run_tool("get_order_status", body.get("order_id", "A-1001"))
    answer = await call_model(f"{q} {docs} {order}")
    logging.getLogger("gateway").info("응답 반환")
    return {"answer": answer}
