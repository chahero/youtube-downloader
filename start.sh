#!/bin/bash

echo "=============================="
echo "유튜브 다운로더 실행"
echo "=============================="

# 가상환경이 없으면 생성
if [ ! -d "venv" ]; then
    echo "가상환경 생성 중..."
    python3 -m venv venv
fi

# 가상환경 활성화
source venv/bin/activate

# 패키지 설치
echo "패키지 설치 중..."
pip install -r requirements.txt

# Flask 앱 실행
echo ""
echo "서버 시작..."
echo "브라우저에서 http://localhost:5000 접속"
echo ""
python app.py