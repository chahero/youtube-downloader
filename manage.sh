#!/bin/bash

export PATH="/opt/homebrew/bin:$PATH"

# 실행할 파이썬 파일명
APP_FILE="app.py"

# 프로세스 ID(PID)를 저장할 파일명
PID_FILE="app.pid"

# 로그 파일을 저장할 디렉터리 및 파일명
LOG_DIR="logs"
LOG_FILE="$LOG_DIR/app.log"
ERROR_LOG="$LOG_DIR/error.log"
PYTHON_BIN="${PYTHON_BIN:-python3}"

# 로그 디렉터리 생성
mkdir -p $LOG_DIR

read_port() {
    PORT=$(awk -F= '/^PORT=/{print $2; exit}' .env 2>/dev/null | tr -d ' "\r')
    if [ -z "$PORT" ]; then
        PORT=5000
    fi
    echo "$PORT"
}

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
        "$PYTHON_BIN" -m venv .venv
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
    PORT=$(read_port)

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
        PORT=$(read_port)
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

logs() {
    echo "[app.log]"
    if [ -f "$LOG_FILE" ]; then
        tail -n 100 "$LOG_FILE"
    else
        echo "Missing $LOG_FILE"
    fi

    echo
    echo "[error.log]"
    if [ -f "$ERROR_LOG" ]; then
        tail -n 100 "$ERROR_LOG"
    else
        echo "Missing $ERROR_LOG"
    fi
}

health() {
    PORT=$(read_port)
    curl -fsS "http://127.0.0.1:${PORT}/" >/dev/null
    echo "OK http://127.0.0.1:${PORT}/"
}

redeploy() {
    set -e

    echo "[1/6] Pull latest source"
    git pull --ff-only

    echo "[2/6] Check environment file"
    test -f .env

    echo "[3/6] Ensure runtime dirs"
    mkdir -p downloads instance logs
    chmod +x manage.sh

    echo "[4/6] Prepare Python environment"
    if [ ! -d ".venv" ]; then
        "$PYTHON_BIN" -m venv .venv
    fi
    . .venv/bin/activate
    python -m pip install --upgrade pip
    pip install -r requirements.txt

    echo "[5/6] Restart app"
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null; then
            echo "Stopping server (PID: $PID)..."
            kill "$PID"
            rm "$PID_FILE"
            echo "✓ Server stopped."
        else
            echo "Process not found. Cleaning up PID file."
            rm "$PID_FILE"
        fi
    else
        echo "Server was not running."
    fi
    sleep 2
    start

    echo "[6/6] Health check"
    health
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
    redeploy)
        redeploy
        ;;
    logs)
        logs
        ;;
    health)
        health
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|redeploy|logs|health}"
        exit 1
        ;;
esac
