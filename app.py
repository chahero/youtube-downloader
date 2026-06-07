from flask import (
    Flask, render_template, request, jsonify, send_file
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
import yt_dlp
import os
import threading
import subprocess
import tempfile
import wave
from datetime import datetime
from queue import Queue
from dotenv import load_dotenv

load_dotenv()

# --- 다운로더 설정 (기존) ---
DOWNLOAD_FOLDER = os.getenv('DOWNLOAD_FOLDER', './downloads')
MAX_CONCURRENT_DOWNLOADS = int(os.getenv('MAX_CONCURRENT_DOWNLOADS', 3))
DEBUG_MODE = os.getenv('DEBUG', 'True').strip().lower() in ('1', 'true', 'yes', 'on')
SUBTITLE_FOLDER = os.getenv('SUBTITLE_FOLDER', './subtitles')
STT_TIMEOUT_SECONDS = int(os.getenv('STT_TIMEOUT_SECONDS', 1800))
STT_GRPC_SERVER = os.getenv('STT_GRPC_SERVER', '192.168.0.67:9031')
STT_LANGUAGE_CODE = os.getenv('STT_LANGUAGE_CODE', os.getenv('STT_LANGUAGE', 'multi'))
STT_WAV_SAMPLE_RATE = int(os.getenv('STT_WAV_SAMPLE_RATE', 16000))
STT_MAX_SUBTITLE_SECONDS = float(os.getenv('STT_MAX_SUBTITLE_SECONDS', 5))
STT_MAX_SUBTITLE_WORDS = int(os.getenv('STT_MAX_SUBTITLE_WORDS', 12))
STT_ENABLE_AUTOMATIC_PUNCTUATION = os.getenv('STT_ENABLE_AUTOMATIC_PUNCTUATION', 'True').strip().lower() in ('1', 'true', 'yes', 'on')

app = Flask(__name__)

# --- SQLite 데이터베이스 설정 ---
instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
os.makedirs(instance_path, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "app.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- DownloadHistory 모델 ---
class DownloadHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(500), nullable=False)
    video_title = db.Column(db.String(500))
    filename = db.Column(db.String(500))
    quality = db.Column(db.String(20))
    format_type = db.Column(db.String(20))
    status = db.Column(db.String(20))  # completed, error, cancelled
    file_size = db.Column(db.Integer)  # bytes
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    subtitle_status = db.Column(db.String(20), default='none')
    subtitle_filename = db.Column(db.String(500))
    subtitle_error = db.Column(db.String(1000))
    subtitle_created_at = db.Column(db.DateTime)

os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
os.makedirs(SUBTITLE_FOLDER, exist_ok=True)

download_status = {}


def get_subtitle_status(history):
    return getattr(history, 'subtitle_status', None) or 'none'


def build_subtitle_filename(history_id, source_filename):
    base = os.path.splitext((source_filename or '').strip())[0].strip()
    if not base:
        base = 'subtitle'
    safe_base = ''.join('_' if ch in '\\/:*?"<>|' else ch for ch in base)
    safe_base = safe_base.strip(' .') or 'subtitle'
    return f'{history_id}-{safe_base}.srt'


def format_srt_timestamp(milliseconds):
    milliseconds = max(0, int(round(milliseconds)))
    hours, remainder = divmod(milliseconds, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f'{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}'


def get_word_field(word, field_name, default=None):
    if isinstance(word, dict):
        return word.get(field_name, default)
    return getattr(word, field_name, default)


def get_repeated_field(item, field_name):
    if isinstance(item, dict):
        return item.get(field_name, []) or []
    return getattr(item, field_name, []) or []


def collect_word_timestamps_from_results(results):
    words = []
    for result in results:
        alternatives = get_repeated_field(result, 'alternatives')
        if not alternatives:
            continue
        words.extend(get_repeated_field(alternatives[0], 'words'))
    return words


def is_punctuation_token(text):
    return bool(text) and all(ch in '.,!?;:)]}\'"' for ch in text)


def append_word_text(current_text, word):
    if not current_text:
        return word
    if is_punctuation_token(word):
        return f'{current_text}{word}'
    return f'{current_text} {word}'


def build_srt_from_word_timestamps(words, max_seconds=None, max_words=None):
    max_seconds = STT_MAX_SUBTITLE_SECONDS if max_seconds is None else max_seconds
    max_words = STT_MAX_SUBTITLE_WORDS if max_words is None else max_words
    entries = []
    current_text = ''
    current_start = None
    current_end = None
    current_word_count = 0

    def flush():
        nonlocal current_text, current_start, current_end, current_word_count
        text_value = current_text.strip()
        if text_value and current_start is not None and current_end is not None:
            end_value = max(current_end, current_start + 1)
            entries.append((current_start, end_value, text_value))
        current_text = ''
        current_start = None
        current_end = None
        current_word_count = 0

    for item in words:
        word = str(get_word_field(item, 'word', '') or '').strip()
        if not word:
            continue

        start_time = get_word_field(item, 'start_time', current_end or 0)
        end_time = get_word_field(item, 'end_time', start_time)
        start_time = int(start_time or 0)
        end_time = int(end_time or start_time)

        is_punctuation = is_punctuation_token(word)
        if current_text and not is_punctuation:
            duration_seconds = (max(end_time, current_end or end_time) - current_start) / 1000
            if current_word_count >= max_words or duration_seconds > max_seconds:
                flush()

        if current_start is None:
            current_start = start_time

        current_text = append_word_text(current_text, word)
        current_end = max(current_end or end_time, end_time, start_time)
        if not is_punctuation:
            current_word_count += 1

        if word in ('.', '?', '!'):
            flush()

    flush()

    return '\n\n'.join(
        f'{index}\n{format_srt_timestamp(start)} --> {format_srt_timestamp(end)}\n{text}'
        for index, (start, end, text) in enumerate(entries, 1)
    ) + ('\n' if entries else '')


def ensure_database_schema():
    db.create_all()

    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())
    if 'download_history' not in table_names:
        return

    columns = {column['name'] for column in inspector.get_columns('download_history')}
    column_defs = {
        'subtitle_status': "VARCHAR(20) DEFAULT 'none'",
        'subtitle_filename': 'VARCHAR(500)',
        'subtitle_error': 'VARCHAR(1000)',
        'subtitle_created_at': 'DATETIME',
    }

    with db.engine.begin() as conn:
        for column_name, column_type in column_defs.items():
            if column_name not in columns:
                conn.execute(text(f'ALTER TABLE download_history ADD COLUMN {column_name} {column_type}'))


def cleanup_partial_files(video_title):
    """부분 다운로드 파일 삭제 (.part, .ytdl 등)"""
    if not video_title:
        return

    try:
        for filename in os.listdir(DOWNLOAD_FOLDER):
            # 부분 다운로드 파일 패턴 매칭
            if filename.endswith(('.part', '.ytdl', '.temp')) or \
               (video_title and video_title in filename and filename.endswith('.part')):
                filepath = os.path.join(DOWNLOAD_FOLDER, filename)
                try:
                    os.remove(filepath)
                    print(f"Cleaned up partial file: {filename}")
                except Exception as e:
                    print(f"Failed to clean up {filename}: {e}")
    except Exception as e:
        print(f"Cleanup error: {e}")


def save_download_history(video_id, status):
    """다운로드 이력을 DB에 저장 (completed만 저장)"""
    # 완료된 것만 저장, 실패/취소는 저장하지 않음
    if status != 'completed':
        return

    try:
        video_data = download_status.get(video_id, {})

        # 파일 크기 가져오기
        file_size = None
        if status == 'completed' and video_data.get('filename'):
            filepath = os.path.join(DOWNLOAD_FOLDER, video_data['filename'])
            if os.path.exists(filepath):
                file_size = os.path.getsize(filepath)

        with app.app_context():
            history = DownloadHistory(
                url=video_data.get('url', ''),
                video_title=video_data.get('video_title', ''),
                filename=video_data.get('filename'),
                quality=video_data.get('quality'),
                format_type=video_data.get('format_type'),
                status=status,
                file_size=file_size,
                completed_at=datetime.utcnow() if status in ['completed', 'error', 'cancelled'] else None
            )
            db.session.add(history)
            db.session.commit()
    except Exception as e:
        print(f"Failed to save download history: {e}")
cancel_events = {}
download_queue = Queue()
subtitle_queue = Queue()
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
                    speed = d.get('speed', 0) # 속도 정보
                    
                    if total > 0:
                        percent = int((downloaded / total) * 100)
                        download_status[video_id]['progress'] = percent
                    else:
                        download_status[video_id]['progress'] = 0
                        
                    # 속도 저장
                    download_status[video_id]['speed'] = speed if speed else 0
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
            'progress': 100,
            'speed': 0
        })

        # 다운로드 이력 저장
        save_download_history(video_id, 'completed')
        
    except Exception as e:
        video_title = download_status[video_id].get('video_title', '')

        if cancel_events[video_id].is_set():
            download_status[video_id].update({
                'status': 'cancelled',
                'message': 'Cancelled',
                'progress': 0,
                'speed': 0
            })
            # 취소 시 부분 파일 삭제
            cleanup_partial_files(video_title)
        else:
            download_status[video_id].update({
                'status': 'error',
                'message': str(e),
                'progress': 0
            })
            # 실패 시 부분 파일 삭제
            cleanup_partial_files(video_title)


