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
playlist_groups = {}

def get_format_string(quality, format_type):
    """화질과 포맷에 따른 yt-dlp 포맷 문자열 반환"""
    if format_type == 'audio_mp3':
        return 'bestaudio/best'
    elif format_type == 'audio_m4a':
        return 'bestaudio[ext=m4a]/bestaudio/best'
    
    # 비디오 포맷
    quality_formats = {
        'best': 'bestvideo+bestaudio/best',
        '2160p': 'bestvideo[height<=2160]+bestaudio/best[height<=2160]',
        '1440p': 'bestvideo[height<=1440]+bestaudio/best[height<=1440]',
        '1080p': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
        '720p': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
        '480p': 'bestvideo[height<=480]+bestaudio/best[height<=480]',
        '360p': 'bestvideo[height<=360]+bestaudio/best[height<=360]'
    }
    
    return quality_formats.get(quality, 'bestvideo+bestaudio/best')

def download_worker():
    global active_downloads
    
    while True:
        video_data = download_queue.get()
        
        if video_data is None:
            break
        
        video_id = video_data['video_id']
        url = video_data['url']
        quality = video_data.get('quality', 'best')
        format_type = video_data.get('format_type', 'video')
        
        with lock:
            active_downloads += 1
        
        download_video(video_id, url, quality, format_type)
        
        with lock:
            active_downloads -= 1
        
        download_queue.task_done()

def download_video(video_id, url, quality='best', format_type='video'):
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
        
        format_string = get_format_string(quality, format_type)
        
        ydl_opts = {
            'format': format_string,
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
            'progress_hooks': [progress_hook],
        }
        
        # 오디오 전용일 때 postprocessor 추가
        if format_type == 'audio_mp3':
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # mp3 변환 시 확장자 변경
            if format_type == 'audio_mp3':
                filename = os.path.splitext(filename)[0] + '.mp3'
        
        download_status[video_id].update({
            'status': 'completed',
            'message': 'Download completed',
            'filename': os.path.basename(filename),
            'progress': 100
        })
        
    except Exception as e:
        if cancel_events[video_id].is_set():
            download_status[video_id].update({
                'status': 'cancelled',
                'message': 'Cancelled',
                'progress': 0
            })
        else:
            download_status[video_id].update({
                'status': 'error',
                'message': str(e),
                'progress': 0
            })

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
            
            if 'entries' in info:
                videos = []
                for entry in info['entries']:
                    if entry:
                        thumbnail = None
                        if 'thumbnails' in entry and entry['thumbnails']:
                            thumbnail = entry['thumbnails'][-1]['url']
                        elif 'thumbnail' in entry:
                            thumbnail = entry['thumbnail']
                        
                        videos.append({
                            'url': f"https://www.youtube.com/watch?v={entry['id']}",
                            'title': entry.get('title', 'Unknown'),
                            'thumbnail': thumbnail,
                            'duration': entry.get('duration', 0)
                        })
                
                playlist_thumbnail = None
                if 'thumbnails' in info and info['thumbnails']:
                    playlist_thumbnail = info['thumbnails'][-1]['url']
                elif videos and videos[0]['thumbnail']:
                    playlist_thumbnail = videos[0]['thumbnail']
                
                return {
                    'is_playlist': True,
                    'title': info.get('title', 'Unknown Playlist'),
                    'videos': videos,
                    'count': len(videos),
                    'thumbnail': playlist_thumbnail
                }
            else:
                thumbnail = None
                if 'thumbnails' in info and info['thumbnails']:
                    thumbnail = info['thumbnails'][-1]['url']
                elif 'thumbnail' in info:
                    thumbnail = info['thumbnail']
                
                return {
                    'is_playlist': False,
                    'title': info.get('title', 'Unknown'),
                    'url': url,
                    'thumbnail': thumbnail,
                    'duration': info.get('duration', 0)
                }
    except Exception as e:
        raise Exception(f"Failed to extract info: {str(e)}")

