# Manual STT Subtitles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add manual subtitle generation for completed downloads using the configured STT API.

**Architecture:** Keep the existing Flask monolith intact and add a small subtitle job queue beside the download queue. Store subtitle state on `DownloadHistory`, write SRT files into `SUBTITLE_FOLDER`, and expose the state through the existing `/api/downloads` response.

**Tech Stack:** Flask 3, Flask-SQLAlchemy, SQLite, requests, Speaches/OpenAI-compatible `/v1/audio/transcriptions`.

---

## File Structure

- Modify `app.py`: add subtitle config, DB columns, schema upgrade, subtitle worker, endpoints, and response fields.
- Modify `templates/index.html`: add subtitle buttons and client-side actions.
- Modify `static/style.css`: add subtitle button/status styling.
- Modify `.env.example`: document STT and subtitle settings.
- Modify `.gitignore`: ignore generated subtitle files while allowing `.gitkeep`.
- Create `subtitles/.gitkeep`: keep subtitle directory in the repo.
- Create `tests/__init__.py`: make tests importable with `unittest`.
- Create `tests/test_subtitle_helpers.py`: cover filename sanitization and subtitle status defaults.

### Task 1: Configuration, Model Fields, and Helpers

**Files:**
- Modify: `app.py`
- Modify: `.env.example`
- Modify: `.gitignore`
- Create: `subtitles/.gitkeep`
- Create: `tests/__init__.py`
- Create: `tests/test_subtitle_helpers.py`

- [ ] **Step 1: Write the failing helper tests**

Create `tests/__init__.py` as an empty file.

Create `tests/test_subtitle_helpers.py`:

```python
import unittest

from app import build_subtitle_filename, get_subtitle_status


class SubtitleHelperTests(unittest.TestCase):
    def test_build_subtitle_filename_sanitizes_reserved_characters(self):
        filename = build_subtitle_filename(42, 'a/b:c*?"<>|.webm')
        self.assertEqual(filename, "42-a_b_c______.srt")

    def test_build_subtitle_filename_handles_blank_source(self):
        filename = build_subtitle_filename(7, "")
        self.assertEqual(filename, "7-subtitle.srt")

    def test_get_subtitle_status_defaults_to_none(self):
        class History:
            subtitle_status = None

        self.assertEqual(get_subtitle_status(History()), "none")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m unittest tests.test_subtitle_helpers
```

Expected: FAIL or import error because `build_subtitle_filename` and `get_subtitle_status` do not exist yet.

- [ ] **Step 3: Add config, model fields, and helper functions**

In `app.py`, add environment-driven settings near existing downloader settings:

```python
SUBTITLE_FOLDER = os.getenv('SUBTITLE_FOLDER', './subtitles')
STT_API_BASE_URL = os.getenv('STT_API_BASE_URL', 'http://192.168.0.67:9010').rstrip('/')
STT_MODEL = os.getenv('STT_MODEL', 'deepdml/faster-whisper-large-v3-turbo-ct2')
STT_RESPONSE_FORMAT = os.getenv('STT_RESPONSE_FORMAT', 'srt')
STT_TIMEOUT_SECONDS = int(os.getenv('STT_TIMEOUT_SECONDS', 1800))
```

Add subtitle fields to `DownloadHistory`:

```python
subtitle_status = db.Column(db.String(20), default='none')
subtitle_filename = db.Column(db.String(500))
subtitle_error = db.Column(db.String(1000))
subtitle_created_at = db.Column(db.DateTime)
```

Create the subtitle directory:

```python
os.makedirs(SUBTITLE_FOLDER, exist_ok=True)
```

Add helpers:

```python
def get_subtitle_status(history):
    return getattr(history, 'subtitle_status', None) or 'none'


def build_subtitle_filename(history_id, source_filename):
    base = os.path.splitext(os.path.basename(source_filename or ''))[0].strip()
    if not base:
        base = 'subtitle'
    safe_base = ''.join('_' if ch in '\\/:*?"<>|' else ch for ch in base)
    safe_base = safe_base.strip(' ._') or 'subtitle'
    return f'{history_id}-{safe_base}.srt'
```

Update `.env.example`:

```env
SUBTITLE_FOLDER=./subtitles
STT_API_BASE_URL=http://192.168.0.67:9010
STT_MODEL=deepdml/faster-whisper-large-v3-turbo-ct2
STT_RESPONSE_FORMAT=srt
STT_TIMEOUT_SECONDS=1800
```

Update `.gitignore`:

```gitignore
subtitles/*
!subtitles/.gitkeep
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python -m unittest tests.test_subtitle_helpers
```

Expected: PASS.

### Task 2: Non-Destructive Schema Upgrade

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add schema upgrade function**

Add a function after helper definitions:

```python
def ensure_database_schema():
    db.create_all()
    inspector = db.inspect(db.engine)
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
                conn.execute(db.text(f'ALTER TABLE download_history ADD COLUMN {column_name} {column_type}'))
```

Replace the startup `db.create_all()` call with:

```python
ensure_database_schema()
```

- [ ] **Step 2: Run syntax verification**

Run:

```bash
python -m compileall app.py init_db.py
```

Expected: both files compile without errors.

### Task 3: Subtitle Queue, STT Worker, and Download Endpoint

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add subtitle queue state and worker**

Add global queue state:

```python
subtitle_queue = Queue()
subtitle_lock = threading.Lock()
```