def convert_media_to_stt_wav(source_path, wav_path):
    """Riva ASR용 16kHz mono PCM WAV를 생성한다."""
    command = [
        'ffmpeg',
        '-y',
        '-hide_banner',
        '-loglevel',
        'error',
        '-i',
        source_path,
        '-ac',
        '1',
        '-ar',
        str(STT_WAV_SAMPLE_RATE),
        '-c:a',
        'pcm_s16le',
        wav_path,
    ]
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=STT_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise Exception('ffmpeg를 찾을 수 없습니다. ffmpeg 설치 또는 PATH 설정을 확인하세요.') from exc
    except subprocess.TimeoutExpired as exc:
        raise Exception('STT용 WAV 변환 시간이 초과되었습니다.') from exc

    if result.returncode != 0:
        error_message = (result.stderr or result.stdout or '').strip()
        raise Exception(f'STT용 WAV 변환 실패: {error_message[:500]}')


def read_wav_frames(wav_path):
    with wave.open(wav_path, 'rb') as wav_file:
        sample_rate = wav_file.getframerate()
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        audio_bytes = wav_file.readframes(wav_file.getnframes())

    if sample_rate != STT_WAV_SAMPLE_RATE or channels != 1 or sample_width != 2:
        raise Exception('STT WAV 형식이 올바르지 않습니다. 16kHz mono PCM 16-bit가 필요합니다.')

    return audio_bytes


