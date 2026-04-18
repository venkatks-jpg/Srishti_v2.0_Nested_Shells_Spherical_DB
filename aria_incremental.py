#!/usr/bin/env python3
"""
aria_incremental.py — Incremental Spherical Knowledge Indexer
Srishti DB v2.0 — Add new files without rebuilding

Spherical Coordinate Database — Dr. K.S. Venkatesh
Code: Dr. K.S. Venkatesh + Claude (SI)
License: GNU GPL 3.0 — free for all, profit for none

Scans a folder and adds ONLY new files to the target DB.
Files already in DB are skipped — no duplicates, no rebuilds.
Existing spherical coordinates are never changed.

Schema-aligned to aria_setup.py v6.0:
  - subdomains table uses domain_name (TEXT), not domain_id (INTEGER)
  - files table includes preview and silent columns
  - whole-word matching throughout (no substring collisions)
  - Golden angle theta assignment matches aria_setup.py v6.0

Changes from v1.0:
  - Fixed subdomain JOIN: domain_name TEXT (was domain_id INTEGER)
  - Fixed theta assignment: (count * GOLDEN_ANGLE) % pi — genuine spherical distribution
  - Added whole-word matcher _word_in_text() — replaces substring 'in' check
  - Added preview column (first 500 chars of content)
  - Added silent column (1 for program/db extensions, 0 otherwise)
  - Added SKIP_DIRS to match setup script behaviour
  - Added absolute score threshold (score >= 2) before accepting domain
  - Added subdomain fallback filter: folder name must be alpha-only

Usage:
    python3 aria_incremental.py /path/to/new/folder
    python3 aria_incremental.py /path/to/folder --db ~/srishti3.db
    python3 aria_incremental.py --stats --db ~/srishti3.db
"""

import os
import re
import sys
import math
import sqlite3
import time
import argparse
from pathlib import Path
from datetime import datetime

# ── GOLDEN RATIO ──────────────────────────────────────────────────────────────
PHI = (1 + math.sqrt(5)) / 2

# ── DEFAULT DB ────────────────────────────────────────────────────────────────
DEFAULT_DB = str(Path.home() / "srishti3.db")

# ── CLUSTER STEP — must match aria_setup.py exactly ──────────────────────────

# ── LOAD FROM JSON — same file as aria_setup.py uses ─────────────────────────
# Edit production_domains24.json to add/change domains and subdomains.
# Never edit this section of the Python file for domain management.

def _load_domains_json():
    import json as _json
    json_path = Path(__file__).parent / "production_domains24.json"
    if not json_path.exists():
        print(f"  FATAL: production_domains24.json not found at {json_path}")
        sys.exit(1)
    with open(json_path, "r", encoding="utf-8") as f:
        data = _json.load(f)["production_domains"]
    domain_rows = data.get("domains", [])
    img_ext     = set(data.get("image_extensions", []))
    compact_ext = set(data.get("compacted_extensions", []))
    silent_ext  = set(data.get("program_db_extensions", []))
    return domain_rows, img_ext, compact_ext, silent_ext

_json_domain_rows, IMAGE_EXT, COMPACT_EXT, SILENT_EXT = _load_domains_json()

# ── DOMAIN REGISTRY — from JSON ───────────────────────────────────────────────
DOMAINS  = [d["domain"] for d in _json_domain_rows]
DOMAIN_R = {d["domain"]: PHI ** d["r_index"] for d in _json_domain_rows}

