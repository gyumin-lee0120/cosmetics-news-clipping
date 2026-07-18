"""텔레그램 아침 브리핑 발송 스크립트.

매일 GitHub Actions에서 데이터 수집 직후 실행되어,
오늘의 뉴스 헤드라인 · KPI 지표 · 트렌드 데이터 · 다가오는 전시회를
텔레그램 메시지 한 통으로 요약해 보냅니다.

필요 환경변수:
  TELEGRAM_BOT_TOKEN  (BotFather에서 발급받은 봇 토큰)
  TELEGRAM_CHAT_ID    (메시지를 받을 개인/그룹 채팅 ID)

두 값이 없으면 조용히 건너뜁니다 (아직 봇 설정 전이어도 파이프라인은 안 깨지도록).
"""
import html
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "collectors"))
from
