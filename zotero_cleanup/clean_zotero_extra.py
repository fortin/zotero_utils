from pyzotero import zotero
from decouple import config


# Replace these with your actual credentials
ZOTERO_USER_ID = config("ZOTERO_USER_ID")
ZOTERO_API_KEY = config("ZOTERO_API_KEY")
LIBRARY_TYPE = 'user'  # Use 'group' if accessing a group library

# Initialize the Zotero client
zot = zotero.Zotero(ZOTERO_USER_ID, LIBRARY_TYPE, ZOTERO_API_KEY)

# Retrieve all top-level items in the library
items = zot.everything(zot.top())

cleaned_count = 0

for item in items:
    extra = item['data'].get('extra', '')
    if 'Citation Key:' in extra:
        # Remove lines starting with 'Citation Key:'
        lines = extra.split('\n')
        filtered_lines = [line for line in lines if not line.strip().lower().startswith('citation key:')]
        new_extra = '\n'.join(filtered_lines)
        
        # Update the item if changes were made
        if new_extra != extra:
            item['data']['extra'] = new_extra
            zot.update_item(item)
            cleaned_count += 1

print(f"✅ Cleaned 'Citation Key:' from {cleaned_count} items.")