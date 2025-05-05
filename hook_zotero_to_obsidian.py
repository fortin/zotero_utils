import os
import subprocess
from pathlib import Path
import requests
from decouple import config

# === CONFIG ===
obsidian_vault = Path(config("OBSIDIAN_VAULT"))
zotero_user_id = config("ZOTERO_USER_ID")
zotero_api_key = config("ZOTERO_API_KEY")

# === Fetch Zotero items with citation keys ===
headers = {"Zotero-API-Key": zotero_api_key}
items_url = f"https://api.zotero.org/users/{zotero_user_id}/items?format=bibtex&limit=10000"

response = requests.get(items_url, headers=headers)
items = response.json()

# === Map citation keys to Zotero URIs ===
zotero_lookup = {}
for item in items:
    cite_key = item.get("data", {}).get("citationKey", "").strip()
    if cite_key:
        zotero_uri = f"zotero://select/items/{item['key']}"
        zotero_lookup[cite_key] = zotero_uri

# === Scan Obsidian notes and hook ===
for note in obsidian_vault.glob("**/@*.md"):
    cite_key = note.stem.lstrip("@")
    zotero_uri = zotero_lookup.get(cite_key)
    if zotero_uri:
        print(f"🔗 Hooking {cite_key} to {note.name}")
        subprocess.run(["hook", "link", "--name", cite_key, zotero_uri, str(note)])
    else:
        print(f"⚠️ No Zotero item found for {cite_key}")