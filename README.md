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
- **Zotero** (with auto-export of `.bib` file including `citekey` and `file` fields)
- **Obsidian** (Advanced URI plugin recommended)
- **DEVONthink** (with scripting enabled)
- **Hookmark**
- **Hook CLI** ([available here](https://brettterpstra.com/projects/hook-cli/))
- **Alfred** (for optional automation)

## 🔨 Setup

Install the Better BibTeX plugin in Zotero and then export your library to a Better BibTeX or Better BibLaTeX `.bib` file. Make sure you select `keep updated` so that any changes you make in Zotero are immediately reflected in the `.bib` file. Add the path as `BIB_PATH` in your `.env` file (see below). This will allow queries and operations to happen on local rather than the much slower and less reliable Zotero Web API.

---

## 🔑 Environment Variables (`.env`)

Create a `.env` file in the root of the project:

```bash
BIB_PATH="/Users/yourname/zotero_utils/My Library.bib"
OBSIDIAN_VAULT="/Users/yourname/Documents/My Vault"
PYTHON_PATH=/Users/yourname/micromamba/envs/zotero/bin/python
LINKED_ITEMS=/Users/yourname/zotero_utils/linked_items.csv
HOOK_PATH=/usr/local/bin/hook
SCRIPT_PATH=/Users/yourname/zotero_utils/standardise_item_types.py
```

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

	- Iterates over all BibTeX citekeys.
	- Ensures Hookmark links exist between Zotero, DEVONthink, and the Obsidian note.
	- Refreshes any missing or outdated cache entries automatically.


## 🔗 Alfred Workflows

You can integrate both main scripts with Alfred for fast access.

	- `create_lit_note.py` → [Literature Linker](https://github.com/fortin/alfred-workflows/blob/main/Literature%20Linker.alfredworkflow)
	- `hook_links.py` → [Hook Zotero-Obsidian-PDF](https://github.com/fortin/alfred-workflows/blob/main/Hook%20Zotero-Obsidian-PDF.alfredworkflow)

These allow you to create and link notes directly from Alfred using citekeys.

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
📄 [Open PDF](/Users/antonio/Dropbox/Documents/DocumentLibrary/BibDesk/${citekey}.pdf)

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
| - Links Zotero ⇄ DEVONthink ⇄ Obsidian note            |
| - Refreshes missing cache entries                       |
+---------------------------------------------------------+
```

## ⚡ Pro Tip

You can run both scripts in Alfred or Raycast workflows, and with the caching system (`linked_items.csv`), performance scales well even with thousands of Zotero entries.

## 📜 License

GNU GPL version 3
