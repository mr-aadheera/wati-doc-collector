import os
import time
import json
import re
import requests
from urllib.parse import urlparse, parse_qs
from flask import Flask, request, jsonify
from datetime import datetime
from dotenv import load_dotenv
import pytesseract
from PIL import Image
from pdf2image import convert_from_path

load_dotenv()

app = Flask(__name__)

# ---- WATI config ----
WATI_TENANT_ID = os.getenv("WATI_TENANT_ID")
WATI_ACCESS_TOKEN = os.getenv("WATI_ACCESS_TOKEN")
WATI_BASE_URL = f"https://live-mt-server.wati.io/{WATI_TENANT_ID}"

# ---- OCR config ----
# UPDATE THESE PATHS to match where you installed Tesseract and Poppler
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER_PATH = r"C:\poppler\Library\bin"

STORAGE_ROOT = "clients"
FILE_TYPES = {"image", "document"}
PROCESSED_IDS_FILE = "processed_message_ids.txt"

# Keyword rules: category -> list of phrases that, if found in the OCR text,
# suggest the document belongs to that category. Checked in order, first
# match wins. Add/adjust phrases as you see real documents come through.
CATEGORY_RULES = [
    ("PAN Card", ["permanent account number", "income tax department", "govt. of india"]),
    ("Aadhaar Card", ["unique identification authority", "aadhaar", "government of india"]),
    ("GST Certificate", ["goods and services tax", "gstin", "certificate of registration"]),
    ("Form 16", ["form no. 16", "form 16", "certificate under section 203"]),
    ("TDS Certificate", ["tax deducted at source", "tds certificate"]),
    ("Bank Statement", ["statement of account", "ifsc", "account number", "bank statement"]),
    ("Invoice", ["invoice", "tax invoice", "bill of supply"]),
    ("Udyam Certificate", ["udyam registration", "udyam"]),
    ("ITR Acknowledgement", ["income tax return", "acknowledgement number", "itr-v"]),
    ("Notice", ["notice under section", "show cause notice"]),
]

# Regex patterns to pull out common identifiers
PATTERNS = {
    "pan": r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
    "gstin": r"\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]\b",
    "amount": r"(?:Rs\.?|INR|₹)\s?[\d,]+\.?\d*",
    "date": r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
}


def already_processed(message_id):
    if not os.path.exists(PROCESSED_IDS_FILE):
        return False
    with open(PROCESSED_IDS_FILE, "r") as f:
        return message_id in f.read().splitlines()


def mark_processed(message_id):
    with open(PROCESSED_IDS_FILE, "a") as f:
        f.write(message_id + "\n")


def download_media(webhook_file_url, save_path, max_retries=3, delay_seconds=2):
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
        print(f"Attempt {attempt} failed with status {resp.status_code}")
        time.sleep(delay_seconds)

    last_error.raise_for_status()


def extract_text(file_path):
    """Run OCR on the file (image directly, or PDF pages converted to images)."""
    extension = os.path.splitext(file_path)[-1].lower()

    if extension == ".pdf":
        pages = convert_from_path(file_path, poppler_path=POPPLER_PATH)
        text = ""
        for page in pages:
            text += pytesseract.image_to_string(page) + "\n"
        return text
    else:
        image = Image.open(file_path)
        return pytesseract.image_to_string(image)


def classify_and_extract(file_path):
    """Free, local classification: OCR the document, then match keywords
    and regex patterns to guess the category and pull out key fields."""
    try:
        text = extract_text(file_path)
    except Exception as e:
        print(f"OCR failed: {e}")
        return {"category": "Other", "extracted_fields": {}, "note": f"OCR error: {e}"}

    text_lower = text.lower()

    category = "Other"
    for cat_name, keywords in CATEGORY_RULES:
        if any(keyword in text_lower for keyword in keywords):
            category = cat_name
            break

    pan_match = re.search(PATTERNS["pan"], text)
    gstin_match = re.search(PATTERNS["gstin"], text)
    amount_match = re.search(PATTERNS["amount"], text)
    date_match = re.search(PATTERNS["date"], text)

    return {
        "category": category,
        "extracted_fields": {
            "pan": pan_match.group(0) if pan_match else None,
            "gstin": gstin_match.group(0) if gstin_match else None,
            "amount": amount_match.group(0) if amount_match else None,
            "date": date_match.group(0) if date_match else None,
        },
        "raw_text_preview": text[:300],
    }


@app.route("/wati-inbound", methods=["POST"])
def wati_inbound():
    data = request.json or {}

    msg_type = data.get("type")
    file_url = data.get("data")
    sender_number = data.get("waId")
    message_id = data.get("whatsappMessageId") or data.get("id")

    if msg_type not in FILE_TYPES or not file_url:
        return jsonify({"status": "ignored", "reason": "not a file message"}), 200

    if message_id and already_processed(message_id):
        return jsonify({"status": "duplicate", "reason": "already processed"}), 200

    client_folder = os.path.join(STORAGE_ROOT, sender_number, "documents")
    os.makedirs(client_folder, exist_ok=True)

    original_filename = file_url.split("fileName=")[-1].split("/")[-1]
    extension = os.path.splitext(original_filename)[-1] or ".bin"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_filename = f"{timestamp}{extension}"
    temp_path = os.path.join(client_folder, temp_filename)

    download_media(file_url, temp_path)

    result = classify_and_extract(temp_path)
    category = result.get("category", "Other").replace(" ", "_")

    final_filename = f"{timestamp}_{category}{extension}"
    final_path = os.path.join(client_folder, final_filename)
    os.rename(temp_path, final_path)

    metadata_path = os.path.join(client_folder, f"{timestamp}_{category}.json")
    with open(metadata_path, "w") as f:
        json.dump(result, f, indent=2)

    if message_id:
        mark_processed(message_id)

    return jsonify({
        "status": "processed",
        "file": final_path,
        "classification": result,
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