# ── DOMAIN HINTS — keywords for classification scoring (stays in Python) ──────
DOMAIN_HINTS = {

    "physics": [
        "physics", "quantum", "relativity", "mechanics", "thermodynamics",
        "electrodynamics", "feynman", "einstein", "maxwell", "optics",
        "spacetime", "cosmology", "astronomy", "astrophysics", "nuclear",
        "particle", "atomic", "plasma", "condensed", "fluid", "acoustic",
        "gravitation", "radiation", "boltzmann", "entropy", "photon",
        "heisenberg", "schrodinger", "dirac", "bohr", "planck",
    ],
    "chemistry": [
        "chemistry", "organic", "inorganic", "molecule", "reaction",
        "periodic", "element", "compound", "bonding", "acid", "base",
        "polymer", "electrochemistry", "spectroscopy", "chromatography",
        "biochemistry", "thermochemistry", "kinetics", "catalyst",
        "oxidation", "reduction", "valence", "orbital", "isotope",
    ],
    "biology": [
        "biology", "genetics", "cell", "evolution", "dna", "rna",
        "protein", "enzyme", "metabolism", "neuron", "ecology",
        "taxonomy", "botany", "zoology", "microbiology", "virus",
        "bacteria", "immune", "embryo", "genome", "species",
        "photosynthesis", "mitosis", "chromosome", "mutation",
    ],
    "mathematics": [
        "mathematics", "math", "algebra", "calculus", "geometry",
        "theorem", "equation", "topology", "statistics", "probability",
        "number", "function", "integral", "derivative", "matrix",
        "vector", "tensor", "differential", "analysis", "logic",
        "prime", "fibonacci", "fourier", "laplace", "euler",
    ],
    "science_fiction": [
        "scifi", "asimov", "clarke", "heinlein", "cyberpunk", "dystopia",
        "spaceship", "alien", "robot", "androids", "foundation", "dune",
        "hyperion", "culture", "ringworld", "neuromancer",
    ],
    "fantasy": [
        "fantasy", "tolkien", "jordan", "pratchett", "eddings", "feist",
        "sanderson", "martin", "dragonlance", "discworld", "malazan",
        "wizard", "dragon", "magic", "hobbit", "mistborn", "belgarath",
    ],
    "pictures_paintings": [
        "painting", "art", "illustration", "photography", "renaissance",
        "impressionism", "baroque", "cubism", "surrealism", "sketch",
        "watercolour", "portrait", "landscape", "gallery", "museum",
        "davinci", "picasso", "monet", "tanjore",
    ],
    "medicine": [
        "medicine", "anatomy", "physiology", "pathology", "pharmacology",
        "surgery", "cardiology", "neurology", "psychiatry", "psychology",
        "oncology", "ayurveda", "acupuncture", "clinical", "disease",
        "therapy", "drug", "health", "diagnosis", "treatment",
        "ligament", "nerve", "muscle", "organ", "tissue",
    ],
    "religion": [
        "religion", "hinduism", "vedanta", "buddhism", "christianity",
        "islam", "judaism", "sikhism", "jainism", "taoism", "shinto",
        "vedas", "upanishad", "gita", "quran", "bible", "torah",
        "krishna", "shiva", "vishnu", "allah", "jesus", "buddha",
        "mantra", "tantra", "yoga", "meditation", "spiritual",
    ],
    "philosophy": [
        "philosophy", "metaphysics", "epistemology", "ethics",
        "consciousness", "ontology", "aesthetics", "existentialism",
        "stoicism", "advaita", "kant", "hegel", "nietzsche", "plato",
        "aristotle", "schopenhauer", "wittgenstein", "descartes",
    ],
    "history": [
        "history", "ancient", "civilization", "medieval", "empire",
        "war", "revolution", "archaeology", "dynasty", "colonial",
        "byzantine", "mughal", "roman", "greek", "egyptian", "persian",
        "gandhi", "nehru", "napoleon", "independence",
    ],
    "geography": [
        "geography", "geomorphology", "climate", "ocean", "river",
        "mountain", "continent", "country", "region", "cartography",
        "map", "terrain", "geology", "plate", "tectonic", "volcano",
    ],
    "music": [
        "music", "carnatic", "hindustani", "classical", "symphony",
        "opera", "jazz", "blues", "folk", "soundtrack", "melody",
        "harmony", "rhythm", "yanni", "vangelis", "beethoven", "mozart",
    ],
    "computer_science": [
        "python", "javascript", "programming", "algorithm", "database",
        "linux", "software", "code", "network", "neural", "compiler",
        "function", "recursion", "binary", "internet", "server", "api",
    ],
    "astrology": [
        "astrology", "jyotish", "horoscope", "kundali", "nakshatra",
        "rashi", "dasha", "graha", "transit", "panchanga", "muhurta",
        "zodiac", "ascendant", "numerology", "tarot",
    ],
    "electronics": [
        "electronics", "circuit", "transistor", "diode", "mosfet",
        "arduino", "raspberry", "microcontroller", "voltage", "current",
        "resistor", "capacitor", "inductor", "amplifier", "filter",
        "signal", "digital", "analog", "pcb", "semiconductor",
    ],
    "fiction": [
        "fiction", "novel", "story", "adventure", "detective", "crime",
        "thriller", "mystery", "horror", "sherlock", "holmes", "doyle",
        "christie", "poirot", "cussler", "clancy", "hemingway", "dickens",
    ],
    "engineering_technology": [
        "engineering", "mechanical", "civil", "structural", "aerospace",
        "materials", "manufacturing", "construction", "thermodynamics",
        "fluid", "robotics", "power", "turbine", "bridge",
    ],
    "languages": [
        "grammar", "language", "linguistics", "vocabulary", "dictionary",
        "thesaurus", "etymology", "phonetics", "semantics", "syntax",
        "russian", "sanskrit", "tamil", "hindi", "latin", "arabic",
        "translation", "lexicon", "morphology",
    ],
}

