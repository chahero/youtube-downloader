# YouTube Downloader

A web-based YouTube video and playlist downloader built with Flask and yt-dlp.

## Features

- 🎥 Download YouTube videos and playlists
- 📋 Playlist support with grouped management
- 🎬 Multiple quality options (4K, 2K, 1080p, 720p, 480p, 360p)
- 🎵 Audio-only download (MP3, M4A)
- 📊 Real-time download progress and speed tracking
- 🔄 Concurrent downloads (configurable limit)
- 🖼️ Video thumbnails and duration display
- ⏸️ Cancel individual or entire playlist downloads
- 📥 Download completed files directly from the web interface
- 🗑️ Clear Inactive - Remove all completed/cancelled/error items at once
- 🗑️ Clean Storage - Delete downloaded files from server
- 🔔 Desktop notifications for download events
- 🌙 Dark mode UI
- 📱 Responsive design

## Tech Stack

- **Backend**: Flask (Python)
- **Frontend**: HTML, CSS, JavaScript
- **Downloader**: yt-dlp
- **Environment**: python-dotenv

## Project Structure

```
youtube-downloader/
├── app.py                  # Flask application
├── requirements.txt        # Python dependencies
├── .env                    # Environment configuration
├── .env.example           # Environment template
├── .gitignore             # Git ignore rules
├── start.bat              # Windows run script
├── start.sh               # Linux/macOS run script
├── templates/
│   └── index.html         # Web interface
├── static/
│   └── style.css          # Stylesheet
└── downloads/             # Downloaded files directory
    └── .gitkeep
```

## Installation

### Prerequisites

- Python 3.7+
- pip
- FFmpeg (required for audio conversion)

### FFmpeg Installation

**Windows:**
```bash
# Using Chocolatey
choco install ffmpeg

# Or download from https://ffmpeg.org/download.html
```

**macOS:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
sudo apt install ffmpeg  # Debian/Ubuntu
sudo yum install ffmpeg  # CentOS/RHEL
```

### Setup

1. Clone the repository:
```bash
git clone https://github.com/chahero/youtube-downloader
cd youtube-downloader
```

2. Create virtual environment:

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux/macOS
python3 -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Configure environment variables:

```bash
# Copy example config
cp .env.example .env

# Edit .env with your settings
```

## Configuration

Edit `.env` file to customize settings:

```env
# Download settings
DOWNLOAD_FOLDER=./downloads
MAX_CONCURRENT_DOWNLOADS=3

# Flask settings
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=True
```

### Configuration Options

- `DOWNLOAD_FOLDER`: Directory where videos will be saved
- `MAX_CONCURRENT_DOWNLOADS`: Maximum number of simultaneous downloads (1-10 recommended)
- `FLASK_HOST`: Server host (0.0.0.0 for all interfaces)
- `FLASK_PORT`: Server port
- `FLASK_DEBUG`: Enable/disable debug mode

## Usage

### Quick Start

**Windows:**

```bash
start.bat
```

**Linux/macOS:**

```bash
chmod +x start.sh
./start.sh
```

### Manual Start

```bash
# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows

