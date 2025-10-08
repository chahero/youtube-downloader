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
playlist_groups = {}  # 플레이리스트 그룹 정보 저장

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
            'progress': 100,
            'playlist_id': download_status[video_id].get('playlist_id'),
            'video_title': download_status[video_id].get('video_title')
        }
        
    except Exception as e:
        if cancel_events[video_id].is_set():
            download_status[video_id] = {
                'status': 'cancelled',
                'message': 'Cancelled',
                'progress': 0,
                'playlist_id': download_status[video_id].get('playlist_id'),
                'video_title': download_status[video_id].get('video_title')
            }
        else:
            download_status[video_id] = {
                'status': 'error',
                'message': str(e),
                'progress': 0,
                'playlist_id': download_status[video_id].get('playlist_id'),
                'video_title': download_status[video_id].get('video_title')
            }

for _ in range(MAX_CONCURRENT_DOWNLOADS):
    worker = threading.Thread(target=download_worker, daemon=True)
    worker.start()

@app.route('/')
def index():
    return render_template('index.html', max_downloads=MAX_CONCURRENT_DOWNLOADS)

def extract_playlist_info(url):
    """플레이리스트 정보 추출"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # 플레이리스트인지 확인
            if 'entries' in info:
                videos = []
                for entry in info['entries']:
                    if entry:
                        videos.append({
                            'url': f"https://www.youtube.com/watch?v={entry['id']}",
                            'title': entry.get('title', 'Unknown')
                        })
                
                return {
                    'is_playlist': True,
                    'title': info.get('title', 'Unknown Playlist'),
                    'videos': videos,
                    'count': len(videos)
                }
            else:
                # 단일 비디오
                return {
                    'is_playlist': False,
                    'title': info.get('title', 'Unknown'),
                    'url': url
                }
    except Exception as e:
        raise Exception(f"Failed to extract info: {str(e)}")

@app.route('/download', methods=['POST'])
def start_download():
    data = request.json
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    
    try:
        # URL 정보 추출
        info = extract_playlist_info(url)
        
        if info['is_playlist']:
            # 플레이리스트 처리
            playlist_id = f"playlist_{datetime.now().timestamp()}"
            playlist_groups[playlist_id] = {
                'title': info['title'],
                'count': info['count'],
                'video_ids': []
            }
            
            video_ids = []
            
            for idx, video in enumerate(info['videos']):
                video_id = f"video_{datetime.now().timestamp()}_{idx}"
                video_ids.append(video_id)
                playlist_groups[playlist_id]['video_ids'].append(video_id)
                
                cancel_events[video_id] = threading.Event()
                
                with lock:
                    queue_position = active_downloads + download_queue.qsize()
                
                if queue_position >= MAX_CONCURRENT_DOWNLOADS:
                    download_status[video_id] = {
                        'status': 'queued',
                        'message': f'Queued (#{queue_position - MAX_CONCURRENT_DOWNLOADS + 1})',
                        'progress': 0,
                        'url': video['url'],
                        'video_title': video['title'],
                        'playlist_id': playlist_id,
                        'playlist_title': info['title'],
                        'playlist_index': idx + 1,
                        'playlist_count': info['count']
                    }
                else:
                    download_status[video_id] = {
                        'status': 'queued',
                        'message': 'Starting soon...',
                        'progress': 0,
                        'url': video['url'],
                        'video_title': video['title'],
                        'playlist_id': playlist_id,
                        'playlist_title': info['title'],
                        'playlist_index': idx + 1,
                        'playlist_count': info['count']
                    }
                
                download_queue.put((video_id, video['url']))
            
            return jsonify({
                'message': f'Playlist download started ({info["count"]} videos)',
                'is_playlist': True,
                'playlist_id': playlist_id,
                'video_ids': video_ids,
                'count': info['count']
            })
        else:
            # 단일 비디오 처리
            video_id = f"video_{datetime.now().timestamp()}"
            
            cancel_events[video_id] = threading.Event()
            
            with lock:
                queue_position = active_downloads + download_queue.qsize()
            
            if queue_position >= MAX_CONCURRENT_DOWNLOADS:
                download_status[video_id] = {
                    'status': 'queued',
                    'message': f'Queued (#{queue_position - MAX_CONCURRENT_DOWNLOADS + 1})',
                    'progress': 0,
                    'url': url,
                    'video_title': info['title']
                }
            else:
                download_status[video_id] = {
                    'status': 'queued',
                    'message': 'Starting soon...',
                    'progress': 0,
                    'url': url,
                    'video_title': info['title']
                }
            
            download_queue.put((video_id, url))
            
            return jsonify({
                'message': 'Download started',
                'is_playlist': False,
                'video_id': video_id
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/status/<video_id>')
def get_status(video_id):
    status = download_status.get(video_id, {'status': 'not_found'})
    return jsonify(status)

@app.route('/playlist-status/<playlist_id>')
def get_playlist_status(playlist_id):
    """플레이리스트 전체 상태 확인"""
    if playlist_id not in playlist_groups:
        return jsonify({'error': 'Playlist not found'}), 404
    
    playlist = playlist_groups[playlist_id]
    video_ids = playlist['video_ids']
    
    statuses = {
        'completed': 0,
        'downloading': 0,
        'queued': 0,
        'error': 0,
        'cancelled': 0
    }
    
    for vid in video_ids:
        if vid in download_status:
            status = download_status[vid].get('status', 'unknown')
            if status in statuses:
                statuses[status] += 1
    
    return jsonify({
        'title': playlist['title'],
        'total': playlist['count'],
        'statuses': statuses
    })

@app.route('/cancel/<video_id>', methods=['POST'])
def cancel_download(video_id):
    if video_id in cancel_events:
        cancel_events[video_id].set()
        return jsonify({'message': 'Cancellation requested'})
    return jsonify({'error': 'Not found'}), 404

@app.route('/cancel-playlist/<playlist_id>', methods=['POST'])
def cancel_playlist(playlist_id):
    """플레이리스트 전체 취소"""
    if playlist_id not in playlist_groups:
        return jsonify({'error': 'Playlist not found'}), 404
    
    playlist = playlist_groups[playlist_id]
    cancelled_count = 0
    
    for video_id in playlist['video_ids']:
        if video_id in cancel_events:
            status = download_status.get(video_id, {}).get('status')
            if status in ['queued', 'downloading']:
                cancel_events[video_id].set()
                cancelled_count += 1
    
    return jsonify({
        'message': f'Cancelled {cancelled_count} videos',
        'cancelled_count': cancelled_count
    })

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

@app.route('/delete-playlist/<playlist_id>', methods=['DELETE'])
def delete_playlist(playlist_id):
    """플레이리스트 전체 삭제"""
    if playlist_id not in playlist_groups:
        return jsonify({'error': 'Playlist not found'}), 404
    
    playlist = playlist_groups[playlist_id]
    deleted_count = 0
    
    for video_id in playlist['video_ids']:
        if video_id in download_status:
            status = download_status[video_id].get('status')
            if status not in ['downloading', 'queued']:
                del download_status[video_id]
                if video_id in cancel_events:
                    del cancel_events[video_id]
                deleted_count += 1
    
    # 플레이리스트 그룹 삭제
    del playlist_groups[playlist_id]
    
    return jsonify({
        'message': f'Deleted {deleted_count} videos',
        'deleted_count': deleted_count
    })

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