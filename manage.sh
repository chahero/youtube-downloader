#!/bin/bash

# 실행할 파이썬 파일명
APP_FILE="app.py"

# 프로세스 ID(PID)를 저장할 파일명
PID_FILE="app.pid"

# 로그 파일을 저장할 디렉터리 및 파일명
LOG_DIR="logs"
LOG_FILE="$LOG_DIR/app.log"
ERROR_LOG="$LOG_DIR/error.log"

# 로그 디렉터리 생성
mkdir -p $LOG_DIR

start() {
    # 이미 실행 중인지 확인
    if [ -f "$PID_FILE" ]; then
        PID=$(cat $PID_FILE)
        if ps -p $PID > /dev/null; then
            echo "✗ App is already running (PID: $PID)"
            exit 1
        fi
    fi

    # 가상환경(.venv)이 없으면 생성
    if [ ! -d ".venv" ]; then
        echo "Creating virtual environment..."
        python -m venv .venv
    fi

    # 가상환경 활성화
    source .venv/bin/activate

    # requirements.txt 파일이 있으면 패키지 설치
    if [ -f "requirements.txt" ]; then
        echo "Checking dependencies..."
        pip install -q -r requirements.txt
    fi

    echo "🎬 Starting App..."
    # 백그라운드에서 nohup으로 앱 실행, 로그 파일에 출력 저장
    nohup python $APP_FILE > $LOG_FILE 2> $ERROR_LOG &
    
    # 실행된 프로세스의 PID를 파일에 저장
    echo $! > $PID_FILE
    
    # .env 파일에서 포트 번호 읽어오기 (없으면 5000)
    PORT=$(grep PORT .env | cut -d '=' -f2)
    if [ -z "$PORT" ]; then
        PORT=5000
    fi

    echo "✓ Server started! (PID: $!)"
    echo "  URL: http://localhost:$PORT"
    echo "  Log: tail -f $LOG_FILE"
}

stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo "✗ Server not running."
        exit 1
    fi

    PID=$(cat $PID_FILE)
    if ps -p $PID > /dev/null; then
        echo "Stopping server (PID: $PID)..."
        kill $PID
        rm $PID_FILE
        echo "✓ Server stopped."
    else
        echo "✗ Process not found. Cleaning up PID file."
        rm $PID_FILE
        exit 1
    fi
}

status() {
    if [ ! -f "$PID_FILE" ]; then
        echo "✗ Server is NOT running."
        exit 1
    fi

    PID=$(cat $PID_FILE)
    if ps -p $PID > /dev/null; then
        PORT=$(grep PORT .env | cut -d '=' -f2)
        if [ -z "$PORT" ]; then
            PORT=5000
        fi
        echo "✓ Server is running (PID: $PID)"
        echo "  URL: http://localhost:$PORT"
        echo ""
        echo "Recent logs:"
        tail -n 10 $LOG_FILE
    else
        echo "✗ Server is NOT running, but PID file exists. Cleaning up."
        rm $PID_FILE
        exit 1
    fi
}

restart() {
    echo "Restarting server..."
    stop
    sleep 2
    start
}

# 사용자가 입력한 인자에 따라 함수 실행
case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac