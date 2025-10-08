from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import threading
from datetime import datetime
from queue import Queue
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

DOWNLOAD_FOLDER = os.getenv('DOWNLOAD_FOLDER', './downloads')
MAX_CONCURRENT_DOWNLOADS = int(os.getenv('MAX_CONCURRENT_DOWNLOADS', 3))
FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'

os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

download_status = {}
cancel_events = {}
download_queue = Queue()
active_downloads = 0
lock = threading.Lock()

def download_worker():
    global active_downloads
    
    while True:
        video_id, url = download_queue.get()
        
        if video_id is None:
            break
        
        with lock:
            active_downloads += 1
        
        download_video(video_id, url)
        
        with lock:
            active_downloads -= 1
        
        download_queue.task_done()

def download_video(video_id, url):
    try:
        download_status[video_id]['status'] = 'downloading'
        download_status[video_id]['message'] = 'Downloading...'
        
        def progress_hook(d):
            if cancel_events[video_id].is_set():
                raise Exception('Cancelled by user')
            
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
            'message': 'Download completed',
            'filename': os.path.basename(filename),
            'progress': 100
        }
        
    except Exception as e:
        if cancel_events[video_id].is_set():
            download_status[video_id] = {
                'status': 'cancelled',
                'message': 'Cancelled',
                'progress': 0
            }
        else:
            download_status[video_id] = {
                'status': 'error',
                'message': str(e),
                'progress': 0
            }

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
        return jsonify({'error': 'No URL provided'}), 400
    
    video_id = f"video_{datetime.now().timestamp()}"
    
    cancel_events[video_id] = threading.Event()
    
    with lock:
        queue_position = active_downloads + download_queue.qsize()
    
    if queue_position >= MAX_CONCURRENT_DOWNLOADS:
        download_status[video_id] = {
            'status': 'queued',
            'message': f'Queued (#{queue_position - MAX_CONCURRENT_DOWNLOADS + 1})',
            'progress': 0,
            'url': url
        }
    else:
        download_status[video_id] = {
            'status': 'queued',
            'message': 'Starting soon...',
            'progress': 0,
            'url': url
        }
    
    download_queue.put((video_id, url))
    
    return jsonify({
        'message': 'Download started',
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
        return jsonify({'message': 'Cancellation requested'})
    return jsonify({'error': 'Not found'}), 404

@app.route('/delete/<video_id>', methods=['DELETE'])
def delete_download(video_id):
    if video_id in download_status:
        status = download_status[video_id].get('status')
        if status in ['downloading', 'queued']:
            return jsonify({'error': 'Please cancel the download first'}), 400
        
        del download_status[video_id]
        if video_id in cancel_events:
            del cancel_events[video_id]
        
        return jsonify({'message': 'Deleted'})
    
    return jsonify({'error': 'Not found'}), 404

@app.route('/download-file/<video_id>')
def download_file(video_id):
    if video_id not in download_status:
        return jsonify({'error': 'Not found'}), 404
    
    status = download_status[video_id]
    
    if status.get('status') != 'completed':
        return jsonify({'error': 'Download not completed'}), 400
    
    filename = status.get('filename')
    if not filename:
        return jsonify({'error': 'File not found'}), 404
    
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': 'File does not exist'}), 404
    
    return send_file(filepath, as_attachment=True, download_name=filename)

if __name__ == '__main__':
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG, threaded=True)