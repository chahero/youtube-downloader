[한글 버전] [English Version](README.en.md)

# YouTube Downloader

Flask와 yt-dlp를 기반으로 만든 간단하고 빠른 웹 기반 YouTube 영상 다운로더입니다. 로그인 없이 바로 사용 가능합니다.

## 기능

- 🎥 YouTube 단일 영상 다운로드 (로그인 불필요)
- 🎬 다양한 화질 옵션 (4K부터 360p까지)
- 🎵 오디오 추출 (MP3, M4A)
- 📊 실시간 진행 상황 및 다운로드 속도 표시
- 🔄 동시 다운로드 (설정 가능한 제한)
- 📋 다운로드 이력 DB 저장 (모든 사용자 공유)
- 🔍 중복 다운로드 감지 및 경고
- 🖼️ 유튜브 썸네일 자동 표시
- 🔗 영상 클릭 시 원본 유튜브로 이동
- 🌙 다크 모드 UI
- 📁 파일 검색 및 관리 기능

## 빠른 시작

### 설치

```bash
# 저장소 복제
git clone https://github.com/chahero/youtube-downloader
cd youtube-downloader

# FFmpeg 설치 (macOS)
brew install ffmpeg

# 가상 환경 생성
python3 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# 환경 설정
cp .env.example .env
```

### 데이터베이스 초기화

```bash
# SQLite 데이터베이스 초기화
python init_db.py

# instance/app.db 파일이 자동으로 생성됩니다
```

### 애플리케이션 실행

**포그라운드 (개발 모드):**
```bash
chmod +x start.sh
./start.sh
```

**백그라운드 (프로덕션):**
```bash
chmod +x manage.sh

# 시작
./manage.sh start

# 상태 확인
./manage.sh status

# 재시작
./manage.sh restart

# 중지
./manage.sh stop
```

`http://localhost:5005` 에서 접속 (.env 파일에서 설정 가능)

## 설정

`.env` 파일 편집:

```env
# 다운로드 설정
DOWNLOAD_FOLDER=./downloads
MAX_CONCURRENT_DOWNLOADS=3

# Flask 설정
HOST=0.0.0.0
PORT=5005
DEBUG=False
```

## 사용법

### 다운로드 관리

1. YouTube URL 입력 (단일 영상만 지원, 플레이리스트 불가)
2. 화질 및 포맷 선택
3. "다운로드 시작" 클릭
4. 실시간 속도와 함께 진행 상황 모니터링
5. 완료 후 다운로드 버튼으로 파일 저장

### 필터 및 검색

- **전체**: 모든 다운로드 항목 표시
- **진행중**: 대기/다운로드 중/실패 항목
- **완료**: 완료된 다운로드 항목
- **검색**: 영상 제목으로 검색

### 관리 기능

- **정리 버튼**: 실패/취소된 항목 삭제 + 임시 파일 정리
- **개별 삭제**: 항목과 파일 함께 삭제 가능
- **중복 감지**: 이미 다운로드한 영상 재다운로드 시 경고

## 로그 관리

로그는 `logs/` 디렉토리에 저장됩니다:

```bash
# 실시간 로그 확인
tail -f logs/app.log

# 오류 로그 확인
tail -f logs/error.log
```

## 프로젝트 구조

```
youtube-downloader/
├── app.py                      # Flask 애플리케이션 (메인)
├── init_db.py                  # 데이터베이스 초기화 스크립트
├── manage.sh                   # 서비스 관리 (macOS/Linux)
├── start.sh                    # 포그라운드 실행 스크립트
├── requirements.txt            # Python 의존성
├── .env.example                # 환경 설정 템플릿
├── .env                        # 환경 설정 (로컬)
├── templates/
│   └── index.html              # 다운로드 인터페이스
├── static/
│   └── style.css               # 스타일시트 (다크 테마)
├── instance/
│   └── app.db                  # SQLite 데이터베이스 (자동 생성)
├── downloads/                  # 다운로드 파일 디렉토리
└── logs/                       # 애플리케이션 로그 디렉토리
```

## 데이터베이스 모델

### DownloadHistory (모든 사용자 공유)
- `id`: 기본 키
- `url`: 유튜브 URL
- `video_title`: 영상 제목
- `filename`: 저장된 파일명
- `quality`: 화질
- `format_type`: 포맷 (video, audio_mp3, audio_m4a)
- `status`: 상태 (completed)
- `file_size`: 파일 크기 (bytes)
- `created_at`: 생성 일시
- `completed_at`: 완료 일시

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/downloads` | 다운로드 목록 조회 (status, q, page 파라미터) |
| DELETE | `/api/downloads/<id>` | 다운로드 항목 삭제 (delete_file 옵션) |
| POST | `/api/downloads/cleanup` | 실패/취소 항목 및 임시파일 정리 |
| POST | `/api/downloads/check-duplicate` | 중복 다운로드 체크 |
| POST | `/download` | 다운로드 시작 |
| POST | `/cancel/<video_id>` | 다운로드 취소 |
| GET | `/download-file/<video_id>` | 파일 다운로드 (진행중) |
| GET | `/download-file-by-history/<id>` | 파일 다운로드 (완료) |

## 문제 해결

**데이터베이스 스키마 오류 (no such column):**
```bash
# 데이터베이스 재초기화
python init_db.py
```

**FFmpeg를 찾을 수 없음:**
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows
# https://ffmpeg.org/download.html 에서 다운로드
```

**포트가 이미 사용 중:**
```bash
# 포트 5005를 사용 중인 프로세스 확인
lsof -i :5005

# 프로세스 종료
kill -9 <PID>
```

**서비스 문제:**
```bash
# 로그 확인
tail -f logs/app.log

# 서비스 재시작
./manage.sh restart

# 프로세스 수동 종료
pkill -f "python app.py"
```

## 요구사항

- Python 3.7+
- FFmpeg
- 최신 웹 브라우저

## 기술 스택

- **Backend**: Flask 3.1.2, Flask-SQLAlchemy 3.1.1
- **Database**: SQLAlchemy ORM을 사용한 SQLite
- **Downloader**: yt-dlp (최신 버전)
- **Frontend**: HTML/CSS/JavaScript (다크 모드 UI)

## 라이선스

교육 목적으로만 사용합니다. YouTube의 서비스 약관 및 저작권법을 준수하세요.

## 부인

이 도구는 개인 사용만 가능합니다. 사용자는 해당 법률 및 서비스 약관을 준수할 책임이 있습니다.