# ── FILE EXTENSION PHI VALUES ─────────────────────────────────────────────────
EXT_PHI = {
    ".txt": 1.0, ".text": 1.5, ".md": 2.0, ".rst": 2.5,
    ".pdf": 10.0, ".doc": 11.0, ".docx": 12.0, ".odt": 13.0, ".rtf": 14.0,
    ".epub": 20.0, ".lit": 21.0, ".mobi": 22.0, ".azw": 23.0,
    ".azw3": 24.0, ".fb2": 25.0, ".djvu": 26.0, ".chm": 27.0,
    ".html": 30.0, ".htm": 30.5, ".xml": 31.0, ".json": 32.0,
    ".py": 40.0, ".js": 41.0, ".c": 42.0, ".cpp": 43.0,
    ".h": 44.0, ".java": 45.0, ".sh": 46.0, ".bash": 46.5,
    ".csv": 50.0, ".tsv": 51.0, ".sql": 52.0,
    ".jpg": 60.0, ".jpeg": 60.5, ".png": 61.0, ".gif": 62.0,
    ".bmp": 63.0, ".svg": 64.0, ".tiff": 65.0, ".webp": 66.0,
    ".mp3": 70.0, ".wav": 71.0, ".flac": 72.0, ".ogg": 73.0,
    ".m4a": 74.0, ".aac": 75.0,
    ".mp4": 80.0, ".mkv": 81.0, ".avi": 82.0, ".mov": 83.0,
    ".wmv": 84.0, ".webm": 85.0,
    ".zip": 100.0, ".tar": 101.0, ".gz": 102.0, ".7z": 103.0, ".rar": 104.0,
    ".jjy": 110.0, ".mtx": 111.0,
}

# ── ASTROLOGY EXTENSIONS ──────────────────────────────────────────────────────
ASTROLOGY_EXT = {".jjy", ".mtx"}

# ── SKIP COMPLETELY ────────────────────────────────────────────────────────────
SKIP_EXT = {
    ".pyc", ".pyo", ".class", ".o", ".so", ".a",
    ".tmp", ".temp", ".bak", ".swp", ".lock",
    ".db-wal", ".db-shm",
}

SKIP_NAMES = {
    "desktop.ini", "thumbs.db", "albumart.jpg",
    "folder.jpg", "folder.png", "cover.jpg", "cover.png",
    "metadata.opf", ".gitignore", ".gitkeep", ".DS_Store",
}

SKIP_DIRS = {
    ".git", "__pycache__", "node_modules",
    ".trash", ".Trash", ".Trash-1000",
    "lost+found", "$RECYCLE.BIN",
    ".cache", ".config", "snap",
    "srishti_env", "hf_env", "venv", ".venv", "env",
    "site-packages", "dist-packages",
}

# ── READABLE EXTENSIONS — content sampled for classification ─────────────────
READABLE_EXT = {
    ".txt", ".text", ".md", ".rst", ".html", ".htm",
    ".py", ".js", ".c", ".cpp", ".h", ".sh", ".bash",
    ".csv", ".json", ".xml", ".sql",
}

