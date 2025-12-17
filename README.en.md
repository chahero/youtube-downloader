[English Version] [한글 버전](README.md)

# YouTube Downloader

A web-based YouTube video downloader with user authentication and admin approval system, built with Flask and yt-dlp.

## Features

- 🎥 Download YouTube single videos
- 🎬 Multiple quality options (4K to 360p)
- 🎵 Audio extraction (MP3, M4A)
- 📊 Real-time progress and download speed
- 🔄 Concurrent downloads (configurable limit)
- 📋 Download history saved to DB with search
- 🔍 Duplicate download detection and warning
- 🖼️ Auto-display YouTube thumbnails
- 🔗 Click video to open original YouTube
- 🌙 Dark mode UI
- 🔐 User authentication with SQLite database
- 👨‍💼 Admin approval system for new users
- 🛡️ Role-based access control

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/chahero/youtube-downloader
cd youtube-downloader

# Install FFmpeg (macOS)
brew install ffmpeg

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
```

### Initialize Database

```bash
# Initialize SQLite database
python init_db.py

# This will create instance/app.db with the proper schema
```

### Run Application

**Foreground (Development):**
```bash
chmod +x start.sh
./start.sh
```

**Background (Production):**
```bash
chmod +x manage.sh

# Start
./manage.sh start

# Check status
./manage.sh status

# Restart
./manage.sh restart

# Stop
./manage.sh stop
```

Access at `http://localhost:5005` (configured in .env)

## Configuration

Edit `.env`:

```env
# Download settings
DOWNLOAD_FOLDER=./downloads
MAX_CONCURRENT_DOWNLOADS=3

# Flask settings
HOST=0.0.0.0
PORT=5005
DEBUG=True

# Security
SECRET_KEY=your-secret-key-here
```

For production, generate a strong SECRET_KEY:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Usage

### Authentication

1. **First Access**: Go to `/register` and create the first account
   - First user automatically becomes Admin with full approval
   - Subsequent users need Admin approval to access the service

2. **Login**: Go to `/login` and enter credentials
   - Only approved users can log in
   - Pending users see: "Account pending admin approval"

### Admin Dashboard

Admin users can access `/admin` to:
- View pending user registrations
- Approve or reject new users
- View list of approved users
- Manage user access control

### Download Management

1. Enter YouTube URL (single video only, playlists not supported)
2. Select quality and format
3. Click "Start Download"
4. Monitor progress with real-time speed
5. Download completed files via download button

### Filters and Search

- **All**: Show all download items
- **Active**: Queued/downloading/failed items
- **Completed**: Completed download items
- **Search**: Search by video title

### Management Features

- **Cleanup Button**: Delete failed/cancelled items + clean temp files
- **Individual Delete**: Delete item with file option
- **Duplicate Detection**: Warning when re-downloading already downloaded video

## Log Management

Logs are in the `logs/` directory:

```bash
# View logs in real-time
tail -f logs/app.log

# View errors
tail -f logs/error.log
```

## Project Structure

```
youtube-downloader/
├── app.py                      # Flask application (main)
├── init_db.py                  # Database initialization script
├── manage.sh                   # Service management (macOS/Linux)
├── start.sh                    # Foreground run script
├── requirements.txt            # Python dependencies
├── .env.example                # Environment configuration template
├── .env                        # Environment configuration (local)
├── templates/
│   ├── index.html              # Download interface
│   ├── login.html              # Login page
│   ├── register.html           # Registration page
│   └── admin.html              # Admin dashboard
├── static/
│   └── style.css               # Stylesheet (dark theme)
├── instance/
│   └── app.db                  # SQLite database (auto-created)
├── downloads/                  # Downloaded files directory
└── logs/                       # Application logs directory
```

## Database Models

### User
- `id`: Primary key
- `username`: Username (unique)
- `password`: Hashed password
- `is_approved`: Admin approval status
- `is_admin`: Admin privilege
- `created_at`: Creation timestamp

### DownloadHistory
- `id`: Primary key
- `user_id`: User ID (foreign key)
- `url`: YouTube URL
- `video_title`: Video title
- `filename`: Saved filename
- `quality`: Quality setting
- `format_type`: Format (video, audio_mp3, audio_m4a)
- `status`: Status (completed)
- `file_size`: File size (bytes)
- `created_at`: Creation timestamp
- `completed_at`: Completion timestamp

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/downloads` | Get download list (status, q, page params) |
| DELETE | `/api/downloads/<id>` | Delete download item (delete_file option) |
| POST | `/api/downloads/cleanup` | Cleanup failed/cancelled items and temp files |
| POST | `/api/downloads/check-duplicate` | Check duplicate download |
| POST | `/download` | Start download |
| POST | `/cancel/<video_id>` | Cancel download |
| GET | `/download-file/<video_id>` | Download file (active) |
| GET | `/download-file-by-history/<id>` | Download file (completed) |

## Troubleshooting

**Database schema errors (no such column):**
```bash
# Reinitialize the database
python init_db.py
```

**FFmpeg not found:**
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

**Port in use:**
```bash
# Find process using port 5005
lsof -i :5005

# Kill process
kill -9 <PID>
```

**Service issues:**
```bash
# Check logs
tail -f logs/app.log

# Restart service
./manage.sh restart

# Kill process manually
pkill -f "python app.py"
```

**Can't login (pending approval):**
- Wait for Admin approval at `/admin` dashboard
- Admin will approve or reject your account

## Requirements

- Python 3.7+
- FFmpeg
- Modern web browser

## Tech Stack

- **Backend**: Flask 3.1.2, Flask-SQLAlchemy 3.1.1, Flask-Login 0.6.3
- **Database**: SQLite with SQLAlchemy ORM
- **Downloader**: yt-dlp
- **Frontend**: HTML/CSS/JavaScript (Dark mode UI)
- **Security**: Werkzeug (password hashing), session-based authentication

## License

For educational purposes. Comply with YouTube's Terms of Service and copyright laws.

## Disclaimer

This tool is for personal use only. Users are responsible for ensuring compliance with applicable laws and terms of service.
