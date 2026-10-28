# AI 보안, 클라우드에서 시작한다 — 실습 코드

> 클라우드 네이티브에서 Agentic AI까지, 기업 AI 보안 아키텍처와 실무 로드맵

책 『AI 보안, 클라우드에서 시작한다』의 장별 [실습] 코드와 단계별 안내를 모은 저장소입니다. 각 폴더의 `README.md`에 실습 순서와 실행 결과 화면이 있습니다.

## 처음 시작할 때: [SETUP.md](./SETUP.md)

코드 실습(2·4~10장)을 하기 전에 **[SETUP.md](./SETUP.md)를 한 번만 해 두세요.** Windows PC에 WSL2·Ubuntu·Docker·Trivy를 설치하고, 이 저장소를 `~/ai-cloud-security-labs`로 내려받고, (선택) VS Code와 Jupyter 노트북을 연결하는 과정을 화면과 함께 안내합니다. 단계마다 "이렇게 보이면 성공"이 있고, 막혔을 때 볼 표도 있습니다. 그다음에는 장 순서와 상관없이 어느 장의 실습이든 바로 시작할 수 있습니다. 1·3장처럼 손으로 하는 실습은 책 본문만 있으면 됩니다.

## 장별 실습

| 장 | 폴더 | 내용 | 코드 파일 수 |
|---|---|---|---|
| 1장 | [ch01-shared-responsibility](./ch01-shared-responsibility) | 클라우드 보안의 시작 — 책임공유모델 워크시트 | 0 |
| 2장 | [ch02-container-security](./ch02-container-security) | 클라우드 네이티브 환경과 보안 — 컨테이너 격리와 Pod 보안 설정 | 2 |
| 3장 | [ch03-ai-nondeterminism-prompt-injection](./ch03-ai-nondeterminism-prompt-injection) | AI가 바꾼 기업 IT와 보안 — 비결정성, 프롬프트 주입, AI 책임공유모델 | 0 |
| 4장 | [ch04-ai-usage-types](./ch04-ai-usage-types) | 기업의 AI 사용 유형별 보안 — 데이터 처리 옵션, 사용 유형 자가진단, 키 유출 탐지 | 1 |
| 5장 | [ch05-agent-mcp-security](./ch05-agent-mcp-security) | Agentic AI와 PaaS 개발환경 보안 — MCP 권한, 간접 주입, Egress 통제 | 8 |
| 6장 | [ch06-aiaas-vendor-evaluation](./ch06-aiaas-vendor-evaluation) | AIaaS의 이해와 환경별 보안 — 약관 검토, 가명처리 검문소, 공급자 전환 리허설 | 10 |
| 7장 | [ch07-zero-trust-lab](./ch07-zero-trust-lab) | 제로트러스트 기반 AI Cloud 보안 아키텍처 — 4계층 점검표, 미니 제로트러스트 랩, RAG 문서 권한 | 13 |
| 8장 | [ch08-devsecops-image-gate](./ch08-devsecops-image-gate) | AI 서비스 개발 보안 — 이미지 CVE 게이트, Jailbreak 성공률, Agent 간접 주입·기억 오염 방어, MCP 간 호출 인증, Skill·MCP 반입 검사 | 30 |
| 9장 | [ch09-ops-tracing-sw-inventory](./ch09-ops-tracing-sw-inventory) | AI 서비스 운영 보안 — SW 버전 자동 수집, Trace ID와 로그 마스킹, 패치·확인·Workaround | 19 |
| 10장 | [ch10-policy-as-code-shadow-ai](./ch10-policy-as-code-shadow-ai) | AI 시대 기업 보안 체계와 전환 로드맵 — 정책을 코드로 집행하기, Shadow AI 발견 | 11 |

## Jupyter 노트북

코드 실습은 README의 단계를 Jupyter 노트북에서 셀 단위로 실행하는 버전도 있습니다. 노트북마다 직접 실행할 버전(출력 없음)과 실행 결과가 저장된 버전(`_executed`) 두 개를 둡니다. 노트북마다 학습 목표, 단계별 설명, 실행 결과, 체크포인트와 과제(힌트 포함)가 들어 있고, `_executed` 버전에 저장된 출력은 2026년 10월 23일 WSL2의 Ubuntu 24.04에서 실제로 실행한 결과입니다.

