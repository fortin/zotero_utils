# Zotero Utils

**Advanced tools for managing a Zotero–Obsidian–DEVONthink academic workflow**  
_Optimized for high-volume literature note-taking and PDF management._

---

## 📝 Overview

This toolkit automates:

- Creating and updating **literature notes** in Obsidian based on your Zotero library.
- Searching DEVONthink for matching PDFs and linking them to the notes.
- Creating **Hookmark** connections between Zotero, Obsidian notes, and DEVONthink PDFs.
- Maintaining a persistent cache (`linked_items.csv`) to avoid redundant operations.

---

## 🔧 Requirements

- **Python 3.9+** with:
  - `bibtexparser`
  - `pandas`
  - `pyyaml`
  - `python-decouple`
- **Zotero**  
  (Export your library as a Better CSL JSON `.json` with `Keep updated` enabled.)
- **Obsidian**  
  (Advanced URI plugin recommended)
- **DEVONthink** (with scripting enabled)
- **Hookmark**
- **Hook CLI** ([available here](https://brettterpstra.com/projects/hook-cli/))
- **Alfred** (for optional automation)

---

## 🔨 Setup

1. **In Zotero**  
   - Install the **Better BibTeX** plugin.
   - Export your library as **Better CSL JSON** with **Keep updated** enabled.  
     _(This prevents stale data and eliminates the need for manual exports.)_

2. **Environment Variables**  
   Create a `.env` file in the root of the project:

   ```bash
   CSL_JSON_PATH="/Users/yourname/zotero_utils/My Library.json"
   OBSIDIAN_VAULT="/Users/yourname/Documents/My Vault"
   PYTHON_PATH=/Users/yourname/micromamba/envs/zotero/bin/python
   LINKED_ITEMS=/Users/yourname/zotero_utils/linked_items.csv
   HOOK_PATH=/usr/local/bin/hook
   SCRIPT_PATH=/Users/yourname/zotero_utils/standardise_item_types.py
   MARKDOWN_IN_DEVONTHINK=False  # or True
   PDF_IN_DEVONTHINK=True        # or False
   ```

3. Linking Behavior (`MARKDOWN_IN_DEVONTHINK` & `PDF_IN_DEVONTHINK`)

- `MARKDOWN_IN_DEVONTHINK=True` → Hook links will point to the note in DEVONthink (assuming it’s indexed there).
- `MARKDOWN_IN_DEVONTHINK=False` → Hook links will point to the note in Obsidian.
- `PDF_IN_DEVONTHINK=True` → Hook links will point to the PDF in DEVONthink (assuming indexed).
- `PDF_IN_DEVONTHINK=False` → Hook links will point directly to the PDF in Finder.

## 🔄 Typical Workflow

### 1️⃣ Create or update a literature note

```bash
python create_lit_note.py <citekey>
```

- Creates or updates a note in the appropriate folder inside the Obsidian vault.
- Searches DEVONthink for the PDF and adds a link if found.
- Updates the `linked_items.csv` cache.
- Creates Hookmark links between the note, the DEVONthink PDF, and the Zotero item.

### 2️⃣ Hook all items incrementally (batch)

```bash
python hook_links.py
```

- Iterates over all CSL JSON citekeys.
- Ensures Hookmark links exist between Zotero, DEVONthink, and the Obsidian note.
- Refreshes any missing or outdated cache entries automatically.

## 🔗 Alfred Workflows

You can integrate both main scripts with Alfred for fast access.

- `create_lit_note.py` → Literature Linker
- `hook_links.py` → Hook Zotero-Obsidian-PDF

_These allow you to create and link notes directly from Alfred using citekeys._

## 🧠 Template for Obsidian Literature Notes

(For use with the Templater plugin in Obsidian)

```markdown
<%*
const citekey = tp.user.citationField("citekey") || "unknown-citekey";
const title = tp.user.citationField("title") || "Untitled";
const authors = tp.user.citationField("authorString") || "Unknown Author(s)";
const doi = tp.user.citationField("DOI") || "";
const zoteroURI = tp.user.citationField("zoteroSelectURI") || "";
const itemType = tp.user.citationField("itemType")?.toLowerCase() || "misc";

// === Year fallback ===
let year = tp.user.citationField("year");
if (!year || year.trim() === "") {
    let date = tp.user.citationField("date") || "";
    const yearMatch = date.match(/\d{4}/);
    year = yearMatch ? yearMatch[0] : "n.d.";
}

// === Folder mapping ===
let targetFolder = "📁 500 📒 Notes/📁 520 🗒 Zettelkasten/522 📚 Source Material/";
if (["article", "incollection", "inbook", "inproceedings", "conference"].includes(itemType)) {
    targetFolder += "532 📄 Articles";
} else if (["book", "booklet", "masterthesis", "phdthesis", "proceedings"].includes(itemType)) {
    targetFolder += "542 📖 Books";
} else {
    targetFolder += "572 ⺟ Other";
}

await tp.file.move(`${targetFolder}/@${citekey}`);
%>

---
title: "<%* tR += title %>"
authors: <%* tR += authors %>
citation: @<%* tR += citekey %>
year: <%* tR += year %>
DOI: <%* tR += doi %>
URI: <%* tR += zoteroURI %>
tags: [[literature]]
---

📎 [Open in Zotero](<%* tR += zoteroURI %>)
📄 [Open PDF](/path/to/pdf_folder/${citekey}.pdf)

## Summary
-

## Key Points
-

## Quotes & Highlights
> “”

## My Thoughts
-

## Related Notes
-
```

## 🔄 Workflow Diagram

```plaintext
+-----------+        +--------------------+        +----------------+
|  Zotero   | ---->  | create_lit_note.py | ---->  | Obsidian Note  |
+-----------+        +--------------------+        +----------------+
                         |                               |
                         v                               |
                  DEVONthink search                      |
                         |                               |
                         v                               |
                [Add DEVONthink link] <------------------
                         |
                         v
                   Update linked_items.csv

+---------------------------------------------------------+
| hook_links.py                                           |
| - Links Zotero ⇄ DEVONthink ⇄ Obsidian note             |
| - Refreshes missing cache entries                       |
+---------------------------------------------------------+
```

## ⚡ Pro Tip

- You can run both scripts in Alfred or Raycast workflows.
- With the caching system (`linked_items.csv`), performance scales well even with thousands of Zotero entries.

## 📜 License

GNU GPL version 3