Add worker functions:

```python
def request_subtitle_from_stt(source_path):
    url = f'{STT_API_BASE_URL}/v1/audio/transcriptions'
    with open(source_path, 'rb') as file_obj:
        response = requests.post(
            url,
            data={
                'model': STT_MODEL,
                'response_format': STT_RESPONSE_FORMAT,
            },
            files={'file': (os.path.basename(source_path), file_obj)},
            timeout=STT_TIMEOUT_SECONDS,
        )
    if response.status_code != 200:
        raise Exception(f'STT API error {response.status_code}: {response.text[:500]}')
    return response.text


def subtitle_worker():
    while True:
        history_id = subtitle_queue.get()
        if history_id is None:
            break
        try:
            generate_subtitle_for_history(history_id)
        finally:
            subtitle_queue.task_done()
```

Add `generate_subtitle_for_history(history_id)` to load the DB row, validate the source file, mark `processing`, call STT, write the SRT, and mark `completed` or `error`.

- [ ] **Step 2: Start subtitle workers**

After download workers are started, start one subtitle worker:

```python
subtitle_worker_thread = threading.Thread(target=subtitle_worker, daemon=True)
subtitle_worker_thread.start()
```

- [ ] **Step 3: Add endpoints**

Add:

```python
@app.route('/api/downloads/<int:history_id>/subtitle', methods=['POST'])
def start_subtitle_generation(history_id):
    ...


@app.route('/subtitle-file-by-history/<int:history_id>')
def download_subtitle_file_by_history(history_id):
    ...
```

`start_subtitle_generation` should reject missing media and duplicate queued/processing jobs, then set `subtitle_status='queued'`, clear stale errors, enqueue `history_id`, and return JSON.

`download_subtitle_file_by_history` should verify the history row and SRT path before returning `send_file(..., as_attachment=True)`.

- [ ] **Step 4: Run syntax verification**

Run:

```bash
python -m compileall app.py init_db.py
```

Expected: compile succeeds.

### Task 4: Include Subtitle State in Download List

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Extend completed item JSON**

In `get_downloads`, add to completed history item dictionaries:

```python
'subtitle_status': get_subtitle_status(h),
'subtitle_filename': h.subtitle_filename,
'subtitle_error': h.subtitle_error,
'subtitle_created_at': h.subtitle_created_at.isoformat() if h.subtitle_created_at else None,
```

- [ ] **Step 2: Run syntax verification**

Run:

```bash
python -m compileall app.py init_db.py
```

Expected: compile succeeds.

### Task 5: Frontend Subtitle Controls

**Files:**
- Modify: `templates/index.html`
- Modify: `static/style.css`

- [ ] **Step 1: Add subtitle buttons to completed items**

In `getActionButtons(item)`, add subtitle button rendering for completed items:

```javascript
if (item.type === 'completed') {
    const subtitleStatus = item.subtitle_status || 'none';
    if (subtitleStatus === 'completed') {
        buttons += `<button class="subtitle-download-btn" onclick="downloadSubtitle('${item.id}')">자막</button>`;
    } else if (subtitleStatus === 'queued' || subtitleStatus === 'processing') {
        buttons += `<button class="subtitle-processing-btn" disabled>자막 생성 중</button>`;
    } else {
        buttons += `<button class="subtitle-generate-btn" onclick="generateSubtitle('${item.id}')">자막 생성</button>`;
    }
}
```

Add an error line in `renderDownloadList`:

```javascript
${item.subtitle_status === 'error' ? `<span class="error-msg">자막 오류: ${item.subtitle_error || '자막 생성 실패'}</span>` : ''}
```

Add functions:

```javascript
async function generateSubtitle(itemId) {
    try {
        const response = await fetch(`/api/downloads/${itemId}/subtitle`, { method: 'POST' });
        const data = await response.json();
        if (!response.ok) {
            alert('자막 오류: ' + (data.error || '자막 생성 요청 실패'));
            return;
        }
        loadDownloads(false);
    } catch (error) {
        alert('자막 오류: ' + error.message);
    }
}

function downloadSubtitle(itemId) {
    window.location.href = `/subtitle-file-by-history/${itemId}`;
}
```

- [ ] **Step 2: Add CSS**

Add button classes:

```css
.subtitle-generate-btn,
.subtitle-download-btn,
.subtitle-processing-btn {
    background: #2563eb;
    color: white;
}

.subtitle-download-btn {
    background: #16a34a;
}

.subtitle-processing-btn {
    background: #52525b;
    cursor: not-allowed;
}
```

- [ ] **Step 3: Run syntax verification**

Run:

```bash
python -m compileall app.py init_db.py
```

Expected: compile succeeds.

### Task 6: Manual Smoke Checks

**Files:**
- Read-only verification

- [ ] **Step 1: Run unit tests**

Run:

```bash
python -m unittest tests.test_subtitle_helpers
```

Expected: PASS.

- [ ] **Step 2: Run compile check**

Run:

```bash
python -m compileall app.py init_db.py
```

Expected: PASS.

- [ ] **Step 3: Check git status**

Run:

```bash
git status --short
```

Expected: only intended files are modified or added.

---

## Self-Review

- Spec coverage: manual button, language auto-detection, SRT response, background queue, DB state, `.env` configuration, error handling, and tests are all covered.
- Placeholder scan: no TBD/TODO placeholders.
- Type consistency: subtitle status field names match between model, API response, and frontend.