def request_subtitle_from_stt(source_path):
    """Riva gRPC ASR에 미디어를 전송하고 word timestamp 기반 SRT 텍스트를 반환한다."""
    try:
        import riva.client as riva
    except ImportError as exc:
        raise Exception('nvidia-riva-client 패키지가 설치되어 있지 않습니다.') from exc

    os.makedirs('tmp', exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='subtitle_', dir='tmp') as temp_dir:
        wav_path = os.path.join(temp_dir, 'input.wav')
        convert_media_to_stt_wav(source_path, wav_path)
        audio_bytes = read_wav_frames(wav_path)

        auth = riva.Auth(uri=STT_GRPC_SERVER, use_ssl=False)
        service = riva.ASRService(auth)
        config = riva.RecognitionConfig(
            encoding=riva.AudioEncoding.LINEAR_PCM,
            sample_rate_hertz=STT_WAV_SAMPLE_RATE,
            language_code=STT_LANGUAGE_CODE,
            max_alternatives=1,
            enable_word_time_offsets=True,
            enable_automatic_punctuation=STT_ENABLE_AUTOMATIC_PUNCTUATION,
        )
        response_future = service.offline_recognize(audio_bytes, config, future=True)
        response = response_future.result(timeout=STT_TIMEOUT_SECONDS)

    if not response.results:
        raise Exception('STT 결과가 비어 있습니다.')

    words = collect_word_timestamps_from_results(response.results)
    if not words:
        raise Exception('STT 결과에 word timestamp가 없습니다.')

    subtitle_text = build_srt_from_word_timestamps(words)
    if not subtitle_text.strip():
        raise Exception('SRT 자막을 생성하지 못했습니다.')

    return subtitle_text


