`# YouTube Downloader

A web-based YouTube video downloader built with Flask and yt-dlp.

## Features

- 🎥 Download YouTube videos with a simple web interface
- 📊 Real-time download progress tracking
- 🔄 Concurrent downloads (configurable limit)
- ⏸️ Cancel downloads in progress
- 📥 Download completed files directly from the web interface
- 🗑️ Remove completed/cancelled items from the list
- 🌙 Dark mode UI
- 📱 Responsive design

## Tech Stack

- ****Backend****: Flask (Python)
- ****Frontend****: HTML, CSS, JavaScript
- ****Downloader****: yt-dlp
- ****Environment****: python-dotenv

## Project Structure`

youtube-downloader/
├── app.py                  # Flask application
├── requirements.txt        # Python dependencies
├── .env                    # Environment configuration
├── .env.example           # Environment template
├── .gitignore             # Git ignore rules
├── run.bat                # Windows run script
├── run.sh                 # Linux/macOS run script
├── templates/
│   └── index.html         # Web interface
├── static/
│   └── style.css          # Stylesheet
└── downloads/             # Downloaded files directory
└── .gitkeep

`## Installation

### Prerequisites

- Python 3.7+
- pip

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd youtube-downloader`

1. Create virtual environment:

bash

`*# Windows*
python -m venv .venv
.venv\Scripts\activate

*# Linux/macOS*
python3 -m venv .venv
source .venv/bin/activate`

1. Install dependencies:

bash

`pip install -r requirements.txt`

1. Configure environment variables:

bash

`*# Copy example config*
cp .env.example .env

*# Edit .env with your settings*`

## Configuration

Edit `.env` file to customize settings:

env

`# Download settings
DOWNLOAD_FOLDER=./downloads
MAX_CONCURRENT_DOWNLOADS=3

# Flask settings
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=True`

### Configuration Options

- `DOWNLOAD_FOLDER`: Directory where videos will be saved
- `MAX_CONCURRENT_DOWNLOADS`: Maximum number of simultaneous downloads
- `FLASK_HOST`: Server host (0.0.0.0 for all interfaces)
- `FLASK_PORT`: Server port
- `FLASK_DEBUG`: Enable/disable debug mode

## Usage

### Quick Start

**Windows:**

bash

`run.bat`

**Linux/macOS:**

bash

`chmod +x run.sh
./run.sh`

### Manual Start

bash

`*# Activate virtual environment*
source .venv/bin/activate  *# Linux/macOS*
.venv\Scripts\activate     *# Windows# Run application*
python app.py`

### Access the Application

Open your browser and navigate to:

`http://localhost:5000`

### How to Use

1. Enter a YouTube URL in the input field
2. Click "Start Download" button
3. Monitor download progress in real-time
4. Download completed files using the ⬇ button
5. Cancel active downloads with the ✕ button
6. Remove items from the list with the 🗑 button

## Features in Detail

### Concurrent Downloads

- Set maximum concurrent downloads via `MAX_CONCURRENT_DOWNLOADS`
- Additional downloads are queued automatically
- Queue position is displayed for waiting downloads

### Download Management

- **Active**: Shows real-time progress percentage
- **Queued**: Displays queue position
- **Completed**: Download file to your device or remove from list
- **Cancelled**: Remove from list
- **Error**: View error message and remove from list

### File Download

- Click the ⬇ button on completed downloads
- Files are downloaded directly to your browser's download folder

## Development

### Project Dependencies

txt

`Flask==3.0.0
yt-dlp==2023.11.16
python-dotenv==1.0.0`

### Adding New Features

1. Backend routes: Edit `app.py`
2. Frontend UI: Edit `templates/index.html`
3. Styling: Edit `static/style.css`

## Troubleshooting

### Common Issues

**Downloads fail:**

- Ensure yt-dlp is up to date: `pip install --upgrade yt-dlp`
- Check if the YouTube URL is valid
- Some videos may be restricted by region or age

**Port already in use:**

- Change `FLASK_PORT` in `.env` to a different port

**Permission errors:**

- Ensure write permissions for the downloads folder

## Security Notes

⚠️ **Important:**

- This application is intended for personal use
- Respect copyright and YouTube's terms of service
- Only download content you have permission to download
- Do not expose this application to the public internet without proper security measures

## License

This project is for educational purposes. Please comply with YouTube's Terms of Service and respect copyright laws.

## Disclaimer

This tool is provided as-is for personal use only. The developers are not responsible for any misuse of this application. Users are responsible for ensuring their use complies with applicable laws and terms of service.