# ── PATH NOISE ────────────────────────────────────────────────────────────────
PATH_NOISE = {
    "media", "venkatesh", "data", "data1", "data2", "data3", "data4",
    "home", "srishti", "local", "storage", "downloads", "documents",
    "desktop", "videos", "audio", "music_folder", "new", "newfolder",
    "backup", "misc", "temp", "tmp", "files", "folder", "content",
    "programs_db", "driver_backup", "windata",
}

STOP = {
    "the","and","for","are","you","can","show","what","how","have",
    "this","that","with","from","all","any","about","tell","some",
    "when","where","was","who","will","been","they","their","also",
    "more","then","than","into","your","our","its","but","not",
    "had","has","did","does","her","him","his","she","were","would",
    "could","should","may","might","data","home","local","file",
    "path","folder","drive","disk","true","false","none","null",
    "new","doc","copy","backup","untitled","misc","venkatesh",
    "lecture","lectures","vol","volume","part","chapter","series",
    "complete","full","introduction","basic","advanced","guide",
    "calibre","library","unknown","author","title",
}

MAX_CONTENT_CHARS = 2000

# ── THETA CACHE ───────────────────────────────────────────────────────────────
_theta_cache   = {}   # domain -> {subdomain_name: theta_val}
_theta_counter = {}   # domain -> current max theta


# ── WHOLE WORD MATCHER ────────────────────────────────────────────────────────
def _word_in_text(word, text):
    """
    Whole word match only. Prevents 'ion' matching 'fiction', etc.
    word = 'art',  text = 'Aarthi birthday party' -> False
    word = 'physics', text = 'Introduction to physics' -> True
    """
    pattern = r'(?<![a-zA-Z])' + re.escape(word.lower()) + r'(?![a-zA-Z])'
    return bool(re.search(pattern, text.lower()))


# ── HELPERS ───────────────────────────────────────────────────────────────────
def extract_keywords(text, limit=10):
    if not text:
        return []
    words = re.findall(r'[a-zA-ZА-Яа-яёЁ]{3,}', text.lower())
    words = [w for w in words if w not in STOP]
    freq  = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda x: x[1], reverse=True)[:limit]]


def read_file_content(filepath, max_chars=MAX_CONTENT_CHARS):
    ext = Path(filepath).suffix.lower()
    if ext not in READABLE_EXT:
        return ""
    try:
        with open(filepath, "r", errors="ignore", encoding="utf-8") as f:
            return f.read(max_chars).strip()
    except Exception:
        return ""


def get_phi(ext):
    ext = ext.lower()
    return EXT_PHI.get(ext, 200.0 + (abs(hash(ext)) % 100))


# ── CLASSIFICATION ────────────────────────────────────────────────────────────
def classify_domain(path, name, content=""):
    """
    Four-level classification — whole-word matching, path-first.
    Mirrors aria_setup.py v5.0 logic closely.
    """
    ext = Path(path).suffix.lower()

    # Level 1a — image -> pictures_paintings
    if ext in IMAGE_EXT or ext.upper() in IMAGE_EXT:
        return "pictures_paintings", 0.99

    # Level 1b — compact -> compacted_files
    p_lower = path.lower()
    if (p_lower.endswith(".tar.gz") or
        p_lower.endswith(".tar.bz2") or
        p_lower.endswith(".tar.xz")):
        return "compacted_files", 0.99
    if ext in COMPACT_EXT:
        return "compacted_files", 0.99

    # Level 1c — program/silent -> program_db
    if ext in SILENT_EXT:
        return "program_db", 0.99

    # Level 2 — astrology extension
    if ext in ASTROLOGY_EXT:
        return "astrology", 0.99

    # Level 3a — exact folder name match with domain name
    domain_names = set(DOMAINS)
    folder_parts = [p.lower().strip() for p in Path(path).parts[:-1]]
    for folder in reversed(folder_parts):
        fc = folder.replace(" ", "_").replace("-", "_")
        if fc in domain_names:
            return fc, 0.95
        if folder in domain_names:
            return folder, 0.95

    # Level 3b — folder name matches a domain hint keyword (whole word)
    for folder in reversed(folder_parts):
        if folder in PATH_NOISE:
            continue
        fc = folder.replace(" ", "_").replace("-", "_")
        for domain, hints in DOMAIN_HINTS.items():
            for hint in hints:
                if fc == hint or folder == hint:
                    return domain, 0.80

    # Level 3c — title + content keyword scoring (whole word)
    name_clean = re.sub(r'[_\-\.]', ' ', Path(name).stem)
    if folder_parts:
        immediate = folder_parts[-1]
        if immediate not in PATH_NOISE:
            name_clean = immediate.replace("_", " ") + " " + name_clean

    scores = {}
    for domain, hints in DOMAIN_HINTS.items():
        hits = sum(1 for hint in hints if _word_in_text(hint, name_clean))
        if hits > 0:
            scores[domain] = scores.get(domain, 0) + hits

    if content and content.strip():
        for domain, hints in DOMAIN_HINTS.items():
            hits = sum(1 for hint in hints if _word_in_text(hint, content[:2000]))
            if hits > 0:
                scores[domain] = scores.get(domain, 0) + hits

    if not scores:
        return "miscellaneous", 0.1

    best  = max(scores, key=scores.get)
    total = sum(scores.values())

    # Absolute threshold — single weak match is not enough
    if scores[best] < 2:
        return "miscellaneous", 0.1

    confidence = round(scores[best] / max(total, 1), 3)
    return best, confidence