def mark_subtitle_error(history_id, message):
    with app.app_context():
        history = db.session.get(DownloadHistory, history_id)
        if not history:
            return
        history.subtitle_status = 'error'
        history.subtitle_error = message[:1000]
        db.session.commit()


def generate_subtitle_for_history(history_id):
    try:
        with app.app_context():
            history = db.session.get(DownloadHistory, history_id)
            if not history:
                return

            if not history.filename:
                raise Exception('다운로드 파일 정보가 없습니다.')

            source_path = os.path.join(DOWNLOAD_FOLDER, history.filename)
            if not os.path.exists(source_path):
                raise Exception('원본 다운로드 파일을 찾을 수 없습니다.')

            subtitle_filename = build_subtitle_filename(history.id, history.filename)
            subtitle_path = os.path.join(SUBTITLE_FOLDER, subtitle_filename)

            history.subtitle_status = 'processing'
            history.subtitle_error = None
            db.session.commit()

        subtitle_text = request_subtitle_from_stt(source_path)

        os.makedirs(SUBTITLE_FOLDER, exist_ok=True)
        with open(subtitle_path, 'w', encoding='utf-8') as subtitle_file:
            subtitle_file.write(subtitle_text)

        with app.app_context():
            history = db.session.get(DownloadHistory, history_id)
            if not history:
                return
            history.subtitle_status = 'completed'
            history.subtitle_filename = subtitle_filename
            history.subtitle_error = None
            history.subtitle_created_at = datetime.utcnow()
            db.session.commit()
    except Exception as e:
        mark_subtitle_error(history_id, str(e))


def subtitle_worker():
    while True:
        history_id = subtitle_queue.get()
        if history_id is None:
            break
        try:
            generate_subtitle_for_history(history_id)
        finally:
            subtitle_queue.task_done()


for _ in range(MAX_CONCURRENT_DOWNLOADS):
    worker = threading.Thread(target=download_worker, daemon=True)
    worker.start()

subtitle_worker_thread = threading.Thread(target=subtitle_worker, daemon=True)
subtitle_worker_thread.start()

def normalize_youtube_url(url):
    """YouTube URL 정규화 - 단일 비디오는 list 파라미터 제거"""
    import re

    # watch?v= 형식 URL (단일 비디오)
    if 'watch?v=' in url or 'youtu.be/' in url:
        # list, index, start_radio 등의 파라미터 제거
        url = re.sub(r'[&?](list|index|start_radio|t|feature)=[^&]*', '', url)
        # 첫 번째 & 뒤의 & 제거
        url = re.sub(r'\?&', '?', url)

    return url

def extract_playlist_info(url):
    """플레이리스트 정보 추출"""
    # URL 정규화
    url = normalize_youtube_url(url)
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

@app.route('/')
def index():
    return render_template('index.html', max_downloads=MAX_CONCURRENT_DOWNLOADS)

