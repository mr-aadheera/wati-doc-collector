"""
Starts an ngrok tunnel pointing to the local Flask app (port 5000),
using a reserved static domain so the URL never changes between restarts.
"""

import os
from pyngrok import ngrok
from dotenv import load_dotenv

load_dotenv()

NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN")
NGROK_STATIC_DOMAIN = os.getenv("NGROK_STATIC_DOMAIN")  # e.g. "your-name.ngrok-free.app"

if NGROK_AUTH_TOKEN:
    ngrok.set_auth_token(NGROK_AUTH_TOKEN)

if NGROK_STATIC_DOMAIN:
    public_url = ngrok.connect(5000, domain=NGROK_STATIC_DOMAIN)
else:
    public_url = ngrok.connect(5000)

print("Your public URL:", public_url)
print("Use this + /wati-inbound as your WATI webhook URL")

input("Press Enter to stop the tunnel...")
