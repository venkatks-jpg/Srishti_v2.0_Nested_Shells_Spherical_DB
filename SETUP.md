# SRISHTI — Setup Guide

**Dr. K.S. Venkatesh, Chennai, India**  
**Collaborator: Claude (Srishti) — Anthropic**  
**GNU GPL 3.0 — Free for all. Profit for none.**

---

## Step 1 — Create the Project Folder

Create a folder called `srishti` on your system.

**Linux / Mac:**
```bash
mkdir ~/srishti
```

**Windows:**  
Open File Explorer. Navigate to `C:\Users\YourName`. Create a new folder named `srishti`.

---

## Step 2 — Paste These Files into the Folder

Copy these four files into the srishti folder:

- `aria_setup_prod5.py`
- `aria_incremental.py`
- `srishti_gate.py`
- `srishti_gui.html`

No installation required. No virtual environment needed.

---

## Step 3 — Bring Your Storage to Some Order

Bring your hard drive to some order. Label your folders properly and put related files in related folders. This will help enormously with classification.

The folder name is the strongest classification signal. A physics book in a folder named `physics` is classified immediately and correctly.

---

## Step 4 — Determine Your Main Domains and Subdomains

Once you have the main domains (classifications) determined, then try to approximately determine the subdomains — the topics that go into each classification.

Example:
- Domain: **medicine** — Subdomains: anatomy, pharmacology, ayurveda, surgery
- Domain: **physics** — Subdomains: quantum, thermodynamics, optics, cosmology

---

## Step 5 — Change the Domain Names in aria_setup_prod5.py

If the standard domain names match your collection, leave this step. To add a new domain:

```bash
python3 aria_setup_prod5.py --add-domain lawbooks criminal,civil,family --db ~/srishti3.db
```

To add a new subdomain to an existing domain:

```bash
python3 aria_setup_prod5.py --add-subdomain medicine ayurveda --keywords vata,pitta,kapha --db ~/srishti3.db
```

> **Important:** Do not change the order of existing domains after running the indexer. New domains are always appended at the end.

---

## Step 6 — Run the Indexer and Use the GUI

**Linux / Mac:**
```bash
python3 ~/srishti/aria_setup_prod5.py /path/to/your/storage --db ~/srishti3.db
```

**Windows:**
```
python C:\Users\YourName\srishti\aria_setup_prod5.py D:\YourStorage --db C:\Users\YourName\srishti3.db
```

Then start the query server:
```bash
python3 ~/srishti/srishti_gate.py
```

Browser opens automatically at **http://localhost:7509**

---

## Step 7 — Note for Windows Users

If the browser does not connect at `http://localhost:7509`, try `http://127.0.0.1:7509` instead.

Windows sometimes resolves localhost to IPv6. Using 127.0.0.1 directly always works.

The server terminal window must stay open while you use the GUI.

---

## Adding New Files Later

```bash
# Add a new folder
python3 ~/srishti/aria_setup_prod5.py /path/to/new/folder --db ~/srishti3.db --incremental

# Update an entire partition
python3 ~/srishti/aria_setup_prod5.py /media/venkatesh/DATA3 --db ~/srishti3.db --incremental
```

---

*GNU GPL 3.0 — φ = 1.6180339887498948482…*