@app.route('/download', methods=['POST'])
def start_download():
    data = request.json
    url = data.get('url', '').strip()
    quality = data.get('quality', 'best')
    format_type = data.get('format_type', 'video')

    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    try:
        # URL 정규화
        url = normalize_youtube_url(url)
        info = extract_playlist_info(url)

        # 플레이리스트 URL 차단
        if info['is_playlist']:
            return jsonify({'error': '플레이리스트는 지원하지 않습니다. 단일 영상 URL만 입력해주세요.'}), 400

        if False:  # 플레이리스트 기능 비활성화
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


@app.route('/download-file-by-history/<int:history_id>')
def download_file_by_history(history_id):
    """DB 이력에서 파일 다운로드"""
    history = DownloadHistory.query.filter_by(id=history_id).first()
    if not history:
        return jsonify({'error': 'Not found'}), 404

    if not history.filename:
        return jsonify({'error': 'File not found'}), 404

    filepath = os.path.join(DOWNLOAD_FOLDER, history.filename)

    if not os.path.exists(filepath):
        return jsonify({'error': 'File does not exist'}), 404

    return send_file(filepath, as_attachment=True, download_name=history.filename)


@app.route('/api/downloads/<int:history_id>/subtitle', methods=['POST'])
def start_subtitle_generation(history_id):
    """완료된 다운로드 항목의 자막 생성 시작"""
    history = db.session.get(DownloadHistory, history_id)
    if not history:
        return jsonify({'error': '항목을 찾을 수 없습니다.'}), 404

    if history.status != 'completed':
        return jsonify({'error': '완료된 다운로드만 자막을 생성할 수 있습니다.'}), 400

    if get_subtitle_status(history) in ['queued', 'processing']:
        return jsonify({'error': '자막 생성이 이미 진행 중입니다.'}), 400

    if not history.filename:
        return jsonify({'error': '다운로드 파일 정보가 없습니다.'}), 400

    source_path = os.path.join(DOWNLOAD_FOLDER, history.filename)
    if not os.path.exists(source_path):
        history.subtitle_status = 'error'
        history.subtitle_error = '원본 다운로드 파일을 찾을 수 없습니다.'
        db.session.commit()
        return jsonify({'error': history.subtitle_error}), 400

    history.subtitle_status = 'queued'
    history.subtitle_error = None
    db.session.commit()

    subtitle_queue.put(history_id)

    return jsonify({
        'message': '자막 생성이 시작되었습니다.',
        'subtitle_status': 'queued'
    })


@app.route('/subtitle-file-by-history/<int:history_id>')
def download_subtitle_file_by_history(history_id):
    """DB 이력에서 생성된 자막 파일 다운로드"""
    history = db.session.get(DownloadHistory, history_id)
    if not history:
        return jsonify({'error': '항목을 찾을 수 없습니다.'}), 404

    if get_subtitle_status(history) != 'completed' or not history.subtitle_filename:
        return jsonify({'error': '자막 파일이 없습니다.'}), 404

    filepath = os.path.join(SUBTITLE_FOLDER, history.subtitle_filename)
    if not os.path.exists(filepath):
        return jsonify({'error': '자막 파일이 존재하지 않습니다.'}), 404

    return send_file(filepath, as_attachment=True, download_name=history.subtitle_filename)


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
    
