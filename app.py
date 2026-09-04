import os
import time
import requests
from urllib.parse import urlparse, parse_qs
from flask import Flask, request, jsonify
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ---- Fill these in your .env file ----
WATI_TENANT_ID = os.getenv("WATI_TENANT_ID")          # e.g. "1090482"
WATI_ACCESS_TOKEN = os.getenv("WATI_ACCESS_TOKEN")    # from WATI dashboard -> API Docs

WATI_BASE_URL = f"https://live-mt-server.wati.io/{WATI_TENANT_ID}"

# Where downloaded files get saved
STORAGE_ROOT = "clients"

# Which message types count as "a file we should save"
FILE_TYPES = {"image", "document", "video", "audio", "voice"}

# Track message IDs we've already processed, so WATI's webhook retries
# don't cause the same file to be downloaded / confirmed multiple times.
PROCESSED_IDS_FILE = "processed_message_ids.txt"


def already_processed(message_id):
    if not os.path.exists(PROCESSED_IDS_FILE):
        return False
    with open(PROCESSED_IDS_FILE, "r") as f:
        return message_id in f.read().splitlines()


def mark_processed(message_id):
    with open(PROCESSED_IDS_FILE, "a") as f:
        f.write(message_id + "\n")


def download_media(webhook_file_url, save_path, max_retries=3, delay_seconds=2):
    """Extract the fileName from the webhook's file URL, then download it
    using WATI's proper documented Media API endpoint (not the raw link)."""
    parsed = urlparse(webhook_file_url)
    query_params = parse_qs(parsed.query)
    file_name = query_params.get("fileName", [None])[0]

    if not file_name:
        raise ValueError(f"Could not extract fileName from URL: {webhook_file_url}")

    media_api_url = f"{WATI_BASE_URL}/api/v1/getMedia"
    headers = {"Authorization": f"Bearer {WATI_ACCESS_TOKEN}"}
    params = {"fileName": file_name}

    last_error = None
    for attempt in range(1, max_retries + 1):
        resp = requests.get(media_api_url, headers=headers, params=params)
        if resp.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(resp.content)
            return
        last_error = resp
        print(f"Attempt {attempt} failed with status {resp.status_code}: {resp.text[:200]}")
        time.sleep(delay_seconds)

    last_error.raise_for_status()


def send_confirmation(whatsapp_number, message_text):
    """Send a plain text session reply back to the client via WATI."""
    url = f"{WATI_BASE_URL}/api/v1/sendSessionMessage/{whatsapp_number}"
    headers = {"Authorization": f"Bearer {WATI_ACCESS_TOKEN}"}
    params = {"messageText": message_text}
    requests.post(url, headers=headers, params=params)


@app.route("/wati-inbound", methods=["POST"])
def wati_inbound():
    data = request.json or {}

    msg_type = data.get("type")
    file_url = data.get("data")
    sender_number = data.get("waId")
    sender_name = data.get("senderName", "Unknown")
    message_id = data.get("whatsappMessageId") or data.get("id")

    # If it's not a file message, just acknowledge and stop here
    if msg_type not in FILE_TYPES or not file_url:
        return jsonify({"status": "ignored", "reason": "not a file message"}), 200

    # If we've already handled this exact message, don't do it again
    # (WATI can resend the same webhook if our response takes too long)
    if message_id and already_processed(message_id):
        return jsonify({"status": "duplicate", "reason": "already processed"}), 200

    # Build the folder path: clients/<phone_number>/documents/
    client_folder = os.path.join(STORAGE_ROOT, sender_number, "documents")
    os.makedirs(client_folder, exist_ok=True)

    # Build a filename: timestamp + original extension from the URL
    original_filename = file_url.split("fileName=")[-1].split("/")[-1]
    extension = os.path.splitext(original_filename)[-1] or ".bin"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_filename = f"{timestamp}{extension}"
    save_path = os.path.join(client_folder, save_filename)

    # Download and save the file
    download_media(file_url, save_path)

    # Mark this message as done so a webhook retry won't repeat any of this
    if message_id:
        mark_processed(message_id)

    return jsonify({
        "status": "saved",
        "path": save_path,
        "sender": sender_number,
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
