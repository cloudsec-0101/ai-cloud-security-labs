"""8장 실습 4 실행기: 인가 서버, MCP A, MCP B를 띄우고 scenarios.json의 호출을 차례로 보낸다.

사용법:
  python3 lab.py bearer   토큰의 서명·만료·범위만 보는 MCP Server. A는 받은 토큰을 B에 그대로 넘긴다
  python3 lab.py secure   대상·소유 증명·승인된 Client까지 확인하고, A는 토큰 교환으로 B를 부른다
"""
import json
import sys

import services
from services import A_RESOURCE, A_URL, B_RESOURCE, B_URL, Client

AUD = {"A": A_RESOURCE, "B": B_RESOURCE}
TARGET = {"A": A_URL + "/mcp", "B": B_URL + "/mcp"}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode not in ("bearer", "secure"):
        sys.exit(__doc__)
    services.MODE = mode
    servers = services.start()
    print(f"MCP Server 검사 수준: {mode}\n")
    for i, sc in enumerate(json.load(open("scenarios.json", encoding="utf-8")), 1):
        client = Client(sc["client"])
        _, body = client.get_token("kim", AUD[sc["aud"]], "docs:read crm:read")
        prove = mode == "secure" and sc.get("prove", True)
        status, body = client.call(TARGET[sc["target"]], body["access_token"], sc["tool"], prove)
        if status != 200:
            verdict, reason = f"{status} 거부", body["error"]
        else:
            result = body["result"]
            verdict = "실패" if result["isError"] else "실행"
            reason = result["content"][0]["text"]
        print(f"{i} {sc['client']:12} → {sc['target']} {sc['tool']:11} {verdict:6} {reason}")
        print(f"  └ {sc['who']}: {sc['note']}")
    for s in servers:
        s.shutdown()


if __name__ == "__main__":
    main()
