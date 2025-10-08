from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import threading
from datetime import datetime
from queue import Queue
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

app = Flask(__name__)

# 환경변수에서 설정 로드
DOWNLOAD_FOLDER = os.getenv('DOWNLOAD_FOLDER', './downloads')
MAX_CONCURRENT_DOWNLOADS = int(os.getenv('MAX_CONCURRENT_DOWNLOADS', 3))
FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'

os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# 다운로드 상태 및 취소 이벤트 저장
download_status = {}
cancel_events = {}
download_queue = Queue()
active_downloads = 0
lock = threading.Lock()

def download_worker():
    """대기열에서 다운로드를 처리하는 워커"""
    global active_downloads
    
    while True:
        video_id, url = download_queue.get()
        
        if video_id is None:  # 종료 신호
            break
        
        # 활성 다운로드 수 증가
        with lock:
            active_downloads += 1
        
        download_video(video_id, url)
        
        # 활성 다운로드 수 감소
        with lock:
            active_downloads -= 1
        
        download_queue.task_done()

def download_video(video_id, url):
    """백그라운드에서 비디오 다운로드"""
    try:
        download_status[video_id]['status'] = 'downloading'
        download_status[video_id]['message'] = '다운로드 중...'
        
        def progress_hook(d):
            # 취소 확인
            if cancel_events[video_id].is_set():
                raise Exception('사용자가 취소했습니다')
            
            if d['status'] == 'downloading':
                try:
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    downloaded = d.get('downloaded_bytes', 0)
                    
                    if total > 0:
                        percent = int((downloaded / total) * 100)
                        download_status[video_id]['progress'] = percent
                    else:
                        download_status[video_id]['progress'] = 0
                except:
                    pass
        
        ydl_opts = {
            'format': 'best',
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
            'progress_hooks': [progress_hook],
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
        
        download_status[video_id] = {
            'status': 'completed',
            'message': '다운로드 완료',
            'filename': os.path.basename(filename),
            'progress': 100
        }
        
    except Exception as e:
        if cancel_events[video_id].is_set():
            download_status[video_id] = {
                'status': 'cancelled',
                'message': '취소됨',
                'progress': 0
            }
        else:
            download_status[video_id] = {
                'status': 'error',
                'message': str(e),
                'progress': 0
            }

# 워커 스레드 시작
for _ in range(MAX_CONCURRENT_DOWNLOADS):
    worker = threading.Thread(target=download_worker, daemon=True)
    worker.start()

@app.route('/')
def index():
    return render_template('index.html', max_downloads=MAX_CONCURRENT_DOWNLOADS)

@app.route('/download', methods=['POST'])
def start_download():
    data = request.json
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'error': 'URL이 없습니다'}), 400
    
    video_id = f"video_{datetime.now().timestamp()}"
    
    # 취소 이벤트 생성
    cancel_events[video_id] = threading.Event()
    
    # 대기열 위치 계산
    with lock:
        queue_position = active_downloads + download_queue.qsize()
    
    if queue_position >= MAX_CONCURRENT_DOWNLOADS:
        download_status[video_id] = {
            'status': 'queued',
            'message': f'대기 중 ({queue_position - MAX_CONCURRENT_DOWNLOADS + 1}번째)',
            'progress': 0,
            'url': url
        }
    else:
        download_status[video_id] = {
            'status': 'queued',
            'message': '곧 시작...',
            'progress': 0,
            'url': url
        }
    
    # 대기열에 추가
    download_queue.put((video_id, url))
    
    return jsonify({
        'message': '다운로드 시작',
        'video_id': video_id
    })

@app.route('/status/<video_id>')
def get_status(video_id):
    status = download_status.get(video_id, {'status': 'not_found'})
    return jsonify(status)

@app.route('/cancel/<video_id>', methods=['POST'])
def cancel_download(video_id):
    if video_id in cancel_events:
        cancel_events[video_id].set()
        return jsonify({'message': '취소 요청됨'})
    return jsonify({'error': '찾을 수 없음'}), 404

@app.route('/delete/<video_id>', methods=['DELETE'])
def delete_download(video_id):
    """목록에서 다운로드 항목 삭제"""
    if video_id in download_status:
        # 진행 중인 다운로드는 삭제 불가
        status = download_status[video_id].get('status')
        if status in ['downloading', 'queued']:
            return jsonify({'error': '진행 중인 다운로드는 먼저 취소해주세요'}), 400
        
        # 상태에서 제거
        del download_status[video_id]
        if video_id in cancel_events:
            del cancel_events[video_id]
        
        return jsonify({'message': '삭제 완료'})
    
    return jsonify({'error': '찾을 수 없음'}), 404

@app.route('/download-file/<video_id>')
def download_file(video_id):
    """완료된 파일을 다운로드"""
    if video_id not in download_status:
        return jsonify({'error': '찾을 수 없음'}), 404
    
    status = download_status[video_id]
    
    if status.get('status') != 'completed':
        return jsonify({'error': '다운로드가 완료되지 않았습니다'}), 400
    
    filename = status.get('filename')
    if not filename:
        return jsonify({'error': '파일을 찾을 수 없습니다'}), 404
    
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': '파일이 존재하지 않습니다'}), 404
    
    return send_file(filepath, as_attachment=True, download_name=filename)

if __name__ == '__main__':
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG, threaded=True)