@app.route('/clean-storage', methods=['POST'])
def clean_storage():
    try:
        # 진행 중인 다운로드의 파일명 수집
        active_files = set()
        for video_id, status in download_status.items():
            if status.get('status') in ['downloading', 'queued']:
                filename = status.get('filename')
                if filename:
                    active_files.add(filename)
        
        # 파일 삭제
        deleted_count = 0
        if os.path.exists(DOWNLOAD_FOLDER):
            for filename in os.listdir(DOWNLOAD_FOLDER):
                if filename not in active_files:
                    filepath = os.path.join(DOWNLOAD_FOLDER, filename)
                    try:
                        os.remove(filepath)
                        deleted_count += 1
                    except Exception as e:
                        print(f"Failed to delete {filename}: {e}")
        
        return jsonify({
            'message': 'Storage cleaned',
            'deleted_count': deleted_count
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# --- 통합 다운로드 API ---
@app.route('/api/downloads')
def get_downloads():
    """통합 다운로드 목록 조회 (진행중 + 완료)"""
    status_filter = request.args.get('status', 'all')  # all, active, completed
    search = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    try:
        items = []

        # 진행 중인 다운로드 (메모리에서)
        if status_filter in ['all', 'active']:
            for video_id, data in download_status.items():
                if data.get('status') in ['queued', 'downloading', 'error', 'cancelled']:
                    # 검색어 필터
                    if search and search.lower() not in (data.get('video_title', '') or '').lower():
                        continue
                    items.append({
                        'id': video_id,
                        'type': 'active',
                        'url': data.get('url', ''),
                        'video_title': data.get('video_title', ''),
                        'thumbnail': data.get('thumbnail'),
                        'quality': data.get('quality'),
                        'format_type': data.get('format_type'),
                        'status': data.get('status'),
                        'progress': data.get('progress', 0),
                        'speed': data.get('speed', 0),
                        'message': data.get('message', ''),
                        'filename': data.get('filename'),
                        'created_at': None
                    })

        # 완료된 다운로드 (DB에서)
        if status_filter in ['all', 'completed']:
            query = DownloadHistory.query.filter_by(status='completed')

            if search:
                query = query.filter(DownloadHistory.video_title.ilike(f'%{search}%'))

            query = query.order_by(DownloadHistory.created_at.desc())
            histories = query.all()

            for h in histories:
                items.append({
                    'id': h.id,
                    'type': 'completed',
                    'url': h.url,
                    'video_title': h.video_title,
                    'thumbnail': None,
                    'quality': h.quality,
                    'format_type': h.format_type,
                    'status': 'completed',
                    'progress': 100,
                    'speed': 0,
                    'message': 'Download completed',
                    'filename': h.filename,
                    'file_size': h.file_size,
                    'created_at': h.created_at.isoformat() if h.created_at else None,
                    'completed_at': h.completed_at.isoformat() if h.completed_at else None,
                    'subtitle_status': get_subtitle_status(h),
                    'subtitle_filename': h.subtitle_filename,
                    'subtitle_error': h.subtitle_error,
                    'subtitle_created_at': h.subtitle_created_at.isoformat() if h.subtitle_created_at else None
                })

        # 정렬: 진행 중 먼저, 그 다음 완료
        def sort_key(item):
            status_order = {'downloading': 0, 'queued': 1, 'error': 2, 'cancelled': 3, 'completed': 4}
            return status_order.get(item['status'], 5)

        items.sort(key=sort_key)

        # 페이지네이션
        total = len(items)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_items = items[start:end]

        return jsonify({
            'items': paginated_items,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page if total > 0 else 1
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# --- 기존 이력 API (하위 호환) ---
@app.route('/api/history')
def get_download_history():
    """다운로드 이력 조회 (하위 호환용)"""
    return get_downloads()


@app.route('/api/downloads/<item_id>', methods=['DELETE'])
def delete_download_item(item_id):
    """다운로드 항목 삭제 (진행중 또는 완료)"""
    delete_file = request.args.get('delete_file', 'false').lower() == 'true'

    try:
        # 진행 중인 다운로드 (메모리) 확인
        if item_id in download_status:
            data = download_status[item_id]

            # 다운로드 중이면 취소 먼저
            if data.get('status') in ['downloading', 'queued']:
                if item_id in cancel_events:
                    cancel_events[item_id].set()

            # 파일 삭제 옵션
            if delete_file and data.get('filename'):
                filepath = os.path.join(DOWNLOAD_FOLDER, data['filename'])
                if os.path.exists(filepath):
                    os.remove(filepath)

            # 메모리에서 삭제
            del download_status[item_id]
            if item_id in cancel_events:
                del cancel_events[item_id]

            return jsonify({'message': '삭제되었습니다.'})

        # 완료된 다운로드 (DB) 확인
        try:
            history_id = int(item_id)
            history = DownloadHistory.query.filter_by(id=history_id).first()
            if history:
                # 파일 삭제 옵션
                if delete_file and history.filename:
                    filepath = os.path.join(DOWNLOAD_FOLDER, history.filename)
                    if os.path.exists(filepath):
                        os.remove(filepath)

                db.session.delete(history)
                db.session.commit()
                return jsonify({'message': '삭제되었습니다.'})
        except ValueError:
            pass

        return jsonify({'error': '항목을 찾을 수 없습니다.'}), 404

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/downloads/cleanup', methods=['POST'])
def cleanup_downloads():
    """정리 기능: 실패/취소 항목 삭제 + 고아 파일 정리"""
    try:
        cleaned_items = 0
        cleaned_files = 0

        # 1. 메모리에서 실패/취소 항목 삭제
        to_delete = []
        for video_id, data in download_status.items():
            if data.get('status') in ['error', 'cancelled']:
                to_delete.append(video_id)

        for video_id in to_delete:
            del download_status[video_id]
            if video_id in cancel_events:
                del cancel_events[video_id]
            cleaned_items += 1

        # 2. 고아 파일 정리 (DB에 없는 파일)
        if os.path.exists(DOWNLOAD_FOLDER):
            # DB에 있는 파일명 목록
            db_filenames = set()
            histories = DownloadHistory.query.all()
            for h in histories:
                if h.filename:
                    db_filenames.add(h.filename)

            # 진행 중인 파일명도 포함
            for data in download_status.values():
                if data.get('filename'):
                    db_filenames.add(data['filename'])

            # 부분 파일 및 고아 파일 삭제
            for filename in os.listdir(DOWNLOAD_FOLDER):
                filepath = os.path.join(DOWNLOAD_FOLDER, filename)

                # 부분 파일 삭제
                if filename.endswith(('.part', '.ytdl', '.temp')):
                    try:
                        os.remove(filepath)
                        cleaned_files += 1
                    except:
                        pass

        return jsonify({
            'message': f'정리 완료: {cleaned_items}개 항목, {cleaned_files}개 파일 삭제',
            'cleaned_items': cleaned_items,
            'cleaned_files': cleaned_files
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# --- 기존 API (하위 호환) ---
@app.route('/api/history/<int:history_id>', methods=['DELETE'])
def delete_history(history_id):
    """다운로드 이력 삭제 (하위 호환)"""
    return delete_download_item(str(history_id))


@app.route('/api/history/clear', methods=['POST'])
def clear_history():
    """모든 다운로드 이력 삭제"""
    try:
        deleted = DownloadHistory.query.delete()
        db.session.commit()
        return jsonify({'message': f'{deleted}개의 이력이 삭제되었습니다.', 'deleted_count': deleted})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/downloads/check-duplicate', methods=['POST'])
def check_duplicate():
    """중복 다운로드 체크"""
    data = request.json
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'duplicate': False})

    try:
        # DB에서 같은 URL로 완료된 다운로드 확인
        existing = DownloadHistory.query.filter_by(
            url=url,
            status='completed'
        ).first()

        if existing:
            return jsonify({
                'duplicate': True,
                'existing': {
                    'video_title': existing.video_title,
                    'quality': existing.quality,
                    'format_type': existing.format_type,
                    'completed_at': existing.completed_at.isoformat() if existing.completed_at else None
                }
            })

        return jsonify({'duplicate': False})
    except Exception as e:
        return jsonify({'duplicate': False, 'error': str(e)})


if __name__ == '__main__':
    # 데이터베이스 테이블 생성
    with app.app_context():
        ensure_database_schema()

    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '5002'))
    app.run(host=host, port=port, debug=DEBUG_MODE, threaded=True)