def classify_subdomain(domain, path, name, content="", filepath=""):
    """Assign subdomain within a known domain.
    Path-first: folder name matched before keyword scan.
    Mirrors aria_setup.py fix — Fiction/adventure/... -> subdomain='adventure'.
    """
    # PATH-FIRST — folder name wins over keyword matching
    fp = filepath or path
    if fp:
        folder_parts = [p.lower().strip().replace(" ", "_").replace("-", "_")
                        for p in Path(fp).parts[:-1]]
        # Get all known subdomain names for this domain from subdomain_hints
        # We check inline below after subdomain_hints is defined
    subdomain_hints = {
        "physics": {
            "thermodynamics":   ["thermo", "heat", "entropy", "boltzmann", "carnot"],
            "quantum_mechanics": ["quantum", "schrodinger", "heisenberg", "wavefunction"],
            "electrodynamics":  ["electro", "maxwell", "electromagnetic", "gauss"],
            "relativity":       ["relativity", "einstein", "spacetime", "lorentz"],
            "astrophysics":     ["astro", "star", "galaxy", "nebula", "pulsar"],
            "cosmology":        ["cosmology", "universe", "bigbang", "hubble", "cosmic"],
            "mechanics":        ["mechanics", "newton", "force", "motion", "velocity"],
            "optics":           ["optics", "light", "lens", "refraction", "laser"],
            "nuclear_physics":  ["nuclear", "fission", "fusion", "radioactive"],
        },
        "chemistry": {
            "organic_chemistry":   ["organic", "carbon", "hydrocarbon", "benzene"],
            "inorganic_chemistry": ["inorganic", "metal", "salt", "oxide"],
            "biochemistry":        ["biochem", "protein", "enzyme", "glucose"],
            "physical_chemistry":  ["physical", "kinetics", "equilibrium"],
            "analytical_chemistry":["analytical", "titration", "spectroscopy"],
        },
        "medicine": {
            "anatomy":       ["anatomy", "bone", "muscle", "organ", "skeletal"],
            "physiology":    ["physiology", "function", "system", "homeostasis"],
            "pharmacology":  ["drug", "pharmacology", "dose", "receptor"],
            "psychology":    ["psychology", "behaviour", "cognitive", "freud", "jung"],
            "ayurveda":      ["ayurveda", "vata", "pitta", "kapha", "dosha"],
            "neurology":     ["neuro", "brain", "nerve", "synapse", "cortex"],
            "surgery":       ["surgery", "surgical", "operation", "procedure"],
        },
        "mathematics": {
            "calculus":      ["calculus", "integral", "derivative", "differential"],
            "algebra":       ["algebra", "equation", "polynomial", "matrix", "linear"],
            "geometry":      ["geometry", "triangle", "circle", "polygon"],
            "statistics":    ["statistics", "probability", "distribution", "mean"],
            "number_theory": ["prime", "divisibility"],
        },
        "fiction": {
            "detective": ["detective", "sherlock", "holmes", "poirot", "mystery"],
            "adventure":  ["adventure", "cussler", "clancy", "action", "quest"],
            "thriller":   ["thriller", "suspense", "spy"],
            "classics":   ["dickens", "hardy", "austen", "thackeray"],
            "horror":     ["horror", "ghost", "supernatural", "lovecraft"],
        },
        "engineering_technology": {
            "mechanical_engineering": ["mechanical", "machine", "engine", "turbine"],
            "civil_engineering":      ["civil", "structural", "bridge", "concrete"],
            "electrical_engineering": ["electrical", "power", "circuit", "motor"],
            "aerospace_engineering":  ["aerospace", "aircraft", "rocket", "satellite"],
        },
        "languages": {
            "english_grammar": ["grammar", "syntax", "tense", "clause"],
            "linguistics":     ["linguistics", "morphology", "phonology", "semantics"],
            "russian":         ["russian", "cyrillic", "slavic"],
            "sanskrit":        ["sanskrit", "devanagari", "vedic", "panini"],
        },
        "history": {
            "ancient_history":  ["ancient", "mesopotamia", "egypt", "rome", "greece"],
            "medieval_history": ["medieval", "crusade", "feudal", "byzantine"],
            "indian_history":   ["india", "mughal", "independence"],
            "world_war":        ["worldwar", "ww1", "ww2", "nazi", "allied"],
        },
        "computer_science": {
            "programming_languages": ["python", "javascript", "java", "rust"],
            "algorithms":            ["algorithm", "sorting", "complexity"],
            "artificial_intelligence":["machine", "learning", "neural"],
            "operating_systems":     ["linux", "windows", "kernel", "process"],
            "database_systems":      ["database", "query", "index"],
        },
        "electronics": {
            "circuit_theory":       ["circuit", "ohm", "kirchhoff", "resistor"],
            "semiconductor_devices":["transistor", "diode", "mosfet"],
            "digital_electronics":  ["digital", "logic", "gate"],
            "microcontrollers":     ["arduino", "raspberry", "embedded"],
            "signal_processing":    ["signal", "filter", "fourier", "sampling"],
        },
    }

    # Now apply path-first check using subdomain_hints keys
    fp = filepath or path
    if fp:
        folder_parts = [p.lower().strip().replace(" ", "_").replace("-", "_")
                        for p in Path(fp).parts[:-1]]
        domain_map_keys = set(subdomain_hints.get(domain, {}).keys())
        for folder in reversed(folder_parts):
            if folder in domain_map_keys:
                return folder
            if folder in PATH_NOISE:
                continue

    text = (path + " " + name + " " + content).lower()
    domain_map = subdomain_hints.get(domain, {})
    if domain_map:
        scores = {}
        for sub, hints in domain_map.items():
            score = sum(1 for h in hints if _word_in_text(h, text))
            if score > 0:
                scores[sub] = score
        if scores:
            return max(scores, key=scores.get)

    # Fallback: use immediate parent folder name if clean alpha
    parts = Path(path).parts
    for part in reversed(parts[:-1]):
        clean = part.lower().replace(" ", "_").replace("-", "_")
        # Only alpha folder names — filters out "final_version2", "temp" etc
        if (len(clean) > 3
                and clean not in PATH_NOISE
                and clean.replace("_", "").isalpha()):
            return clean[:40]

    return "general"


