<#
  collect_windows.ps1 — Windows Server의 OS와 설치 SW 버전을 자동 수집한다 (9장 실습 2)
  사용법: powershell -ExecutionPolicy Bypass -File .\collect_windows.ps1 [-OutDir .\inventories]
  Windows Server 2016/2019/2022/2025, Windows 10/11의 Windows PowerShell 5.1에서 동작한다.

  collect_linux.sh와 같은 형식(JSON)으로 결과를 남기므로, merge_report.py로 리눅스 결과와 함께 합칠 수 있다.
  수집 대상: ① 자산 식별자·OS ② 설치된 핫픽스 ③ 설치 프로그램(레지스트리) ④ 포트를 열고 있는 프로세스
  조회만 하고 아무것도 바꾸지 않는다. 관리자 권한으로 실행하면 ④에서 더 많은 프로세스 경로가 보인다.
#>
param([string]$OutDir = ".\inventories")
$ErrorActionPreference = "SilentlyContinue"   # 읽을 수 없는 항목이 있어도 멈추지 않고 계속 수집한다
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# 1) 자산 식별자: 호스트명은 겹칠 수 있으므로 MachineGuid를 함께 기록한다
$machineId = (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Cryptography").MachineGuid
$os = Get-CimInstance Win32_OperatingSystem   # OS 이름, 버전, 빌드 번호, 마지막 부팅 시각

# 2) 보안 업데이트(핫픽스)
#    설치일이 있는 것만 최신순으로 20개. 마지막 패치가 언제였는지 보는 것이 목적이다
$hotfix = Get-HotFix | Where-Object InstalledOn | Sort-Object InstalledOn -Descending |
  Select-Object -First 20 @{n="id";e={$_.HotFixID}}, @{n="installed_on";e={$_.InstalledOn.ToString("yyyy-MM-dd")}}

# 3) 설치 프로그램: 레지스트리 Uninstall 키 (64비트 + 32비트)
#    "프로그램 추가/제거"에 보이는 목록과 같다. 윈도우 구성 요소(SystemComponent)는 뺀다
$keys = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*"
$packages = Get-ItemProperty $keys | Where-Object { $_.DisplayName -and -not $_.SystemComponent } |
  Sort-Object DisplayName -Unique |
  ForEach-Object { [pscustomobject]@{ name = $_.DisplayName; version = "$($_.DisplayVersion)"; publisher = $_.Publisher; source = "registry" } }

# 4) 레지스트리에 없는 SW 찾기: 포트를 열고 대기 중인 프로세스의 실행 파일과 파일 버전
#    압축만 풀어 쓰는 WAS·에이전트처럼 설치 기록이 없는 SW도, 포트를 열고 있으면 여기서 드러난다
#    (외부에서 접근 가능한 SW일수록 취약점 대응이 급하므로 따로 모아 둔다)
$listening = Get-NetTCPConnection -State Listen | Select-Object -ExpandProperty OwningProcess -Unique |
  ForEach-Object { Get-Process -Id $_ } | Where-Object Path | Sort-Object Path -Unique |
  ForEach-Object {
    $vi = (Get-Item $_.Path).VersionInfo     # 실행하지 않고 파일에 기록된 버전 정보만 읽는다
    [pscustomobject]@{ name = $_.ProcessName; version = "$($vi.ProductVersion)"; path = $_.Path; source = "listening-process" }
  }

# 5) 결과를 JSON 파일 하나로 저장한다 (항목 이름은 collect_linux.sh와 맞춤)
$result = [ordered]@{
  host         = $env:COMPUTERNAME
  machine_id   = $machineId
  collected_at = (Get-Date).ToString("s")
  os           = [ordered]@{ name = $os.Caption; version = $os.Version; build = $os.BuildNumber; last_boot = $os.LastBootUpTime.ToString("s") }
  hotfixes     = @($hotfix)
  packages     = @($packages) + @($listening)
}
$out = Join-Path $OutDir ("inventory-{0}-{1}.json" -f $env:COMPUTERNAME, $machineId.Substring(0, 8))
$result | ConvertTo-Json -Depth 5 | Out-File -Encoding utf8 $out
"수집 완료: {0} | {1} ({2})" -f $env:COMPUTERNAME, $os.Caption, $os.Version
"  핫픽스 {0}개 | 설치 SW(레지스트리) {1}개 | 포트 대기 프로세스 {2}개" -f @($hotfix).Count, @($packages).Count, @($listening).Count
"  결과 파일: {0}" -f $out
