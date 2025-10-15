#!/bin/bash

echo "=============================="
echo "YouTube Downloader"
echo "=============================="

# 가상환경이 없으면 생성
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# 가상환경 활성화
echo "Activating virtual environment..."
source venv/bin/activate

# 패키지 설치 (조용히)
echo "Installing packages..."
pip install -q -r requirements.txt

# Flask 앱 실행
echo ""
echo "=============================="
echo "Server started!"
echo "Access: http://localhost:5002"
echo "Press Ctrl+C to stop"
echo "=============================="
echo ""
python app.py