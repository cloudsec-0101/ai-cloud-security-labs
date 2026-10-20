# zt.rego 정책의 테스트. 정책도 코드이므로, 고친 뒤에는 테스트로 의도대로 동작하는지 확인한다.
# 실행: docker compose exec opa opa test /policy -v
# 이름이 test_로 시작하는 규칙이 하나의 테스트이며, 규칙이 성립(참)하면 통과(PASS)다.
package zt_test

import data.zt

# 기준이 되는 정상 요청: 임직원 kim이 자기 관리 기기로 ERP를 읽는다
kim_ok := {"user": "kim", "roles": ["employee"], "app": "erp", "method": "GET",
	"device": {"managed": true, "owner": "kim", "edr": true, "patched": true}}

# 정상 요청은 허용되어야 한다
test_kim_erp_allowed if zt.decision.allow with input as kim_ok

# 등록되지 않은 기기면 같은 사람이라도 차단되어야 한다
# (object.union으로 kim_ok에서 device만 바꿔 끼운다)
test_unmanaged_device_denied if {
	not zt.decision.allow with input as object.union(kim_ok, {"device": {"managed": false}})
}

# 협력사(partner)는 ERP에 접근할 수 없고, 차단 사유에 "권한 없음"이 들어 있어야 한다
test_partner_erp_denied if {
	d := zt.decision with input as object.union(kim_ok, {"user": "lee", "roles": ["partner"],
		"device": {"managed": true, "owner": "lee", "edr": true, "patched": true}})
	"이 앱에 대한 권한 없음" in d.reasons
}

# 위험 점수 50이면 추가 인증(step_up)을 요구해야 한다
# (with data.risk as ...: detector 없이 위험 점수를 직접 넣어 시험한다)
test_high_risk_step_up if {
	d := zt.decision with input as kim_ok with data.risk as {"kim": 50}
	d.step_up
}

# 위험 점수 90이면 차단되어야 한다
test_very_high_risk_denied if {
	not zt.decision.allow with input as kim_ok with data.risk as {"kim": 90}
}
