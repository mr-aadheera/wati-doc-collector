# WATI WhatsApp Document Collector + Free AI-Style Classifier

Automatically receives documents and images that clients send over WhatsApp, downloads them via the WATI API, runs local OCR to classify what type of document it is (PAN card, GST certificate, bank statement, etc.), extracts key fields, and saves everything into a structured local folder — organized by client phone number.

No paid APIs — classification runs entirely locally using free, open-source OCR (Tesseract).

Built by **Aadhil Mohamed** as an internal office automation project.

---

## How it works

```
Client sends a PDF/photo on WhatsApp
            │
            ▼
   WATI fires a "Message Received" webhook
            │
            ▼
   Flask app downloads the file via WATI's Media API
            │
            ▼
   Local OCR (Tesseract) extracts the text from the file
            │
            ▼
   Keyword + regex rules classify the document type and
   pull out fields like PAN, GSTIN, dates, and amounts
            │
            ▼
   File renamed with its category + a matching .json
   metadata file saved to clients/<phone_number>/documents/
```

Duplicate protection is built in — if WATI resends the same webhook, the message ID is checked against a local log so the same file is never processed twice.

---

## Prerequisites

- Python 3.10+
- A [WATI](https://www.wati.io/) account with API access
- A **scoped API token** with media-read permission (the classic "API Docs" bearer token does *not* have media permissions by default — see [Getting a working token](#getting-a-working-token))
- A free or paid [ngrok](https://ngrok.com/) account (a static domain is strongly recommended)
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) installed locally (Windows build)
- [Poppler for Windows](https://github.com/oschwartz10612/poppler-windows/releases) (needed to convert PDF pages to images for OCR)

---

## Setup

### 1. Clone and install Python dependencies

```bash
git clone https://github.com/mr-aadheera/wati-doc-collector.git
cd wati-doc-collector
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 2. Install Tesseract OCR

Download and run the Windows installer from the link above. Default install location (`C:\Program Files\Tesseract-OCR`) works fine with the default config in this repo.

### 3. Install Poppler

Download the Windows release zip, extract it (e.g. to `C:\poppler`), then locate the exact folder containing `pdftoppm.exe` — the path varies slightly by release version. Update `POPPLER_PATH` at the top of `app.py` to match.

### 4. Get your WATI Tenant ID and a working token

1. Log into WATI → **More** → **API Docs** for your Tenant ID and base bearer token.
2. If the media download endpoint returns 401 with that token (a known limitation of the classic token), go to **Connector** → **API** → **Create API Token** and generate a scoped token with media-read permission instead.

### 5. Reserve a static ngrok domain (recommended)

Reserve a free static domain under **Domains** in your ngrok dashboard, so your webhook URL never changes across restarts.

### 6. Configure your secrets

```bash
copy .env.example .env
```
Edit `.env`:
```
WATI_TENANT_ID=your_tenant_id
WATI_ACCESS_TOKEN=your_scoped_access_token
NGROK_AUTH_TOKEN=your_ngrok_auth_token
NGROK_STATIC_DOMAIN=your_static_domain.ngrok-free.dev
```

### 7. Run it

```bash
python app.py
```
In a separate terminal:
```bash
python run_tunnel.py
```

### 8. Register the webhook in WATI

URL: `https://your-static-domain.ngrok-free.dev/wati-inbound`, event: **Message Received**, status: Enabled.

### 9. Test it

Send a document via WhatsApp. Check `clients/<sender_number>/documents/` for the renamed file plus a `.json` file containing the detected category and extracted fields.

---

## How classification works

This uses a simple, transparent, fully local approach instead of a paid AI API:

1. **OCR**: Tesseract extracts raw text from the image or PDF.
2. **Keyword matching**: the extracted text is checked against a list of phrases per category (e.g. "Unique Identification Authority of India" → Aadhaar Card). See `CATEGORY_RULES` in `app.py`.
3. **Regex extraction**: PAN numbers, GSTIN numbers, dates, and amounts are pulled out using pattern matching. See `PATTERNS` in `app.py`.

This works well on clean, well-lit, printed documents. Accuracy drops on blurry or angled phone photos, since OCR quality depends heavily on image clarity — no different from any OCR-based tool. The `raw_text_preview` field saved in each metadata JSON makes it easy to see exactly what OCR read, which is useful for tuning the keyword rules as more real documents come through.

### Extending the categories

Add more phrases to `CATEGORY_RULES` in `app.py` as you see documents that get misclassified — it's plain Python, no retraining needed.

---

## Auto-start on PC boot (Windows)

1. Edit `start_wati_automation.bat` and set `PROJECT_DIR` to your actual path.
2. Open **Task Scheduler** → **Create Task**.
3. **General tab**: name it, leave **"Run only when user is logged on"** selected (avoids needing your Windows password).
4. **Triggers tab**: New → **At log on**.
5. **Actions tab**: New → **Start a program** → select `start_wati_automation.bat`.
6. **Conditions tab**: uncheck AC-power-only if on a laptop.
7. Save, then restart your PC to confirm it launches automatically.

---

## Security

- `.env` is excluded via `.gitignore` — never commit real credentials.
- `clients/` (downloaded client files, which may include personal ID documents) and `processed_message_ids.txt` are also excluded — this repo is the automation code, not a place to store real client documents.
- If a token is ever accidentally exposed, rotate it immediately from the WATI dashboard.

---

## Production Notes

This is built for local development/testing. For continuous office use, consider:

- Hosting on an always-on machine (e.g. a Synology NAS via Docker) instead of a personal PC.
- Image preprocessing (grayscale, contrast boost, deskew) before OCR to improve accuracy on rough phone photos.
- Moving processed-message tracking and extracted metadata from flat files into a small SQLite database as volume grows.
- Adding a manual review step for low-confidence classifications rather than trusting them outright, since this is real client data (PAN, Aadhaar, financial documents) — misfiling matters.

---

## Tech Stack

- Python 3 / Flask — webhook receiver
- WATI Media API — file retrieval
- Tesseract OCR + pdf2image — local, free document text extraction
- ngrok — tunnel with a static domain for a permanent public URL

## Author

**Aadhil Mohamed**

## License

MIT
