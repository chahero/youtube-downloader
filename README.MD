[한글 버전] [English Version](README.en.md)

# YouTube Downloader

Flask와 yt-dlp를 기반으로 만든 사용자 인증 및 관리자 승인 시스템이 포함된 웹 기반 YouTube 영상 다운로더입니다.

## 기능

- 🎥 YouTube 단일 영상 다운로드
- 🎬 다양한 화질 옵션 (4K부터 360p까지)
- 🎵 오디오 추출 (MP3, M4A)
- 📊 실시간 진행 상황 및 다운로드 속도 표시
- 🔄 동시 다운로드 (설정 가능한 제한)
- 📋 다운로드 이력 DB 저장 및 검색
- 🔍 중복 다운로드 감지 및 경고
- 🖼️ 유튜브 썸네일 자동 표시
- 🔗 영상 클릭 시 원본 유튜브로 이동
- 🌙 다크 모드 UI
- 🔐 SQLite 데이터베이스 기반 사용자 인증
- 👨‍💼 새 사용자를 위한 관리자 승인 시스템
- 🛡️ 역할 기반 접근 제어

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
DEBUG=True

# 보안
SECRET_KEY=your-secret-key-here
```

프로덕션 환경에서는 강력한 SECRET_KEY를 생성하세요:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## 사용법

### 인증

1. **첫 접속**: `/register` 에서 첫 번째 계정 생성
   - 첫 번째 사용자는 자동으로 관리자로 설정되어 즉시 승인됨
   - 그 이후의 사용자는 관리자의 승인이 필요함

2. **로그인**: `/login` 에서 자격증명 입력
   - 승인된 사용자만 로그인 가능
   - 승인 대기 중인 사용자는 "승인 대기 중인 계정입니다" 메시지 표시

### 관리자 대시보드

관리자는 `/admin` 에 접속하여:
- 승인 대기 중인 사용자 목록 확인
- 새 사용자 승인 또는 거절
- 승인된 사용자 목록 확인
- 사용자 접근 제어 관리

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
│   ├── index.html              # 다운로드 인터페이스
│   ├── login.html              # 로그인 페이지
│   ├── register.html           # 회원가입 페이지
│   └── admin.html              # 관리자 대시보드
├── static/
│   └── style.css               # 스타일시트 (다크 테마)
├── instance/
│   └── app.db                  # SQLite 데이터베이스 (자동 생성)
├── downloads/                  # 다운로드 파일 디렉토리
└── logs/                       # 애플리케이션 로그 디렉토리
```

## 데이터베이스 모델

### User
- `id`: 기본 키
- `username`: 사용자명 (고유)
- `password`: 해시된 비밀번호
- `is_approved`: 관리자 승인 여부
- `is_admin`: 관리자 권한
- `created_at`: 생성 일시

### DownloadHistory
- `id`: 기본 키
- `user_id`: 사용자 ID (외래 키)
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

**로그인할 수 없음 (승인 대기 중):**
- `/admin` 대시보드에서 관리자의 승인을 기다리세요
- 관리자가 계정을 승인하거나 거절할 수 있습니다

## 요구사항

- Python 3.7+
- FFmpeg
- 최신 웹 브라우저

## 기술 스택

- **Backend**: Flask 3.1.2, Flask-SQLAlchemy 3.1.1, Flask-Login 0.6.3
- **Database**: SQLAlchemy ORM을 사용한 SQLite
- **Downloader**: yt-dlp
- **Frontend**: HTML/CSS/JavaScript (다크 모드 UI)
- **Security**: Werkzeug (비밀번호 해싱), 세션 기반 인증

## 라이선스

교육 목적으로만 사용합니다. YouTube의 서비스 약관 및 저작권법을 준수하세요.

## 부인

이 도구는 개인 사용만 가능합니다. 사용자는 해당 법률 및 서비스 약관을 준수할 책임이 있습니다.
