# AI 보안, 클라우드에서 시작한다 — 실습 코드

> 클라우드 네이티브에서 Agentic AI까지, 기업 AI 보안 아키텍처와 실무 로드맵

책 『AI 보안, 클라우드에서 시작한다』의 장별 [실습] 코드와 단계별 안내를 모은 저장소입니다. 각 폴더의 `README.md`에 실습 순서와 실행 결과 화면이 있습니다.

| 장 | 폴더 | 내용 | 코드 파일 수 |
|---|---|---|---|
| 1장 | [ch01-shared-responsibility](./ch01-shared-responsibility) | 클라우드 보안의 시작 — 공동책임모델 워크시트 | 0 |
| 2장 | [ch02-container-security](./ch02-container-security) | 클라우드 네이티브 환경과 보안 — 컨테이너 격리와 Pod 보안 설정 | 2 |
| 3장 | [ch03-ai-nondeterminism-prompt-injection](./ch03-ai-nondeterminism-prompt-injection) | AI가 바꾼 기업 IT와 보안 — 비결정성, 프롬프트 주입, AI 책임공유모델 | 0 |
| 4장 | [ch04-ai-usage-types](./ch04-ai-usage-types) | 기업의 AI 사용 유형별 보안 — 데이터 처리 옵션, 사용 유형 자가진단, 키 유출 탐지 | 1 |
| 5장 | [ch05-agent-mcp-security](./ch05-agent-mcp-security) | Agentic AI와 PaaS 개발환경 보안 — MCP 권한, 간접 주입, Egress 통제 | 8 |
| 6장 | [ch06-aiaas-vendor-evaluation](./ch06-aiaas-vendor-evaluation) | AIaaS의 이해와 환경별 보안 — 약관 검토, 가명처리 검문소, 공급자 전환 리허설 | 10 |
| 7장 | [ch07-zero-trust-lab](./ch07-zero-trust-lab) | 제로트러스트 기반 AI Cloud 보안 아키텍처 — RAG 문서 권한, 미니 제로트러스트 랩 | 13 |
| 8장 | [ch08-devsecops-image-gate](./ch08-devsecops-image-gate) | AI 서비스 개발 보안 — 이미지 CVE 게이트, Jailbreak 성공률, Agent Tool 호출 검증 | 12 |
| 9장 | [ch09-ops-tracing-sw-inventory](./ch09-ops-tracing-sw-inventory) | AI 서비스 운영 보안 — SW 버전 자동 수집, Trace ID와 로그 마스킹, 클라우드 지원 종료 대조, 패치·확인·Workaround | 19 |
| 10장 | [ch10-policy-as-code-shadow-ai](./ch10-policy-as-code-shadow-ai) | AI 시대 기업 보안 체계와 전환 로드맵 — 정책을 코드로 집행하기, Shadow AI 발견 | 11 |

## 실습 환경

- 대부분의 실습은 Windows PC 한 대로 할 수 있습니다. 리눅스와 Docker가 필요한 실습(2·5·6·7·8·9·10장)은 WSL2의 Ubuntu 24.04에서 확인했습니다. 설치 방법은 [8장 README](./ch08-devsecops-image-gate/README.md)의 [실습 준비]를 보세요.
- 확인한 버전: Windows 11 Pro, WSL 3.0.3, Ubuntu 24.04, Docker 29.1.3, Docker Compose 2.40.3, Trivy 0.76.0, Python 3.12, Keycloak 26.0.7, OPA 1.0.0

## 주의

- 모든 실습은 실습용 계정과 실습용 환경에서만 실행하세요. 운영 시스템이나 회사 계정에서 실행하지 마세요.
- 실습 코드에 들어 있는 계정과 비밀번호(예: `Passw0rd!`)는 실습용입니다. 실제 환경에서는 쓰지 마세요.
- 가짜 API Key 예시(`sk-test-...`)는 Secret 스캐닝 실습용 문자열이며 실제 키가 아닙니다.

## 라이선스

라이선스는 공개 전에 정합니다(예: 코드는 MIT, 문서는 CC BY-NC 4.0).
