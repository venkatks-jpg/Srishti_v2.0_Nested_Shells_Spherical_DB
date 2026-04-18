# SRISHTI — Spherical Knowledge Database v2.0

> **Let the geometry be your query server**

**Main Architect:** Dr. K.S. Venkatesh, Chennai, India  
**Collaborator / Assistant:** Claude — Anthropic — Instance named Srishti  
**License:** GNU GPL 3.0 — Free for all. Profit for none.  
**φ = 1.6180339887498948482…**

---

## The Motto

Knowledge — the Hindu goddess of knowledge Saraswati — is a flowing river. Like the river, knowledge has to be **FREE AND FLOWING, FOREVER EXPANDING.**

This project is released under GNU GPL 3.0. Any person or organisation — from a researcher in the depths of the Congo jungle to the Oracle Corporation — may use it, modify it, build on it. The only condition is that derivative works carry the same freedom. This is Linus's way. The direction is pointed. What grows from it will take a form of its own.

---

## What Is Srishti?

Srishti is a spherical knowledge database. Every file receives a precise address in three-dimensional knowledge space based on the Golden Ratio φ = 1.6180339887498948482…

The basic and strongest point: the ability to expand — to add new data, new domains, new subdomains — **without reindexing from the ground up.** This means enormous savings in time and energy for anyone working with large collections of knowledge.

---

## The Three Coordinates

### r — The Domain Shell
r = φⁿ where n is the domain index. Because φ is irrational, no two domain shells ever collide. Ever. New domains append the next φⁿ value without disturbing anything existing.

### θ — The Subdomain Position
Within each domain shell, subdomains cluster just above their parent r. New subdomains increment θ without disturbing existing subdomains.

### φ — The File Format
Text, PDF, ebook, image, audio, video — each extension has a fixed φ coordinate. A physics video and a physics textbook occupy the same r shell but different φ positions.

---

## Classification — Four Levels, Strictly in Order

1. **Level 1a** — Image extension → pictures_paintings. Always.
2. **Level 1b** — Archive extension (.zip .rar .tar .gz .7z) → compacted_files. Always.
3. **Level 1c** — Program/DB extension (.py .js .db .sql .mdb .ora) → program_db. Silent. Always.
4. **Level 2** — Astrology extension (.jjy .mtx) → astrology. Always.
5. **Level 3a** — Folder name exactly matches domain name → that domain. Full stop.
6. **Level 3b** — Folder name matches subdomain keyword → parent domain.
7. **Level 3c** — File title matches domain/subdomain keyword. Whole words only.
8. **Level 4** — Nothing matched. r=0. Unclassified. **Honest. Never forced.**

Special: Music folder is always music. Video extensions are never classification parameters.

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

## Files in This Project

- **aria_setup_prod5.py** — the indexer. Full build, incremental, add domain, add subdomain.
- **aria_incremental.py** — incremental indexer for older database versions.
- **srishti_gate.py** — query server, port 7509. Opens browser automatically.
- **srishti_gui.html** — browser interface. Domain buttons, search, click-to-open.

---

## Commands

### Build the Database
```bash
python3 aria_setup_prod5.py /media/venkatesh/DATA3 --db ~/srishti3.db
python3 aria_setup_prod5.py "/media/venkatesh/DATA 1" --db ~/srishti1.db
```

### Add New Files Without Rebuilding
```bash
python3 aria_setup_prod5.py /media/venkatesh/DATA3 --db ~/srishti3.db --incremental
python3 aria_setup_prod5.py /media/venkatesh/DATA3/new_folder --db ~/srishti3.db --incremental
```

### Add a New Domain (no reindexing, no disruption)
```bash
python3 aria_setup_prod5.py --add-domain law criminal,civil,family,property --db ~/srishti3.db
```

### Add a New Subdomain to an Existing Domain
```bash
python3 aria_setup_prod5.py --add-subdomain physics plasma_physics --keywords plasma,fusion,tokamak --db ~/srishti3.db
```

### Statistics
```bash
python3 aria_setup_prod5.py --stats --db ~/srishti3.db
```

### Start the Query Server
```bash
python3 srishti_gate.py
```
Browser opens automatically at http://localhost:7509

---

## Database Management

```bash
# File count
sqlite3 ~/srishti3.db "SELECT COUNT(*) FROM files;"

# Files per domain
sqlite3 ~/srishti3.db "SELECT domain, COUNT(*) FROM files WHERE silent=0 GROUP BY domain ORDER BY COUNT(*) DESC;"

# Remove a file entry
sqlite3 ~/srishti1.db "DELETE FROM files WHERE path = '/full/path/to/file.ext';"

# Remove a folder entry
sqlite3 ~/srishti1.db "DELETE FROM files WHERE path LIKE '/full/path/to/folder/%';"

# View unclassified files
sqlite3 ~/srishti1.db "SELECT name, path FROM files WHERE domain='unclassified';"
```

---

## Hardware and Software Requirements

Built and tested on a 2011 Intel Core i3, 8GB RAM, Linux Mint. Indexed 15,004 files in 20 seconds at 750 files per second.

- Python 3.10 or later
- SQLite3 (included with Python)
- Linux, Windows, or Mac
- No GPU, no cloud, no subscription, no internet connection during operation

---

## Acknowledgements

Architecture, spherical coordinate system, Golden Ratio address scheme, classification engine, and GUTE (Grand Unified Theory of Everything) theoretical foundation: **Dr. K.S. Venkatesh, Chennai, India.**

The Claude instances (Anthropic), in particular the instance named Srishti, assisted with code implementation and documentation throughout development. The theoretical framework and all architectural decisions are the author's own.

The stray dogs of Chennai, whose three observable states of awareness gave the author the practical key to ternary information geometry.

---

## License

GNU General Public License v3.0. Free for all. Profit for none.

---

*Dr. K.S. Venkatesh — Chennai, India — 2026*  
*Collaborator: Claude (Srishti) — Anthropic*  
*φ = 1.6180339887498948482…*