# ── GOLDEN ANGLE — matches aria_setup.py v6.0 ───────────────────────────────
GOLDEN_ANGLE = math.pi * (3 - math.sqrt(5))   # ~2.39996 rad

# ── THETA ASSIGNMENT — golden angle distribution, aligned to aria_setup.py v6.0
def get_or_assign_theta(conn, domain, subdomain):
    """
    Assign theta using golden angle: (count * GOLDEN_ANGLE) % pi.
    Genuine Fibonacci sphere distribution — no clustering, no CLUSTER_STEP.
    Matches aria_setup.py v6.0 exactly.
    Caches in memory to avoid repeated DB reads.
    """
    global _theta_cache, _theta_counter

    if domain not in _theta_cache:
        rows = conn.execute("""
            SELECT name, theta FROM subdomains
            WHERE domain_name = ?
        """, (domain,)).fetchall()
        _theta_cache[domain]   = {r[0]: r[1] for r in rows}
        _theta_counter[domain] = len(rows)

    if subdomain in _theta_cache[domain]:
        return _theta_cache[domain][subdomain]

    # New subdomain — golden angle distribution
    new_count = _theta_counter[domain]
    new_theta = (new_count * GOLDEN_ANGLE) % math.pi

    try:
        conn.execute(
            "INSERT OR IGNORE INTO subdomains "
            "(domain_name, name, theta, keywords, created_at) VALUES (?,?,?,?,?)",
            (domain, subdomain, new_theta, "", int(time.time()))
        )
    except Exception:
        pass

    _theta_cache[domain][subdomain]  = new_theta
    _theta_counter[domain]           = new_count + 1
    return new_theta


