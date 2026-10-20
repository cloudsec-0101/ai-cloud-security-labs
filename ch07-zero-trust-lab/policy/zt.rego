# ② 정책 엔진(PDP): 요청마다 신원·기기·위험 점수를 함께 보고 판단한다
#
# 입력(input)은 pep.py가 보내 준다:
#   {"user": "kim", "roles": ["employee"], "app": "erp", "method": "GET",
#    "device": {"managed": true, "owner": "kim", "edr": true, "patched": true}, "country": "KR"}
# 위험 점수(data.risk)는 detector.py가 계속 갱신한다: {"kim": 50, ...}
# 출력(decision)은 {"allow": 참/거짓, "step_up": 참/거짓, "reasons": 사유 목록}이다.
#
# Rego 읽는 법(처음 보는 사람을 위해)
#   규칙 이름 if { 조건1; 조건2 }   → 중괄호 안의 조건이 "모두" 참이면 규칙이 성립한다
#   deny contains "사유" if {...}  → 조건이 맞으면 deny 집합에 "사유"를 하나 넣는다 (같은 이름의 규칙을 여러 개 써서 사유를 모은다)
#   default x := 값                → 다른 규칙이 성립하지 않을 때 쓸 기본값
package zt

# 위험 점수: detector가 아직 점수를 넣지 않은 사용자는 0점으로 본다
default risk := 0

risk := data.risk[input.user] if data.risk[input.user]

# 어떤 역할이 어떤 앱에 접근할 수 있는가
#   erp는 임직원만, AI 챗봇은 임직원과 협력사 모두 허용
app_roles := {
	"erp":    {"employee"},
	"aichat": {"employee", "partner"},
}

# 차단 사유 (하나라도 있으면 차단)
# Zero Trust는 "로그인했으니 통과"가 아니라, 신원·기기·권한·상태를 요청마다 다시 확인한다

# 기기 확인 1: 회사가 관리(MDM 등록)하는 기기인가
deny contains "등록되지 않은 기기" if not input.device.managed

# 기기 확인 2: 남의 기기를 빌려 쓰는 것은 아닌가
deny contains "기기 소유자 불일치" if {
	input.device.managed
	input.device.owner != input.user
}

# 기기 확인 3: 백신·EDR이 켜져 있는가
deny contains "EDR 미동작 기기" if {
	input.device.managed
	not input.device.edr
}

# 권한 확인: 사용자의 역할 중 이 앱에 허용된 역할이 하나라도 있는가 (교집합의 크기가 0이면 차단)
deny contains "이 앱에 대한 권한 없음" if {
	count({r | some r in input.roles; r in app_roles[input.app]}) == 0
}

# 요청 내용까지 본다: 읽기(GET)는 허용하되, 패치가 안 된 기기의 쓰기는 막는다
deny contains "보안 패치 미적용 기기로 쓰기 요청" if {
	input.method != "GET"
	not input.device.patched
}

# 위험 점수가 70 이상이면 차단
deny contains sprintf("위험 점수 %d (70 이상 차단)", [risk]) if risk >= 70

# 차단은 아니지만 추가 인증이 필요한 경우
#   위험 점수 40~69: 바로 막기보다 MFA 같은 추가 확인을 요구한다 (Step-up 인증)
step_up if {
	risk >= 40
	risk < 70
}

# 최종 결정: 아래 세 경우 중 정확히 하나만 성립하도록 조건을 나눴다
# 1) 차단 사유가 있으면 → 차단
decision := {"allow": false, "step_up": false, "reasons": deny} if count(deny) > 0

# 2) 차단 사유는 없지만 위험 점수가 애매하면 → 추가 인증 요구
decision := {"allow": false, "step_up": true, "reasons": {sprintf("위험 점수 %d: 추가 인증 필요", [risk])}} if {
	count(deny) == 0
	step_up
}

# 3) 아무 문제가 없으면 → 허용
decision := {"allow": true, "step_up": false, "reasons": set()} if {
	count(deny) == 0
	not step_up
}
