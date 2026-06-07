# Manual STT Subtitle Generation Design

## Context

This project is a Flask-based YouTube downloader. Downloads run through an in-memory worker queue, completed download history is stored in SQLite, and the UI polls `/api/downloads` for status.

The STT server at `http://192.168.0.67:9010` is a Speaches/FastAPI service with an OpenAI-compatible audio transcription endpoint:

- `POST /v1/audio/transcriptions`
- `model=deepdml/faster-whisper-large-v3-turbo-ct2`
- `file=<uploaded media file>`
- `response_format=srt`

The model supports multiple languages. The app will omit the `language` parameter so the STT service auto-detects Korean, English, Japanese, or other supported languages.

## Goals

- Add a manual "generate subtitles" action for completed downloads.
- Generate SRT subtitles from the downloaded media file using the STT API.
- Keep the browser request short by running STT in a background job.
- Show subtitle generation state in the existing download list.
- Preserve the existing SQLite data during upgrade.

## Non-Goals

- Automatic subtitle generation immediately after every download.
- User editing of subtitle text.
- Word-level timeline UI.
- Translation.
- Full `app.py` module split during this feature.

## Data Model

Add these nullable columns to `DownloadHistory`:

- `subtitle_status`: `none`, `queued`, `processing`, `completed`, or `error`
- `subtitle_filename`: generated `.srt` filename
- `subtitle_error`: last error message
- `subtitle_created_at`: timestamp when subtitle generation completed

Default behavior for old rows:

- Missing or null `subtitle_status` is treated as `none`.
- Existing download history remains usable.

Because `init_db.py` drops all tables, the app should also include a non-destructive schema upgrade path that adds missing subtitle columns with `ALTER TABLE` when the app starts.

## API Design

Add subtitle endpoints:

- `POST /api/downloads/<id>/subtitle`
  - Starts subtitle generation for a completed DB history item.
  - Returns immediately after marking the item `queued`.
  - Returns `404` if the history item is missing.
  - Returns `400` if the media file is missing or the item is already queued/processing.

- `GET /subtitle-file-by-history/<id>`
  - Downloads the generated SRT file.
  - Returns `404` if the history item or subtitle file is missing.

Extend `GET /api/downloads` completed items with:

- `subtitle_status`
- `subtitle_filename`
- `subtitle_error`
- `subtitle_created_at`

## Background Job Flow

Use a dedicated subtitle queue and worker threads separate from the download queue.

1. User clicks "자막 생성" on a completed item.
2. Server validates the DB item and source file.
3. Server sets `subtitle_status=queued`.
4. A subtitle worker picks up the job and sets `subtitle_status=processing`.
5. Worker sends multipart form data to:
   - `http://192.168.0.67:9010/v1/audio/transcriptions`
   - `model=deepdml/faster-whisper-large-v3-turbo-ct2`
   - `response_format=srt`
   - `file=<downloaded media>`
6. Worker writes the response body to an `.srt` file.
7. Worker marks the DB item `completed`, saves `subtitle_filename`, clears `subtitle_error`, and sets `subtitle_created_at`.
8. On failure, worker marks the DB item `error` and stores a concise error message.

## File Storage

Store subtitles under a dedicated directory:

- `subtitles/`

Use a deterministic filename based on the DB history id and source base name:

- `<history_id>-<source-base>.srt`

The source title can contain non-ASCII text, so the implementation should sanitize path separators and reserved filename characters before writing. If a subtitle is regenerated, overwrite the previous SRT for that history item.

## Frontend Behavior

For completed items:

- If `subtitle_status` is `none` or `error`, show `자막 생성`.
- If `subtitle_status` is `queued` or `processing`, show a disabled `자막 생성 중` state.
- If `subtitle_status` is `completed`, show `자막 다운로드`.
- If `subtitle_status` is `error`, show the error message and allow retry.

The existing polling behavior can refresh subtitle status through `/api/downloads`; no new realtime mechanism is needed.

## Configuration

Add environment variables with sensible defaults:

- `STT_API_BASE_URL=http://192.168.0.67:9010`
- `STT_MODEL=deepdml/faster-whisper-large-v3-turbo-ct2`
- `STT_RESPONSE_FORMAT=srt`
- `STT_TIMEOUT_SECONDS=1800`
- `SUBTITLE_FOLDER=./subtitles`

Do not set a default `language`; automatic detection is required.

## Error Handling

Handle these cases explicitly:

- STT API unavailable.
- STT API returns non-200 status.
- Source media file no longer exists.
- Subtitle output cannot be written.
- Duplicate click while a subtitle job is queued or processing.

Errors should not delete the original download or DB history row.

## Testing

Minimum verification:

- Python syntax compile succeeds.
- Existing `/api/downloads` still returns completed items.
- `POST /api/downloads/<id>/subtitle` rejects missing files.
- A generated subtitle job reaches `completed` with a test or existing media file when the STT API is available.
- `GET /subtitle-file-by-history/<id>` downloads the SRT after completion.

Use a synthetic audio file for API smoke tests when possible to avoid uploading existing user media without explicit approval.
