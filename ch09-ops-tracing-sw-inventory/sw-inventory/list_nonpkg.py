"""list_nonpkg.py — 수집 결과에서 OS 패키지 관리자 밖에 설치된 SW만 골라 보여 준다 (9장 실습 2)
사용법: python3 list_nonpkg.py [결과 파일 이름의 일부] [찾을 SW 이름 ...]
  예) python3 list_nonpkg.py web01
  예) python3 list_nonpkg.py web01 tomcat-catalina log4j-core

apt upgrade로는 고쳐지지 않는 SW(직접 설치한 실행 파일, WAS, pip 라이브러리 등)가 패치에서 가장 잘 빠진다.
그래서 그 부분만 따로 뽑아 담당자가 확인할 수 있게 한다.
"""
import sys
import json, glob
# inventories 폴더에서 이름에 첫 번째 인자가 들어간 결과 파일 중 첫 번째를 연다 (인자가 없으면 아무 파일이나 첫 번째)
d = json.load(open(glob.glob(f'inventories/*{sys.argv[1] if len(sys.argv) > 1 else ""}*.json')[0]))
# SBOM 결과는 수가 많으므로, 지정한 이름(기본: 실습에 나오는 네 가지)만 보여 준다
keys = sys.argv[2:] or ('tomcat-catalina', 'requests', 'urllib3', 'Jinja2')
for p in d['packages']:
    # manual(직접 설치한 실행 파일)은 모두, sbom-*은 이름이 keys와 같은 것만
    # (Java 패키지 이름은 "org.apache.tomcat:tomcat-catalina"처럼 생겼으므로 ':' 뒤만 비교한다)
    if p['source'] == 'manual' or (p['source'].startswith('sbom-') and any(k == p['name'].split(':')[-1] for k in keys)):
        print(f"{p['source']:15} {p['name']:38} {p['version']:10} {p.get('path','')[:60]}")
