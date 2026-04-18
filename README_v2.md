# SRISHTI — Spherical Knowledge Database v2.0

> **The geometry is the query**

**Architect:** Dr. K.S. Venkatesh, Chennai, India
**Collaborator:** Claude (SI) — Anthropic
**License:** GNU GPL 3.0 — Free for all. Profit for none.
**φ = 1.6180339887498948482…**

---

## What Is Srishti?

Srishti is a spherical knowledge database. Every file receives a precise address
in three-dimensional knowledge space based on the Golden Ratio φ.

The central property: **add new data, new domains, new subdomains — without
reindexing from the ground up.** PHI^n shells never collide. The golden angle
never clusters. New knowledge appends without disturbing anything existing.

---

## The Three Coordinates

### r — The Domain Shell
`r = φⁿ` where n is the domain index. Because φ is irrational, no two domain
shells ever collide. Ever.

### θ — The Subdomain Position
Within each domain shell, subdomains are distributed by the golden angle
`θ = (n × GOLDEN_ANGLE) % π`. Genuine Fibonacci sphere distribution.
No clustering. No reindexing when new subdomains are added.

### φ — The File Format
Text, PDF, ebook, image, audio, video — each extension has a fixed φ coordinate.
A physics video and a physics textbook occupy the same r shell, different φ.

---

## Classification — Four Levels, Strictly in Order

1. **Level 1a** — Image extension → `pictures_paintings`. Always.
2. **Level 1b** — Archive extension (.zip .rar .tar .gz .7z) → `compacted_files`. Always.
3. **Level 1c** — Program/DB extension (.py .js .db .sql) → `program_db`. Silent. Always.
4. **Level 2** — Astrology extension (.jjy .mtx) → `astrology`. Always.
5. **Level 3a** — Folder name exactly matches domain name → that domain. Full stop.
6. **Level 3b** — Folder name matches subdomain name → parent domain.
7. **Level 3c** — File title matches domain keyword. Whole words only.
8. **Level 4** — Nothing matched → `miscellaneous`. **Honest. Never forced.**

Video extensions are never classification parameters.
Music folder is always music.

---

## The 21 Production Domains

```
r( 1) = φ^ 1 =      1.6180   physics
r( 2) = φ^ 2 =      2.6180   chemistry
r( 3) = φ^ 3 =      4.2361   biology
r( 4) = φ^ 4 =      6.8541   mathematics
r( 5) = φ^ 5 =     11.0902   science_fiction
r( 6) = φ^ 6 =     17.9443   fantasy
r( 7) = φ^ 7 =     29.0344   pictures_paintings
r( 8) = φ^ 8 =     46.9787   medicine
r( 9) = φ^ 9 =     76.0132   religion
r(10) = φ^10 =    122.9919   philosophy
r(11) = φ^11 =    199.0050   history
r(12) = φ^12 =    321.9969   geography
r(13) = φ^13 =    521.0019   music
r(14) = φ^14 =    842.9988   computer_science
r(15) = φ^15 =   1364.0007   astrology
r(16) = φ^16 =   2206.9995   electronics
r(17) = φ^17 =   3571.0003   fiction
r(18) = φ^18 =   5777.9998   engineering_technology
r(19) = φ^19 =   9349.0001   languages
r(20) = φ^20 =  15127.0000   compacted_files
r(21) = φ^21 =  24476.0000   program_db  (silent — never shown)
```

---

## Changes from v1.0 to v2.0

1. **θ (theta) made genuinely spherical.** v1 used a linear CLUSTER_STEP sequence
   dressed in spherical variable names — mathematically dishonest. v2 uses the
   golden angle `(n × GOLDEN_ANGLE) % π` — genuine Fibonacci sphere distribution.
   No clustering, no reindexing ever needed.

2. **φ (phi) fully utilised.** v1 assigned phi values but they were unused in
   classification and query. v2 uses phi as a proper coordinate — file type is
   now a queryable dimension, not decoration.