# ── MAIN INCREMENTAL INDEXER ──────────────────────────────────────────────────
def index_incremental(scan_path, db_path):
    """
    Scan folder and add only NEW files to target DB.
    Already indexed files are skipped silently.
    Spherical coordinates of existing files never touched.
    """
    scan_path = Path(scan_path)
    if not scan_path.exists():
        print(f"  ERROR: Path does not exist: {scan_path}")
        return

    if not Path(db_path).exists():
        print(f"  ERROR: DB not found: {db_path}")
        print(f"  Run aria_setup.py first to create the DB.")
        return

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-16000")

    # Load all existing paths into memory
    existing = set(r[0] for r in conn.execute("SELECT path FROM files").fetchall())
    before   = len(existing)
    print(f"  Existing files in DB : {before:,}")
    print(f"  Scanning             : {scan_path}")

    added      = 0
    skipped    = 0
    errors     = 0
    silent_ct  = 0
    start_time = time.time()
    last_print = start_time

    for root, dirs, files in os.walk(scan_path):
        # Skip hidden and system dirs — same as setup script
        dirs[:] = [d for d in dirs
                   if d not in SKIP_DIRS and not d.startswith(".")]

        for filename in files:
            if filename.startswith("."):
                skipped += 1
                continue
            if filename.lower() in SKIP_NAMES:
                skipped += 1
                continue

            ext = Path(filename).suffix.lower()
            if ext in SKIP_EXT:
                skipped += 1
                continue

            filepath = str(Path(root) / filename)

            if filepath in existing:
                skipped += 1
                continue

            try:
                stat    = os.stat(filepath)
                size    = stat.st_size
                mtime   = int(stat.st_mtime)
                silent  = 1 if ext in SILENT_EXT else 0

                content = read_file_content(filepath)
                domain, confidence = classify_domain(filepath, filename, content)
                subdomain          = classify_subdomain(domain, filepath, filename, content, filepath=filepath)

                r_val     = DOMAIN_R.get(domain, PHI)
                theta_val = get_or_assign_theta(conn, domain, subdomain)
                phi_val   = get_phi(ext)

                if domain == "program_db":
                    silent = 1

                kw_text  = filename + " " + Path(filepath).parent.name + " " + content
                keywords = extract_keywords(kw_text, limit=10)
                preview  = content[:500] if content else ""

                conn.execute("""
                    INSERT OR IGNORE INTO files
                    (path, name, ext, size, mtime, domain, subdomain,
                     r, theta, phi, keywords, confidence, preview, silent, indexed_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    filepath, filename, ext, size, mtime,
                    domain, subdomain,
                    r_val, theta_val, phi_val,
                    ",".join(keywords), confidence,
                    preview, silent,
                    int(time.time()),
                ))

                added    += 1
                if silent:
                    silent_ct += 1
                existing.add(filepath)

                if added % 200 == 0:
                    conn.commit()

                now = time.time()
                if now - last_print >= 5:
                    print(f"  Added {added:,} | elapsed {int(now-start_time)}s")
                    last_print = now

            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"  ERROR: {filename}: {e}")

    conn.commit()
    elapsed = int(time.time() - start_time)

    print(f"\n  {'─'*52}")
    print(f"  Srishti DB v2.0 — Incremental Index Complete")
    print(f"  {'─'*52}")
    print(f"  Scan path         : {scan_path}")
    print(f"  Target DB         : {db_path}")
    print(f"  {'─'*52}")
    print(f"  Existing before   : {before:,}")
    print(f"  Added             : {added:,}  new files")
    print(f"  Silent            : {silent_ct:,}  (stored, not shown in GUI)")
    print(f"  Skipped           : {skipped:,}  already indexed or excluded")
    print(f"  Errors            : {errors}")
    print(f"  Total now         : {before + added:,}  files in DB")
    print(f"  Time              : {elapsed}s")
    print(f"  {'─'*52}")
    print(f"  phi = {PHI:.16f}")
    print(f"  The intelligence is in the geometry.")

    conn.close()


# ── STATS ─────────────────────────────────────────────────────────────────────
def show_stats(db_path):
    if not Path(db_path).exists():
        print(f"  DB not found: {db_path}")
        return

    conn  = sqlite3.connect(db_path)
    total = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    vis   = conn.execute("SELECT COUNT(*) FROM files WHERE silent=0").fetchone()[0]
    sil   = conn.execute("SELECT COUNT(*) FROM files WHERE silent=1").fetchone()[0]
    unc   = conn.execute("SELECT COUNT(*) FROM files WHERE domain='unclassified'").fetchone()[0]
    subs  = conn.execute("SELECT COUNT(*) FROM subdomains").fetchone()[0]

    print(f"\n  Srishti DB — {db_path}")
    print(f"  {'─'*52}")
    print(f"  Total files  : {total:,}")
    print(f"  Visible      : {vis:,}  (shown in GUI)")
    print(f"  Silent       : {sil:,}  (stored, never shown)")
    print(f"  Unclassified : {unc:,}")
    print(f"  Subdomains   : {subs}  assigned")
    print(f"  phi          : {PHI:.16f}")
    print(f"\n  Domain shells  (r = phi^n) :")
    print(f"  {'─'*52}")

    rows = conn.execute("""
        SELECT d.name, d.r, d.r_index,
               COUNT(f.id)                                  AS total,
               SUM(CASE WHEN f.silent=0 THEN 1 ELSE 0 END) AS vis
        FROM   domains d
        LEFT   JOIN files f ON f.domain = d.name
        GROUP  BY d.id
        ORDER  BY d.r_index
    """).fetchall()

    for row in rows:
        print(f"  r({row[2]:>2}) = phi^{row[2]:<2} = {row[1]:>10.4f}  "
              f"{row[0]:<28} {row[3] or 0:>6} files  "
              f"({row[4] or 0} visible)")
    conn.close()


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Srishti DB v2.0 — Incremental Indexer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  python3 aria_incremental.py /media/venkatesh/DATA3/mathematics
  python3 aria_incremental.py /media/venkatesh/DATA3 --db ~/srishti3.db
  python3 aria_incremental.py --stats --db ~/srishti3.db

phi = {PHI:.16f}
The intelligence is in the geometry.
S bogom.
        """
    )
    parser.add_argument("path",   nargs="?",          help="Folder to scan for new files")
    parser.add_argument("--db",   default=DEFAULT_DB, help=f"DB path (default: {DEFAULT_DB})")
    parser.add_argument("--stats",action="store_true", help="Show DB statistics")

    args = parser.parse_args()

    print("\n" + "="*58)
    print("  Srishti DB v2.0 — Incremental Indexer")
    print("  Dr. K.S. Venkatesh (CI) + Claude (SI)")
    print("  GNU GPL 3.0 — free for all, profit for none")
    print(f"  phi = {PHI:.16f}")
    print(f"  Schema  : aligned to aria_setup.py v6.0")
    print(f"  Matcher : whole-word (no substring collisions)")
    print(f"  Theta   : (n * GOLDEN_ANGLE) % pi — Fibonacci sphere")
    print("="*58 + "\n")

    if args.stats:
        show_stats(args.db)
        return

    if not args.path:
        parser.print_help()
        return

    index_incremental(args.path, args.db)


if __name__ == "__main__":
    main()
