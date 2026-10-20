# 정책 자체의 테스트: opa test policy/ -v
package aigov_test

import data.aigov

agent := {
	"id": "T-1", "name": "시험 Agent", "type": "Agent", "status": "운영",
	"owner_dept": "구매팀", "accountable": "홍길동", "declared_grade": "매우 높음",
	"data": {"executes_changes": true},
	"controls": {
		"approved_by": "보안위원회", "security_test": "통과", "agent_scenario_test": "통과",
		"human_approval": true, "kill_switch": true, "last_review": "2026-10-01",
	},
}

deny_for(a) := d if {
	d := aigov.deny with data.assets as [a] with data.mcp_servers as [] with input.today as "2026-10-20"
}

# 모든 기준을 갖춘 Agent는 통과한다
test_compliant_agent_passes if {
	count(deny_for(agent)) == 0
}

# Kill Switch가 꺼지면 위반이다
test_missing_kill_switch_denied if {
	a := json.patch(agent, [{"op": "replace", "path": "/controls/kill_switch", "value": false}])
	some m in deny_for(a)
	contains(m, "Kill Switch")
}

# 신고 등급을 낮춰도 데이터와 행동으로 정해지는 기준 등급은 그대로다
test_grade_follows_data if {
	a := object.union(agent, {"declared_grade": "중간"})
	aigov.required_grade(a) == "매우 높음"
	some m in deny_for(a)
	contains(m, "[등급]")
}

# 승인되지 않은 MCP Server를 쓰면 위반이다
test_unapproved_tool_denied if {
	a := object.union(agent, {"tools": ["MCP-X"]})
	some m in deny_for(a)
	contains(m, "MCP-X")
}