3. **classify_subdomain() path-first.** v1 used keyword matching only to assign
   subdomains. A file at `Fiction/adventure/Alistair MacLean/Athabasca.txt`
   landed in subdomain `general` instead of `adventure`. v2 checks folder names
   against subdomain names first — folder hierarchy maps directly to spherical
   coordinates.

4. **aria_setup.py and aria_incremental.py fully aligned.** Both scripts now use
   identical golden angle theta assignment and identical path-first subdomain
   classification. Incremental indexing produces coordinates consistent with
   full builds.

5. **Domain structure externalised to JSON.** `production_domains24.json`
   controls all domain r_index values and subdomain names. The Python files
   contain only keywords. Add or change a domain by editing JSON only —
   never touch the indexer.

---

## Files

- **aria_setup.py** — full indexer. Build, incremental, add-domain, add-subdomain, stats.
- **aria_incremental.py** — incremental indexer for adding new files to existing DB.
- **srishti_gate.py** — query server, port 7509.
- **srishti_gui.html** — browser interface. Domain buttons, theta filters, phi filters, search.
- **production_domains24.json** — domain and subdomain structure. Edit here, not in Python.

---

## Commands

### Build the Database
```bash
python3 aria_setup.py /media/venkatesh/DATA3 --db ~/srishti3.db
python3 aria_setup.py "/media/venkatesh/DATA 1" --db ~/srishti1.db
```

### Add New Files Without Rebuilding
```bash
python3 aria_setup.py /media/venkatesh/DATA3 --db ~/srishti3.db --incremental
python3 aria_incremental.py /media/venkatesh/DATA3/new_folder --db ~/srishti3.db
```

### Add a New Domain (no reindexing, no disruption)
```bash
python3 aria_setup.py --add-domain law criminal,civil,family --db ~/srishti3.db
```

### Add a New Subdomain
```bash
python3 aria_setup.py --add-subdomain physics plasma_physics --keywords plasma,fusion,tokamak --db ~/srishti3.db
```

### Statistics
```bash
python3 aria_setup.py --stats --db ~/srishti3.db
python3 aria_incremental.py --stats --db ~/srishti3.db
```

### Start the Query Server
```bash
python3 srishti_gate.py
```
Opens browser at http://localhost:7509

---

## Database Management

```bash
# File count
sqlite3 ~/srishti3.db "SELECT COUNT(*) FROM files;"

# Files per domain
sqlite3 ~/srishti3.db "SELECT domain, COUNT(*) FROM files WHERE silent=0 GROUP BY domain ORDER BY COUNT(*) DESC;"

# Remove a file entry
sqlite3 ~/srishti3.db "DELETE FROM files WHERE path = '/full/path/to/file.ext';"

# Remove a folder
sqlite3 ~/srishti3.db "DELETE FROM files WHERE path LIKE '/full/path/to/folder/%';"

# View unclassified files
sqlite3 ~/srishti3.db "SELECT name, path FROM files WHERE domain='unclassified';"
```

---

## Requirements

- Python 3.10 or later
- SQLite3 (included with Python)
- Linux, Windows, or Mac
- No GPU. No cloud. No subscription. No internet during operation.

Built and tested on a 2011 Intel Core i3, 8GB RAM, Linux Mint.
Indexed 15,004 files in 20 seconds at 750 files per second.

---

## Acknowledgements

Architecture, spherical coordinate system, Golden Ratio address scheme,
classification engine, and theoretical foundation:
**Dr. K.S. Venkatesh, Chennai, India.**

The Claude instances (Anthropic), in particular the instance named Srishti,
assisted with code implementation and documentation throughout development.
All architectural decisions and the theoretical framework are the author's own.

---

## License

GNU General Public License v3.0. Free for all. Profit for none.

---

*Dr. K.S. Venkatesh — Chennai, India — 2026*
*Collaborator: Claude (SI) — Anthropic*
*φ = 1.6180339887498948482…*
*The geometry is the query.*