# Run application
python app.py
```

### Access the Application

Open your browser and navigate to:

```
http://localhost:5000
```

### How to Use

1. **Enter URL**: Paste a YouTube video or playlist URL
2. **Select Quality**: Choose video quality (Best, 4K, 1080p, etc.)
3. **Select Format**: 
   - Video (MP4) - Downloads video with audio
   - Audio Only (MP3) - Extracts audio as MP3
   - Audio Only (M4A) - Extracts audio as M4A
4. **Enable/Disable Notifications**: Toggle desktop notifications
5. **Start Download**: Click the download button
6. **Monitor Progress**: View real-time progress and download speed
7. **Manage Downloads**:
   - ⬇ Download completed files
   - ✕ Cancel active downloads
   - 🗑 Delete individual items
   - 🗑️ Clear Inactive - Remove all completed/cancelled/error items
   - 🗑️ Clean Storage - Delete all files from server storage

## Features in Detail

### Playlist Support

- Download entire YouTube playlists
- Playlists are grouped with expandable/collapsible view
- Shows total videos and status breakdown
- Cancel or delete entire playlist at once
- Individual video management within playlist

### Quality Options

**Video:**
- Best - Highest available quality
- 2160p (4K)
- 1440p (2K)
- 1080p (Full HD)
- 720p (HD)
- 480p
- 360p

**Audio Only:**
- MP3 (192 kbps)
- M4A (Best quality)

### Concurrent Downloads

- Set maximum concurrent downloads via `MAX_CONCURRENT_DOWNLOADS`
- Additional downloads are queued automatically
- Queue position is displayed for waiting downloads
- Active download count shown in info bar

### Download Status

- **Queued**: Waiting in queue with position number
- **Downloading**: Real-time progress percentage and speed (e.g., "5.2 MB/s")
- **Completed**: Download file or remove from list
- **Cancelled**: Remove from list
- **Error**: View error message and remove from list

### Notifications

- Desktop notifications for download events
- Notifies on: Download started, completed, playlist completed, errors
- Can be enabled/disabled via checkbox
- Browser permission required on first use

### Storage Management

**Clear Inactive:**
- Removes all completed, cancelled, and error items from the list
- Cleans up the UI without deleting files
- Also removes empty playlists

**Clean Storage:**
- Deletes all downloaded files from server storage
- Protects files from active/queued downloads
- Requires double confirmation to prevent accidents
- Shows number of deleted files

## Development

### Project Dependencies

```txt
Flask==3.1.2
python-dotenv==1.1.1
yt-dlp==2025.9.26
```

### Adding New Features

1. Backend routes: Edit `app.py`
2. Frontend UI: Edit `templates/index.html`
3. Styling: Edit `static/style.css`

### API Endpoints

- `POST /download` - Start download
- `GET /status/<video_id>` - Get download status
- `GET /playlist-status/<playlist_id>` - Get playlist status
- `POST /cancel/<video_id>` - Cancel download
- `POST /cancel-playlist/<playlist_id>` - Cancel playlist
- `DELETE /delete/<video_id>` - Delete download record
- `DELETE /delete-playlist/<playlist_id>` - Delete playlist
- `GET /download-file/<video_id>` - Download file
- `POST /clear-inactive` - Clear inactive items
- `POST /clean-storage` - Clean server storage

## Troubleshooting

### Common Issues

**Downloads fail:**
- Ensure yt-dlp is up to date: `pip install --upgrade yt-dlp`
- Check if the YouTube URL is valid
- Some videos may be restricted by region or age
- Verify FFmpeg is installed for audio conversion

**Audio conversion fails:**
- Install FFmpeg (see FFmpeg Installation section)
- Ensure FFmpeg is in system PATH

**Port already in use:**
- Change `FLASK_PORT` in `.env` to a different port

**Permission errors:**
- Ensure write permissions for the downloads folder
- Run with appropriate permissions

**Notifications not working:**
- Allow notifications in browser settings
- Check browser compatibility (modern browsers required)

**Storage not cleaning:**
- Verify folder permissions
- Check if files are locked by other processes

## Browser Compatibility

- Chrome/Edge: Full support
- Firefox: Full support
- Safari: Full support
- Opera: Full support

Note: Desktop notifications require browser permission on first use.

## Security Notes

⚠️ **Important:**

- This application is intended for personal use
- Respect copyright and YouTube's terms of service
- Only download content you have permission to download
- Do not expose this application to the public internet without proper security measures
- Use HTTPS in production environments
- Consider implementing authentication for multi-user scenarios

## Performance Tips

- Limit concurrent downloads based on your internet speed
- Use lower quality for faster downloads
- MP3 conversion adds processing time
- Clean storage periodically to free up disk space

## License

This project is for educational purposes. Please comply with YouTube's Terms of Service and respect copyright laws.

## Disclaimer

This tool is provided as-is for personal use only. The developers are not responsible for any misuse of this application. Users are responsible for ensuring their use complies with applicable laws and terms of service.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues and questions, please open an issue on GitHub.