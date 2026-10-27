# AI 자산 등록 정책 (10-2의 표 10-5 위험 등급, 10-2 책임 조직, 10-3 허용 목록)
# 위반 메시지는 "자산 ID [분류] 이름: 내용" 형식입니다.
#
# 읽는 데이터: data.assets(등록된 AI 자산), data.mcp_servers(승인 MCP 목록) — registry/ai-assets.yaml
#              input.today(기준일) — check.sh가 넣어 줌
# 구조: 앞부분은 "등급을 어떻게 정하나"(계산), 뒷부분 1~7은 "무엇을 위반으로 보나"(deny 규칙)입니다.
# Rego에서 같은 이름의 deny 규칙을 여러 개 쓰면, 각 규칙이 찾은 메시지가 하나의 집합으로 모입니다.
package aigov

# 등급 순서
rank := {"낮음": 0, "중간": 1, "높음": 2, "매우 높음": 3}

# 데이터와 행동으로 정해지는 기준 등급 (표 10-5)
# if ... else 사슬: 위에서부터 차례로 검사해 처음 맞는 등급을 쓴다 (외부 전송·실제 변경이 있으면 바로 "매우 높음")
required_grade(a) := "매우 높음" if {
	some x in ["external_send", "executes_changes"]
	a.data[x] == true
} else := "높음" if {
	some x in ["personal_or_confidential", "internet_exposed"]
	a.data[x] == true
} else := "중간" if {
	a.data.internal_read == true
} else := "낮음"

# 신고 등급 (비어 있거나 잘못된 값이면 기준 등급만 본다)
declared(a) := a.declared_grade if {
	rank[a.declared_grade] >= 0
} else := "낮음"

# 실제로 적용할 등급: 신고 등급과 기준 등급 중 높은 쪽
grade(a) := required_grade(a) if {
	rank[required_grade(a)] > rank[declared(a)]
} else := declared(a)

# 등급별 승인 주체, 필요한 테스트, 재평가 주기 (표 10-5)
# 승인 주체는 "이 중 하나면 된다"는 집합이다. 상위 기관의 승인은 하위 등급에서도 인정된다
approvers := {
	"매우 높음": {"보안위원회"},
	"높음": {"보안팀", "보안위원회"},
	"중간": {"부서장", "보안팀", "보안위원회"},
	"낮음": {"등록만", "부서장", "보안팀", "보안위원회"},
}

approver_text := {"매우 높음": "보안위원회", "높음": "보안팀 이상", "중간": "부서장 이상", "낮음": "등록"}

tests_required := {
	"매우 높음": ["security_test", "agent_scenario_test"],
	"높음": ["security_test"],
	"중간": [],
	"낮음": [],
}

check_label := {"security_test": "보안 테스트", "agent_scenario_test": "Agent 시나리오 테스트"}

review_days := {"매우 높음": 90, "높음": 180, "중간": 365}

# 통제 항목 값을 꺼낸다. 비어 있거나 없으면 "없음"으로 통일해 메시지에 그대로 쓸 수 있게 한다
control(a, k) := v if {
	v := a.controls[k]
	v != null
	v != ""
} else := "없음"

# 1. 책임: 소유 부서와 최종 책임자(A) 한 명 (10-2의 책임 조직)
owner_label := {"owner_dept": "소유 부서", "accountable": "최종 책임자(A)"}

deny contains msg if {
	some a in data.assets
	some f, label in owner_label
	object.get(a, f, "") in {"", null}
	msg := sprintf("%s [책임] %s: %s가 비어 있습니다", [a.id, a.name, label])
}

# 2. 등급: 신고 등급이 기준 등급보다 낮으면 안 된다
deny contains msg if {
	some a in data.assets
	not rank[a.declared_grade]
	msg := sprintf("%s [등급] %s: 위험 등급이 정해지지 않았습니다 (기준 등급 '%s')", [a.id, a.name, required_grade(a)])
}

deny contains msg if {
	some a in data.assets
	rank[required_grade(a)] > rank[a.declared_grade]
	msg := sprintf("%s [등급] %s: 신고 등급(%s)이 기준 등급(%s)보다 낮습니다", [a.id, a.name, a.declared_grade, required_grade(a)])
}

# 3. 승인: 운영 중인 자산은 등급에 맞는 곳의 승인이 있어야 한다
deny contains msg if {
	some a in data.assets
	a.status == "운영"
	g := grade(a)
	not control(a, "approved_by") in approvers[g]
	msg := sprintf("%s [승인] %s: '%s' 등급은 %s 승인이 필요합니다 (현재 %s)", [a.id, a.name, g, approver_text[g], control(a, "approved_by")])
}

# 4. 테스트: 등급별 배포 전 테스트 통과 기록
deny contains msg if {
	some a in data.assets
	a.status == "운영"
	g := grade(a)
	some t in tests_required[g]
	control(a, t) != "통과"
	msg := sprintf("%s [테스트] %s: '%s' 등급은 %s 통과 기록이 필요합니다 (현재 %s)", [a.id, a.name, g, check_label[t], control(a, t)])
}

# 5. 통제: 매우 높음 등급은 사람 승인과 Kill Switch
control_label := {"human_approval": "사람 승인", "kill_switch": "Kill Switch"}

deny contains msg if {
	some a in data.assets
	grade(a) == "매우 높음"
	some c, label in control_label
	not a.controls[c] == true
	msg := sprintf("%s [통제] %s: '매우 높음' 등급인데 %s 통제가 꺼져 있습니다", [a.id, a.name, label])
}

# 6. 재평가: 등급별 주기를 넘기지 않는다
# 날짜 두 개를 나노초로 바꿔 뺀 뒤 하루(24×60×60×10^9 나노초)로 나눠 경과 일수를 구한다
# ("2006-01-02"는 날짜 형식을 나타내는 Go 언어의 약속된 표기)
days_since(d) := floor((time.parse_ns("2006-01-02", input.today) - time.parse_ns("2006-01-02", d)) / ((24 * 60) * 60e9))

deny contains msg if {
	some a in data.assets
	g := grade(a)
	limit := review_days[g]
	last := control(a, "last_review")
	last != "없음"
	days_since(last) > limit
	msg := sprintf("%s [재평가] %s: 마지막 평가 %s 이후 %d일, '%s' 등급의 주기 %d일을 넘었습니다", [a.id, a.name, last, days_since(last), g, limit])
}

deny contains msg if {
	some a in data.assets
	review_days[grade(a)]
	control(a, "last_review") == "없음"
	msg := sprintf("%s [재평가] %s: 위험평가 기록이 없습니다", [a.id, a.name])
}

# 7. Tool: Agent는 승인된 MCP Server만 쓴다 (10-3 허용 목록)
approved_mcp := {m.id | some m in data.mcp_servers; m.status == "승인"}

deny contains msg if {
	some a in data.assets
	some t in object.get(a, "tools", [])
	not t in approved_mcp
	msg := sprintf("%s [Tool] %s: %s는 승인된 MCP Server 목록에 없습니다", [a.id, a.name, t])
}
