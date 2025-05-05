#!/bin/bash
cd /Users/antonio/Dropbox/Code/Python/zotero_utils
export $(grep -v '^#' .env | xargs)

LOCKFILE="standardise.lock"

# Check for existing lockfile
if [ -e "$LOCKFILE" ]; then
    echo "Another instance is running. Exiting." >> hazel_log.txt
    exit 0
fi

# Create lockfile
touch "$LOCKFILE"

# Run the script
micromamba run -n zotero python standardise_item_types.py >> hazel_log.txt 2>&1
changes=$?

# Remove lockfile
rm -f "$LOCKFILE"

# Notify if changes occurred
if [ $changes -ne 0 ]; then
    osascript -e 'display notification "BibTeX item types standardised" with title "Zotero Cleanup"'
fi