- 실행 환경: WSL2의 Ubuntu 24.04 + Docker. 노트북의 `%%bash` 셀은 리눅스 명령으로 실행됩니다.
- 준비: [SETUP.md](./SETUP.md) 6단계에 VS Code 연결과 커널 고르기를 화면 순서대로 안내했습니다. 요약하면 `sudo apt install -y python3-venv` → `python3 -m venv ~/.venv-lab` → `~/.venv-lab/bin/pip install jupyterlab ipykernel` 뒤, Ubuntu 터미널에서 `cd ~/ai-cloud-security-labs && code .`로 열고 `~/.venv-lab`의 Python을 커널로 고릅니다. 브라우저에서 하려면 노트북이 있는 장 폴더에서 `~/.venv-lab/bin/jupyter lab`을 실행합니다.
- 노트북은 실습 파일을 홈 디렉터리의 작업 폴더로 복사해 실행하므로, 저장소의 원본 파일은 바뀌지 않습니다.

| 장 | 노트북(직접 실행) | 실행 결과 포함 |
|---|---|---|
| 2장 | [ch02_lab1_container_isolation.ipynb](./ch02-container-security/ch02_lab1_container_isolation.ipynb) | [ch02_lab1_container_isolation_executed.ipynb](./ch02-container-security/ch02_lab1_container_isolation_executed.ipynb) |
| 4장 | [ch04_lab3_gitleaks_api_key.ipynb](./ch04-ai-usage-types/ch04_lab3_gitleaks_api_key.ipynb) | [ch04_lab3_gitleaks_api_key_executed.ipynb](./ch04-ai-usage-types/ch04_lab3_gitleaks_api_key_executed.ipynb) |
| 5장 | [ch05_lab1_mcp_least_privilege.ipynb](./ch05-agent-mcp-security/ch05_lab1_mcp_least_privilege.ipynb) | [ch05_lab1_mcp_least_privilege_executed.ipynb](./ch05-agent-mcp-security/ch05_lab1_mcp_least_privilege_executed.ipynb) |
| 5장 | [ch05_lab2_indirect_prompt_injection.ipynb](./ch05-agent-mcp-security/ch05_lab2_indirect_prompt_injection.ipynb) | [ch05_lab2_indirect_prompt_injection_executed.ipynb](./ch05-agent-mcp-security/ch05_lab2_indirect_prompt_injection_executed.ipynb) |
| 5장 | [ch05_lab3_egress_allowlist.ipynb](./ch05-agent-mcp-security/ch05_lab3_egress_allowlist.ipynb) | [ch05_lab3_egress_allowlist_executed.ipynb](./ch05-agent-mcp-security/ch05_lab3_egress_allowlist_executed.ipynb) |
| 6장 | [ch06_lab2_pseudonymization_checkpoint.ipynb](./ch06-aiaas-vendor-evaluation/ch06_lab2_pseudonymization_checkpoint.ipynb) | [ch06_lab2_pseudonymization_checkpoint_executed.ipynb](./ch06-aiaas-vendor-evaluation/ch06_lab2_pseudonymization_checkpoint_executed.ipynb) |
| 6장 | [ch06_lab3_exit_rehearsal.ipynb](./ch06-aiaas-vendor-evaluation/ch06_lab3_exit_rehearsal.ipynb) | [ch06_lab3_exit_rehearsal_executed.ipynb](./ch06-aiaas-vendor-evaluation/ch06_lab3_exit_rehearsal_executed.ipynb) |
| 7장 | [ch07_lab2_mini_zero_trust.ipynb](./ch07-zero-trust-lab/ch07_lab2_mini_zero_trust.ipynb) | [ch07_lab2_mini_zero_trust_executed.ipynb](./ch07-zero-trust-lab/ch07_lab2_mini_zero_trust_executed.ipynb) |
| 7장 | [ch07_lab3_rag_document_acl.ipynb](./ch07-zero-trust-lab/ch07_lab3_rag_document_acl.ipynb) | [ch07_lab3_rag_document_acl_executed.ipynb](./ch07-zero-trust-lab/ch07_lab3_rag_document_acl_executed.ipynb) |
| 8장 | [ch08_lab1_image_cve_gate.ipynb](./ch08-devsecops-image-gate/ch08_lab1_image_cve_gate.ipynb) | [ch08_lab1_image_cve_gate_executed.ipynb](./ch08-devsecops-image-gate/ch08_lab1_image_cve_gate_executed.ipynb) |
| 8장 | [ch08_lab2_garak_jailbreak_rate.ipynb](./ch08-devsecops-image-gate/ch08_lab2_garak_jailbreak_rate.ipynb) | [ch08_lab2_garak_jailbreak_rate_executed.ipynb](./ch08-devsecops-image-gate/ch08_lab2_garak_jailbreak_rate_executed.ipynb) |
| 8장 | [ch08_lab3_agent_tool_guard.ipynb](./ch08-devsecops-image-gate/ch08_lab3_agent_tool_guard.ipynb) | [ch08_lab3_agent_tool_guard_executed.ipynb](./ch08-devsecops-image-gate/ch08_lab3_agent_tool_guard_executed.ipynb) |
| 8장 | [ch08_lab4_mcp_caller_auth.ipynb](./ch08-devsecops-image-gate/ch08_lab4_mcp_caller_auth.ipynb) | [ch08_lab4_mcp_caller_auth_executed.ipynb](./ch08-devsecops-image-gate/ch08_lab4_mcp_caller_auth_executed.ipynb) |
| 8장 | [ch08_lab5_agent_component_intake.ipynb](./ch08-devsecops-image-gate/ch08_lab5_agent_component_intake.ipynb) | [ch08_lab5_agent_component_intake_executed.ipynb](./ch08-devsecops-image-gate/ch08_lab5_agent_component_intake_executed.ipynb) |
| 9장 | [ch09_lab1_sw_inventory.ipynb](./ch09-ops-tracing-sw-inventory/ch09_lab1_sw_inventory.ipynb) | [ch09_lab1_sw_inventory_executed.ipynb](./ch09-ops-tracing-sw-inventory/ch09_lab1_sw_inventory_executed.ipynb) |
| 9장 | [ch09_lab2_trace_id_masking.ipynb](./ch09-ops-tracing-sw-inventory/ch09_lab2_trace_id_masking.ipynb) | [ch09_lab2_trace_id_masking_executed.ipynb](./ch09-ops-tracing-sw-inventory/ch09_lab2_trace_id_masking_executed.ipynb) |
| 9장 | [ch09_lab3_patch_verify_workaround.ipynb](./ch09-ops-tracing-sw-inventory/ch09_lab3_patch_verify_workaround.ipynb) | [ch09_lab3_patch_verify_workaround_executed.ipynb](./ch09-ops-tracing-sw-inventory/ch09_lab3_patch_verify_workaround_executed.ipynb) |
| 10장 | [ch10_lab1_policy_as_code.ipynb](./ch10-policy-as-code-shadow-ai/ch10_lab1_policy_as_code.ipynb) | [ch10_lab1_policy_as_code_executed.ipynb](./ch10-policy-as-code-shadow-ai/ch10_lab1_policy_as_code_executed.ipynb) |
| 10장 | [ch10_lab2_shadow_ai.ipynb](./ch10-policy-as-code-shadow-ai/ch10_lab2_shadow_ai.ipynb) | [ch10_lab2_shadow_ai_executed.ipynb](./ch10-policy-as-code-shadow-ai/ch10_lab2_shadow_ai_executed.ipynb) |

## 실습 환경

- 대부분의 실습은 Windows PC 한 대로 할 수 있습니다. 리눅스와 Docker가 필요한 실습(2·5·6·7·8·9·10장)은 WSL2의 Ubuntu 24.04에서 확인했습니다. 설치 방법은 위 [처음 시작할 때]를 보세요.
- 확인한 버전: Windows 11 Pro, WSL 3.0.3, Ubuntu 24.04, Docker 29.1.3, Docker Compose 2.40.3, Trivy 0.76.0, Python 3.12, Keycloak 26.0.7, OPA 1.0.0

## 주의

- 모든 실습은 실습용 계정과 실습용 환경에서만 실행하세요. 운영 시스템이나 회사 계정에서 실행하지 마세요.
- 실습 코드에 들어 있는 계정과 비밀번호(예: `Passw0rd!`)는 실습용입니다. 실제 환경에서는 쓰지 마세요.
- 가짜 API Key 예시(`sk-test-...`)는 Secret 스캐닝 실습용 문자열이며 실제 키가 아닙니다.

## 라이선스

라이선스는 공개 전에 정합니다(예: 코드는 MIT, 문서는 CC BY-NC 4.0).