@app.route('/download', methods=['POST'])
def start_download():
    data = request.json
    url = data.get('url', '').strip()
    quality = data.get('quality', 'best')
    format_type = data.get('format_type', 'video')
    
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    
    try:
        info = extract_playlist_info(url)
        
        if info['is_playlist']:
            playlist_id = f"playlist_{datetime.now().timestamp()}"
            playlist_groups[playlist_id] = {
                'title': info['title'],
                'count': info['count'],
                'video_ids': [],
                'thumbnail': info.get('thumbnail'),
                'quality': quality,
                'format_type': format_type
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
                        'thumbnail': video.get('thumbnail'),
                        'duration': video.get('duration', 0),
                        'playlist_id': playlist_id,
                        'playlist_title': info['title'],
                        'playlist_index': idx + 1,
                        'playlist_count': info['count'],
                        'quality': quality,
                        'format_type': format_type
                    }
                else:
                    download_status[video_id] = {
                        'status': 'queued',
                        'message': 'Starting soon...',
                        'progress': 0,
                        'url': video['url'],
                        'video_title': video['title'],
                        'thumbnail': video.get('thumbnail'),
                        'duration': video.get('duration', 0),
                        'playlist_id': playlist_id,
                        'playlist_title': info['title'],
                        'playlist_index': idx + 1,
                        'playlist_count': info['count'],
                        'quality': quality,
                        'format_type': format_type
                    }
                
                download_queue.put({
                    'video_id': video_id,
                    'url': video['url'],
                    'quality': quality,
                    'format_type': format_type
                })
            
            return jsonify({
                'message': f'Playlist download started ({info["count"]} videos)',
                'is_playlist': True,
                'playlist_id': playlist_id,
                'video_ids': video_ids,
                'count': info['count'],
                'thumbnail': info.get('thumbnail')
            })
        else:
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
                    'video_title': info['title'],
                    'thumbnail': info.get('thumbnail'),
                    'duration': info.get('duration', 0),
                    'quality': quality,
                    'format_type': format_type
                }
            else:
                download_status[video_id] = {
                    'status': 'queued',
                    'message': 'Starting soon...',
                    'progress': 0,
                    'url': url,
                    'video_title': info['title'],
                    'thumbnail': info.get('thumbnail'),
                    'duration': info.get('duration', 0),
                    'quality': quality,
                    'format_type': format_type
                }
            
            download_queue.put({
                'video_id': video_id,
                'url': url,
                'quality': quality,
                'format_type': format_type
            })
            
            return jsonify({
                'message': 'Download started',
                'is_playlist': False,
                'video_id': video_id,
                'thumbnail': info.get('thumbnail')
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/status/<video_id>')
def get_status(video_id):
    status = download_status.get(video_id, {'status': 'not_found'})
    return jsonify(status)

@app.route('/playlist-status/<playlist_id>')
def get_playlist_status(playlist_id):
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
        'statuses': statuses,
        'thumbnail': playlist.get('thumbnail'),
        'quality': playlist.get('quality'),
        'format_type': playlist.get('format_type')
    })

@app.route('/cancel/<video_id>', methods=['POST'])
def cancel_download(video_id):
    if video_id in cancel_events:
        cancel_events[video_id].set()
        return jsonify({'message': 'Cancellation requested'})
    return jsonify({'error': 'Not found'}), 404

@app.route('/cancel-playlist/<playlist_id>', methods=['POST'])
def cancel_playlist(playlist_id):
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

@app.route('/clear-inactive', methods=['POST'])
def clear_inactive():
    inactive_statuses = ['completed', 'cancelled', 'error']
    deleted_videos = []
    deleted_playlists = []
    
    # 비활성 비디오 삭제
    for video_id in list(download_status.keys()):
        if download_status[video_id].get('status') in inactive_statuses:
            deleted_videos.append(video_id)
            del download_status[video_id]
            if video_id in cancel_events:
                del cancel_events[video_id]
    
    # 모든 비디오가 삭제된 플레이리스트 삭제
    for playlist_id in list(playlist_groups.keys()):
        playlist = playlist_groups[playlist_id]
        remaining_videos = [vid for vid in playlist['video_ids'] if vid in download_status]
        
        if not remaining_videos:
            deleted_playlists.append(playlist_id)
            del playlist_groups[playlist_id]
    
    return jsonify({
        'message': 'Inactive items cleared',
        'deleted_videos': len(deleted_videos),
        'deleted_playlists': len(deleted_playlists)
    })

if __name__ == '__main__':
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG, threaded=True)