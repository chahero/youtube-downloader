#!/bin/bash

PID_FILE="app.pid"
LOG_DIR="logs"
LOG_FILE="$LOG_DIR/app.log"
ERROR_LOG="$LOG_DIR/error.log"

# logs 폴더 생성
mkdir -p $LOG_DIR

start() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat $PID_FILE)
        if ps -p $PID > /dev/null; then
            echo "✗ Already running (PID: $PID)"
            exit 1
        fi
    fi

    echo "Starting YouTube Downloader..."
    source venv/bin/activate
    nohup python app.py > $LOG_FILE 2> $ERROR_LOG &
    echo $! > $PID_FILE
    echo "✓ Server started! (PID: $!)"
    echo "  URL: http://localhost:5000"
    echo "  Log: tail -f $LOG_FILE"
}

stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo "✗ Server not running"
        exit 1
    fi

    PID=$(cat $PID_FILE)
    if ps -p $PID > /dev/null; then
        echo "Stopping server (PID: $PID)..."
        kill $PID
        rm $PID_FILE
        echo "✓ Server stopped"
    else
        echo "✗ Process not found"
        rm $PID_FILE
        exit 1
    fi
}

status() {
    if [ ! -f "$PID_FILE" ]; then
        echo "✗ Server is NOT running"
        exit 1
    fi

    PID=$(cat $PID_FILE)
    if ps -p $PID > /dev/null; then
        echo "✓ Server is running (PID: $PID)"
        echo "  URL: http://localhost:5000"
        echo ""
        echo "Recent logs:"
        tail -n 10 $LOG_FILE
    else
        echo "✗ Server is NOT running"
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