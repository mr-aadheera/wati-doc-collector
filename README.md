# WATI WhatsApp Document Collector

Automatically receives documents and images that clients send over WhatsApp, downloads them via the WATI API, and saves them into a structured local folder — organized by client phone number — with no manual downloading required.

Built as an internal office automation project by **ANFI Technologies**, Tiruchirappalli.

---

## How it works

```
Client sends a PDF/photo on WhatsApp
            │
            ▼
   WATI fires a "Message Received" webhook
            │
            ▼
   Flask app checks the message type (image/document/etc.)
            │
            ▼
   Flask calls WATI's Media API (getMedia) to fetch the file
            │
            ▼
   File saved to clients/<phone_number>/documents/
```

Duplicate protection is built in — if WATI resends the same webhook (which happens if the server takes too long to respond), the message ID is checked against a local log so the same file is never downloaded twice.

---

## Prerequisites

- Python 3.10+
- A [WATI](https://www.wati.io/) account with API access
- A **scoped API token** with media-read permission (see [Getting a working token](#getting-a-working-token) — the classic "API Docs" bearer token does *not* have media permissions by default)
- A free or paid [ngrok](https://ngrok.com/) account (a static domain is strongly recommended — see below)

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/mr-aadheera/wati-doc-collector.git
cd wati-doc-collector
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

### 2. Get your WATI Tenant ID and Endpoint

1. Log into your WATI account.
2. Go to **More** → **API Docs**.
3. Your API Endpoint URL (contains your Tenant ID) and Bearer Token are shown there.

### 3. Getting a working token

The classic bearer token shown on the API Docs page can authenticate most endpoints (like contacts) but **may return 401 Unauthorized on the media download endpoint**. If that happens:

1. Go to **Connector** → **API** → **Create API Token** (naming may vary slightly by plan).
2. Generate a new scoped token, selecting permissions that include media/file access.
3. Use this token instead of the classic one.

### 4. Reserve a static ngrok domain (recommended)

On the ngrok free plan, one static domain is included. Reserve it under **Domains** in your ngrok dashboard — this means your webhook URL never changes, even after restarting your PC.

### 5. Configure your secrets

```bash
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux
```

Edit `.env`:
```
WATI_TENANT_ID=your_tenant_id
WATI_ACCESS_TOKEN=your_scoped_access_token
NGROK_AUTH_TOKEN=your_ngrok_auth_token
NGROK_STATIC_DOMAIN=your_static_domain.ngrok-free.dev
```

### 6. Run the app

```bash
python app.py
```

### 7. Start the tunnel (separate terminal)

```bash
venv\Scripts\activate
python run_tunnel.py
```

This connects using your static domain, so the URL stays the same every time.

### 8. Register the webhook in WATI

1. Go to **Webhooks** in the WATI dashboard.
2. Click **Add Webhook**.
3. URL: `https://your-static-domain.ngrok-free.dev/wati-inbound`
4. Status: Enabled
5. Event: **Message Received**
6. Save.

### 9. Test it

Send a PDF or photo from WhatsApp to your WATI business number. Confirm:
- Flask terminal shows `200`
- The file appears under `clients/<sender_number>/documents/`

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
- `clients/` (downloaded client files) and `processed_message_ids.txt` are also excluded — this repo is the automation code, not a place to store real client documents or phone numbers.
- If a token is ever accidentally exposed, rotate it immediately from the WATI dashboard or ngrok dashboard.

---

## Production Notes

This is built for local development/testing. For continuous office use, consider:

- Hosting on an always-on machine (e.g. a Synology NAS via Docker) instead of a personal PC.
- Adding retry/alerting if the media download fails after all attempts.
- Moving processed-message tracking from a flat text file to a small SQLite database as volume grows.

---

## Tech Stack

- Python 3 / Flask — webhook receiver
- WATI Media API — file retrieval
- ngrok — tunnel with a static domain for a permanent public URL

## Author

**Aadhil Mohamed** — ANFI Technologies, Tiruchirappalli

## License

MIT
