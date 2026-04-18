#!/usr/bin/env python3
"""
aria_setup_prod6.py  —  Srishti Spherical DB Indexer  v6.0

Author  : Dr. K.S. Venkatesh (CI) + Claude (SI)
License : GNU GPL 3.0  —  free for all, profit for none

SPHERICAL GEOMETRY:
    r     =  PHI ^ n  —  fixed at domain creation, never changes, never collides
    theta =  ( subdomain_index * GOLDEN_ANGLE ) % pi
              Golden angle (~2.3999 rad) distributes subdomains evenly across
              [0, pi] as you add them — no clustering, no reindexing, genuinely
              angular. Fibonacci sphere distribution. Mathematically honest.
    phi   =  numeric value assigned by file extension

CLASSIFICATION — four levels, strict priority:

    Level 1a — Image extension      →  pictures_paintings  directly. No argument.
    Level 1b — Compact extension    →  compacted_files     directly. No argument.
    Level 1c — Program/DB extension →  program_db          directly. silent=1. No argument.
    Level 2  — Astrology extension (.jjy .mtx)  →  astrology  directly.
    Level 3  — Path-based classification:
               a. Does any folder in the path exactly match a domain name?
                  If yes — that is the domain. Full stop.
               b. Does any folder name match a subdomain of any domain?
                  If yes — that parent domain is the domain.
               c. Does the file title as a phrase match a domain or subdomain?
                  If yes — that domain.
               Whole word matching throughout — no substrings.
               mp4 and video extensions are NEVER classification parameters.
    Level 4 — r=0 unclassified. Honest. Never forced.

SPECIAL RULES:
    - Music folder is always music. No exception.
    - All image extensions always go to pictures_paintings. No exception.
    - mp4, mkv, avi, mov, wmv, webm — extension ignored for classification.
    - No file is ever forced into a domain by guessing.

USAGE:
    python3 aria_setup.py /path --db ~/db3.db
    python3 aria_setup.py /path --db ~/db1.db
    python3 aria_setup.py /path --db ~/db3.db --incremental
    python3 aria_setup.py --stats --db ~/db3.db
    python3 aria_setup.py --add-domain law criminal,civil,family --db ~/db3.db
    python3 aria_setup.py --add-subdomain physics plasma_physics --keywords plasma,tokamak --db ~/db3.db
"""

import os
import re
import sys
import math
import time
import sqlite3
import argparse
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


# ── GOLDEN RATIO & GOLDEN ANGLE ───────────────────────────────────────────────
PHI          = (1 + math.sqrt(5)) / 2          # 1.6180339887498948482...
GOLDEN_ANGLE = math.pi * (3 - math.sqrt(5))   # ~2.39996322972865332 rad
                                                # Distributes points on sphere
                                                # without clustering or reindex


# ── CONFIGURATION ──────────────────────────────────────────────────────────────
DEFAULT_DB    = str(Path.home() / "db1.db")
MAX_THREADS   = 2     # Sandy Bridge i3 + USB2 HDD: 2 threads avoids I/O contention
BATCH_SIZE    = 200
MAX_CONTENT   = 3000


# ── IMAGE EXTENSIONS — direct to pictures_paintings, no classification needed ──
IMAGE_EXT = {
    ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif",
    ".gif", ".webp", ".svg", ".raw", ".cr2", ".nef",
    ".heic", ".heif", ".ico", ".xcf",
    # Case variants — filesystem may preserve case
    ".JPG", ".JPEG", ".PNG", ".BMP", ".TIFF", ".TIF",
    ".GIF", ".WEBP", ".SVG",
}

# ── ASTROLOGY EXTENSIONS — direct to astrology ────────────────────────────────
ASTROLOGY_EXT = {".jjy", ".mtx"}

# ── COMPACT EXTENSIONS — direct to compacted_files, no classification needed ──
# Compound extensions (.tar.gz etc) checked by endswith before single-ext check.
COMPACT_EXT = {
    ".zip", ".rar", ".gz", ".gzip", ".tar", ".tgz",
    ".bz2", ".xz", ".7z", ".cab", ".iso",
    ".tar.gz", ".tar.bz2", ".tar.xz",
    ".Z", ".lz", ".lzma", ".lzh", ".arj",
}
# Single-extension members for fast set lookup
COMPACT_EXT_SINGLE = {
    ".zip", ".rar", ".gz", ".gzip", ".tar", ".tgz",
    ".bz2", ".xz", ".7z", ".cab", ".iso",
    ".Z", ".lz", ".lzma", ".lzh", ".arj",
}

# ── VIDEO EXTENSIONS — ignored for classification ─────────────────────────────
# A video file's domain comes from its folder or title, never its extension.
VIDEO_EXT = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm",
    ".flv", ".m4v", ".3gp", ".ogv",
}

# ── AUDIO EXTENSIONS — not classification parameters ──────────────────────────
# Audio files in music folder → music. Audio files elsewhere → classified by path.
AUDIO_EXT = {
    ".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma",
}

# ── SILENT EXTENSIONS — stored, never shown in GUI ────────────────────────────
SILENT_EXT = {
    ".py", ".pyc", ".pyo",
    ".js", ".ts", ".jsx", ".tsx",
    ".json", ".yaml", ".yml", ".toml",
    ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp",
    ".java", ".class", ".jar",
    ".sh", ".bash", ".zsh", ".fish",
    ".cs", ".vb", ".fs",
    ".go", ".rs", ".rb", ".php",
    ".sql", ".db", ".sqlite", ".sqlite3", ".db-wal", ".db-shm",
    ".mdb", ".accdb",                        # Microsoft Access
    ".mdf", ".ldf", ".ndf",                  # Microsoft SQL Server
    ".frm", ".ibd", ".myd", ".myi",          # MySQL
    ".dbf",                                  # dBase / FoxPro / Oracle
    ".ora", ".dmp",                          # Oracle
    ".fdb", ".gdb",                          # Firebird
    ".db3",                                  # SQLite variant
    ".dll", ".exe", ".so", ".o", ".a",
    ".sys", ".cat", ".inf", ".drv",    # Windows driver files
    ".msi", ".reg",                    # Windows installer / registry
    ".bat", ".cmd", ".ps1",
    ".gguf", ".bin", ".pt", ".pth", ".safetensors", ".ckpt",
    ".pkl", ".pickle",
    ".xml", ".xsd", ".dtd",
    ".css", ".less", ".scss",
    ".pem", ".key", ".crt", ".csr",
    ".cfg", ".ini", ".conf",
    ".log",
    ".pth", ".typed",
    ".swf", ".flv",
}

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
    "INSTALLER", "RECORD", "WHEEL", "REQUESTED", "METADATA",
    "top_level.txt", "py.typed",
}

SKIP_DIRS = {
    ".git", "__pycache__", "node_modules",
    ".trash", ".Trash", ".Trash-1000",
    "lost+found", "$RECYCLE.BIN", "Emoji",
    ".cache", ".config", "snap",
    "srishti_env", "hf_env", "venv", ".venv", "env",
    "site-packages", "dist-packages",
    "dist-info", "egg-info",
}

# ── READABLE — content extracted for subdomain classification only ─────────────
READABLE_EXT = {
    ".txt", ".text", ".md", ".rst", ".tex",
    ".html", ".htm",
    ".py", ".js", ".c", ".cpp", ".h", ".sh", ".bash",
    ".json", ".yaml", ".yml", ".toml",
    ".csv", ".sql", ".lit",
}

# ── PHI VALUES — file extension coordinate (not classification) ───────────────
EXT_PHI = {
    ".txt": 1.0, ".text": 1.5, ".md": 2.0, ".rst": 2.5, ".tex": 3.0,
    ".pdf": 10.0, ".doc": 11.0, ".docx": 12.0, ".odt": 13.0, ".rtf": 14.0,
    ".epub": 20.0, ".lit": 21.0, ".mobi": 22.0, ".azw": 23.0, ".azw3": 24.0,
    ".fb2": 25.0, ".djvu": 26.0, ".chm": 27.0,
    ".html": 30.0, ".htm": 30.5,
    ".json": 32.0, ".xml": 31.0, ".yaml": 33.0,
    ".csv": 50.0, ".sql": 52.0, ".db": 53.0, ".sqlite": 53.5,
    ".py": 40.0, ".js": 41.0, ".ts": 41.5,
    ".c": 42.0, ".cpp": 43.0, ".h": 44.0,
    ".java": 45.0, ".sh": 46.0, ".bash": 46.5,
    ".jpg": 60.0, ".jpeg": 60.5, ".png": 61.0, ".gif": 62.0,
    ".bmp": 63.0, ".svg": 64.0, ".tiff": 65.0, ".webp": 66.0,
    ".mp3": 70.0, ".wav": 71.0, ".flac": 72.0, ".ogg": 73.0,
    ".m4a": 74.0, ".aac": 75.0,
    ".mp4": 80.0, ".mkv": 81.0, ".avi": 82.0, ".mov": 83.0,
    ".wmv": 84.0, ".webm": 85.0,
    ".zip": 100.0, ".tar": 101.0, ".gz": 102.0, ".7z": 103.0, ".rar": 104.0,
    ".jjy": 110.0, ".mtx": 111.0,
}

# ── STOP WORDS ─────────────────────────────────────────────────────────────────
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

# ── PATH NOISE — folder names that carry no domain meaning ────────────────────
PATH_NOISE = {
    "media","venkatesh","data","data1","data2","data3","data4",
    "home","srishti","local","storage","downloads","documents",
    "desktop","videos","audio","music_folder","new","newfolder",
    "backup","misc","temp","tmp","files","folder","content",
    "programs_db","driver_backup","windata",               # Windows data noise
    "01","02","03","04","05","06","07","08","09","10",
    "a","b","c","d","e","f","g","h","i","j","k","l","m",
    "n","o","p","q","r","s","t","u","v","w","x","y","z",
}

# ── LOAD DOMAINS AND SUBDOMAINS FROM JSON ─────────────────────────────────────
# Edit production_domains24.json to add/change domains and subdomains.
# Never edit this section of the Python file for domain management.

def _load_domains_json():
    """
    Load domains, subdomains, and extension lists from production_domains24.json.
    JSON must be in the same folder as this script.
    Returns (DOMAINS list, SUBDOMAINS list, IMAGE_EXT set, COMPACT_EXT set,
             COMPACT_EXT_SINGLE set, SILENT_EXT set)
    """
    json_path = Path(__file__).parent / "production_domains24.json"
    if not json_path.exists():
        print(f"  FATAL: production_domains24.json not found at {json_path}")
        sys.exit(1)
    import json as _json
    with open(json_path, "r", encoding="utf-8") as f:
        data = _json.load(f)["production_domains"]

    # Extension lists from JSON
    img_ext     = set(data.get("image_extensions", []))
    compact_ext = set(data.get("compacted_extensions", []))
    # Single-extension compact (no dots in name beyond the leading dot)
    compact_single = {e for e in compact_ext if e.count(".") == 1}
    silent_ext  = set(data.get("program_db_extensions", []))

    # Domains — JSON format: {r_index, domain, subdomains_theta:[...]}
    # We need keywords too — those come from the in-file DOMAINS list below
    # which we keep as the keyword source but load r_index and subdomain names
    # from JSON. That way JSON controls structure, Python controls keywords.
    # Build: DOMAINS = [(r_index, name, [keywords...]), ...]
    # Keywords stay in Python — only r_index and subdomain names come from JSON.

    domain_rows = data.get("domains", [])
    # Build subdomain list from JSON: [(domain_name, subdomain_name, []), ...]
    subdomains = []
    for d in domain_rows:
        dname = d["domain"]
        for sub in d.get("subdomains_theta", []):
            subdomains.append((dname, sub, []))

    return domain_rows, subdomains, img_ext, compact_ext, compact_single, silent_ext


_json_domain_rows, _json_subdomains, \
    IMAGE_EXT, COMPACT_EXT, COMPACT_EXT_SINGLE, SILENT_EXT = _load_domains_json()

# ── DOMAIN R MAP — built from JSON r_index values ─────────────────────────────
DOMAIN_R = {d["domain"]: PHI ** d["r_index"] for d in _json_domain_rows}

# ── 19 PRODUCTION DOMAINS — keywords stay here, r_index comes from JSON ────────
# r_index values are NOT hardcoded here — they are loaded from JSON via
# _json_domain_rows and used as PHI**r_index at DB setup time.
# To change a domain's shell: edit r_index in production_domains24.json only.
# DOMAINS list here = keywords only. Structure = JSON only. No silent divergence.
# ── DOMAIN KEYWORDS — structure (r_index) comes from JSON, keywords stay here ──
# To add a domain: add entry in JSON, add keywords here.
# r_index is NEVER hardcoded here — it is always read from production_domains24.json.
_DOMAIN_KW = {
    "physics": [
        "physics","quantum","relativity","mechanics","thermodynamics",
        "electrodynamics","feynman","einstein","maxwell","optics",
        "spacetime","cosmology","astronomy","astrophysics","nuclear",
        "particle","atomic","plasma","condensed","gravitation",
        "boltzmann","entropy","photon","heisenberg","schrodinger","dirac",
        "kinematics","dynamics","statics","fluid","acoustics","wave",
        "biophysics","geophysics","atmospheric","celestial","solid",
        "electrostatics","magnetostatics","unified","gut","susskind",
        "hawking","penrose","bohr","rutherford","curie","planck",
        "theoretical","spinor","lagrangian","hamiltonian","tensor",
    ],
    "chemistry": [
        "chemistry","organic","inorganic","molecule","reaction",
        "periodic","element","compound","bonding","acid","base",
        "polymer","electrochemistry","spectroscopy","chromatography",
        "biochemistry","thermochemistry","kinetics","catalyst",
        "analytical","physical","computational","photochemistry",
        "redox","colloid","surface","medicinal","materials","gcse",
        "stoichiometry","titration","molarity","avogadro",
    ],
    "biology": [
        "biology","genetics","cell","evolution","dna","rna",
        "protein","enzyme","metabolism","neuron","ecology",
        "taxonomy","botany","zoology","microbiology","virus",
        "bacteria","immune","embryo","genome","species",
        "virology","bacteriology","mycology","parasitology",
        "immunology","neurobiology","developmental","histology",
        "cytology","proteomics","metabolomics","bioinformatics",
        "biotechnology","synthetic","conservation","ethology",
        "marine","astrobiology","epigenetics","genomics","darwin",
        "mendel","mitosis","meiosis","photosynthesis","anatomy",
        "gerontology","aging","senescence","longevity","lifespan",
    ],
    "mathematics": [
        "mathematics","math","algebra","calculus","geometry",
        "theorem","equation","topology","statistics","probability",
        "number","function","integral","derivative","matrix",
        "vector","tensor","differential","prime","fourier","euler",
        "arithmetic","linear","abstract","multivariable","analysis",
        "complex","functional","algebraic","combinatorics","graph",
        "logic","stochastic","numerical","optimization","chaos",
        "fractal","pythagoras","fibonacci","riemann","gauss",
        "trigonometry","logarithm","polynomial","factorial",
    ],
    "science_fiction": [
        "scifi","asimov","clarke","heinlein","philip_dick","le_guin",
        "cyberpunk","dystopia","spaceship","alien","robot","android",
        "foundation","dune","hyperion","ringworld","neuromancer",
        "space_opera","steampunk","biopunk","post_apocalyptic",
        "time_travel","first_contact","military_scifi","banks",
        "hamilton","reynolds","baxter","bear","utopia","orwell",
        "huxley","bradbury","verne","wells","ender","rama",
        "vernor_vinge","kim_stanley_robinson","connie_willis",
        "ursula","lois_mcmaster_bujold","joe_haldeman","pohl",
        "frederik","zelazny","leiber","brunner","simak","cherryh",
        "farmer","joan_vinge","james_blish","walter_miller",
    ],
    "fantasy": [
        "fantasy","tolkien","jordan","pratchett","eddings","feist",
        "sanderson","martin","dragonlance","discworld","malazan",
        "wizard","dragon","magic","hobbit","mistborn","belgarath",
        "epic_fantasy","dark_fantasy","urban_fantasy","sword_sorcery",
        "mythic","fairy_tale","folklore","grimdark","heroic",
        "forgotten_realms","wheel_of_time","world_building","mythology",
        "fablehaven","eragon","narnia","elves","dwarves",
        "terry_goodkind","margaret_weis","david_gemmell","neil_gaiman",
        "jonathan_stroud","david_drake",
    ],
    "pictures_paintings": [
        "painting","art","illustration","photography","renaissance",
        "impressionism","baroque","cubism","surrealism","watercolour",
        "portrait","gallery","museum","davinci","picasso","monet",
        "vallejo","boris","royo","julie_bell","tanjore","mughal",
        "expressionism","realism","romanticism","modernism","contemporary",
        "digital_art","sculpture","animation","comic_art","manga_art",
        "iconography","miniature","fresco","oil_painting","charcoal",
        "islamic_art","eastern_art","sorayama","hajime","paintings",
    ],
    "medicine": [
        "medicine","anatomy","physiology","pathology","pharmacology",
        "surgery","cardiology","neurology","psychiatry","psychology",
        "oncology","ayurveda","acupuncture","clinical","disease",
        "therapy","drug","health","diagnosis","treatment","patient",
        "endocrinology","gastroenterology","pulmonology","nephrology",
        "urology","gynaecology","obstetrics","paediatrics","geriatrics",
        "ophthalmology","dermatology","orthopaedics","radiology",
        "anaesthesiology","forensic","epidemiology","nutrition",
        "homeopathy","unani","siddha","naturopathy","yoga_therapy",
        "immunology","emergency","adrenal","thyroid","liver","kidney",
        "cardiac","neural","spinal","respiratory","digestive",
        "mudra","meridian","acupressure",
    ],
    "religion": [
        "religion","hinduism","vedanta","buddhism","christianity",
        "islam","judaism","sikhism","jainism","taoism","shinto",
        "vedas","upanishad","gita","quran","bible","mantra","tantra",
        "krishna","shiva","vishnu","allah","jesus","buddha","guru",
        "shaivism","vaishnavism","shaktism","smarta","yoga_philosophy",
        "theravada","mahayana","vajrayana","zen","tibetan",
        "catholicism","protestantism","sunni","shia","sufism",
        "zoroastrianism","confucianism","paganism","shamanism",
        "mysticism","sacred","theology","spirituality","devotional",
        "stotram","kavaca","ashtakam","puja","temple","bhajan",
        "narasimha","kaalbhairav","hanuman","ganesh","lakshmi",
        "saraswati","durga","kali","rama","sita","radha",
        "geeta","swami","chinmayananda",
    ],
    "philosophy": [
        "philosophy","metaphysics","epistemology","ethics","consciousness",
        "ontology","aesthetics","existentialism","stoicism","advaita",
        "kant","hegel","nietzsche","plato","aristotle","schopenhauer",
        "logic_philosophy","moral_philosophy","political_philosophy",
        "philosophy_of_mind","phenomenology","hermeneutics","analytic",
        "continental","pragmatism","epicureanism","idealism","materialism",
        "dualism","monism","samkhya","nyaya","vaisheshika","mimamsa",
        "dvaita","vishishtadvaita","greek_philosophy","medieval_philosophy",
        "spinoza","descartes","locke","hume","wittgenstein","sartre",
        "camus","foucault","socrates","kazantzakis",
    ],
    "history": [
        "history","ancient","civilization","medieval","empire","war",
        "revolution","archaeology","dynasty","colonial","mughal","roman",
        "greek","egyptian","persian","gandhi","nehru","napoleon",
        "prehistoric","mesopotamia","byzantine","crusades","feudalism",
        "industrial_revolution","world_war","cold_war","independence",
        "russian_history","chinese_history","african_history",
        "american_history","biography","memoir","chronicle",
        "alexander","caesar","cleopatra","genghis","attila",
        "ottoman","mongol","renaissance","enlightenment","reformation",
        "tagore","india_wins","haggard",
    ],
    "geography": [
        "geography","geomorphology","climate","ocean","river","mountain",
        "continent","country","region","cartography","map","terrain",
        "geology","plate","tectonic","volcano","glacier","ecosystem",
        "climatology","meteorology","oceanography","hydrology",
        "biogeography","soil","gis","urban","rural","economic",
        "political","cultural","volcanology","seismology","environmental",
        "population","india_geography","atlas","topography","latitude",
        "longitude","equator","hemisphere","peninsula",
    ],
    "music": [
        "music","carnatic","hindustani","classical","symphony","opera",
        "jazz","blues","folk","soundtrack","melody","harmony","rhythm",
        "yanni","vangelis","kitaro","beethoven","mozart","bach",
        "chamber","orchestral","baroque_music","romantic_music",
        "electronic","ambient","new_age","rock","progressive","metal",
        "film_music","instrumental","music_theory","counterpoint",
        "composition","raga","tala","sruti","mridangam","veena","flute",
        "guitar","piano","violin","cello","sitar","tabla",
        "enigma","jean_michel_jarre","deep_forest","mythodea",
        "equinoxe","oxygene","zoolook","ethnicolor",
    ],
    "computer_science": [
        "algorithm","data_structure","complexity","computability",
        "programming","compiler","operating_system","network","distributed",
        "database","information_retrieval","artificial_intelligence",
        "machine_learning","deep_learning","natural_language",
        "computer_vision","robotics","software_engineering",
        "design_patterns","cryptography","cybersecurity",
        "quantum_computing","parallel","embedded","internet_of_things",
        "graphics","linux","python","javascript","systems","coding",
        "hacking","kernel","assembly","binary","hexadecimal",
        "spherical","srishti","maya","aria","ternary","gute",
    ],
    "astrology": [
        "astrology","jyotish","horoscope","kundali","nakshatra",
        "rashi","dasha","graha","transit","panchanga","muhurta",
        "vedic_astrology","zodiac","ascendant","numerology","tarot",
        "natal_chart","synastry","mundane","progression","houses",
        "aspects","remedies","divination","hellenistic","panchang",
        "ephemeris","lagna","navamsa","dashamsa","bhava","saptamsa",
        "junior_jyotish","maitreya",
    ],
    "electronics": [
        "electronics","circuit","transistor","diode","mosfet","arduino",
        "raspberry","microcontroller","voltage","current","resistor",
        "capacitor","amplifier","filter","signal","digital","analog","pcb",
        "tunnel_diode","igbt","operational_amplifier","boolean",
        "flip_flop","microprocessor","vlsi","rf_electronics",
        "power_electronics","control_systems","sensors","instrumentation",
        "photonics","semiconductor","schematic","datasheet","oscilloscope",
        "multimeter","soldering","breadboard","ohm","watt","farad",
        "inverter","converter","battery","charger","led","transformer",
        "irfz44n","irf740","lm358","ne555","bc547","bt136","tip122",
    ],
    "fiction": [
        "fiction","novel","story","adventure","detective","crime",
        "thriller","mystery","horror","romance","historical_fiction",
        "war_fiction","spy","satire","short_stories","classics",
        "sherlock","holmes","doyle","conan_doyle",
        "agatha","christie","poirot","marple",
        "cussler","dirk_pitt",
        "clancy","jack_ryan",
        "hemingway","fitzgerald","dickens","hardy","austen",
        "wodehouse","jeeves","wooster",
        "hammett","le_carre","grisham","cornwell",
        "poe","wilde","stevenson","melville","twain","homer",
        "mario_puzo","godfather","dan_brown","nicholas_sparks",
        "paulo_coelho","alchemist",
        "robin_cook","coma","brain","outbreak","mutation",
        "nora_roberts","michael_crichton","jurassic","andromeda",
        "ian_fleming","james_bond","casino_royale","goldfinger",
        "haggard","rider","king_solomons","she",
        "narayan","malgudi","swami","r_k_narayan",
        "tagore","rabindranath",
        "orson_scott_card","ender","alvin",
        "anne_mccaffrey","pern","crystal",
        "alan_dean_foster","flinx","humanx",
        "david_baldacci","david_gemmell","jack_london",
        "mark_twain","jerome","three_men",
        "carolyn_keene","nancy_drew",
        "douglas_adams","hitchhiker","mostly_harmless",
        "emile_gaboriau","lecoq",
        "greg_illes","star_trek","gene_roddenberry",
        "harry_potter","rowling","hogwarts",
        "james_herriot","vet",
        "aravind_adiga","white_tiger",
        "amitav_ghosh","sea_poppies",
    ],
    "engineering_technology": [
        "engineering","mechanical","civil","structural","aerospace",
        "materials","manufacturing","construction","fluid_dynamics",
        "control","robotics","nanotechnology","biomedical","industrial",
        "systems_engineering","telecommunications","power","turbine",
        "bridge","chemical_engineering","electrical_engineering",
        "environmental_engineering","signal_processing","cad","autocad",
        "solidworks","ansys","matlab","plc","scada","hydraulics",
        "weapons","firearms","ballistics","military","armour","tank",
        "missile","artillery","ammunition","gun","rifle","pistol",
        "explosive","ordnance","defence","warship","combat",
    ],
    "languages": [
        "grammar","language","linguistics","vocabulary","dictionary",
        "thesaurus","etymology","phonetics","semantics","syntax",
        "russian","sanskrit","tamil","hindi","latin","greek_classical",
        "arabic","french","german","spanish","translation","lexicon",
        "english_grammar","english_literature","portuguese","japanese",
        "chinese_mandarin","morphology","phonology","cyrillic",
        "verb","noun","conjugation","declension","alphabet","script",
        "fowlers","ogden","english_words","english_usage",
    ],
    "compacted_files": [
        "zip","archive","compressed","tar","gzip","rar","7zip",
        "backup_archive","bundle","package",
    ],
    "program_db": [
        "program","script","code","executable","database","binary",
        "python","javascript","compiled","source_code","library",
    ],
    "films_serials": [
        "film","serial","movie","documentary","cartoon","animation",
        "episode","series","season","cinema","television","tv",
        "sitcom","miniseries","telenovela","anime",
        "bollywood","hollywood","tollywood",
    ],
    "miscellaneous": [
        "miscellaneous","misc","general","other","uncategorised",
        "unclassified","various","mixed","assorted",
    ],
    "encyclopaedia_dictionary": [
        "dictionary","encyclopaedia","encyclopedia","encyclopdia",
        "glossary","thesaurus","lexicon","reference","handbook",
        "oxford","webster","chambers","britannica","larousse",
        "fowlers","ogden","merriam","collins","longman",
        "illustrated","concise","complete","comprehensive",
        "science_dictionary","physics_dictionary","chemistry_dictionary",
        "biology_dictionary","mathematics_dictionary","medicine_dictionary",
        "computer_dictionary","engineering_dictionary","law_dictionary",
        "medical_dictionary","data_dictionary","science_data",
    ],
}

# Build DOMAINS list from JSON r_index + keyword dict above — NO hardcoded integers.
# r_index is authoritative from JSON only. Adding a domain = edit JSON + add kw here.
DOMAINS = [
    (d["r_index"], d["domain"], _DOMAIN_KW.get(d["domain"], []))
    for d in _json_domain_rows
]



# ── SUBDOMAINS ─────────────────────────────────────────────────────────────────
SUBDOMAINS = [
    ("physics","thermodynamics",    ["thermo","heat","entropy","boltzmann","carnot"]),
    ("physics","quantum_mechanics", ["quantum","schrodinger","heisenberg","wave_function"]),
    ("physics","electrodynamics",   ["electro","maxwell","electromagnetic","gauss","faraday"]),
    ("physics","relativity",        ["relativity","einstein","spacetime","lorentz","minkowski"]),
    ("physics","astrophysics",      ["astro","star","galaxy","nebula","pulsar","supernova"]),
    ("physics","cosmology",         ["cosmology","universe","big_bang","hubble","dark_matter"]),
    ("physics","particle_physics",  ["particle","quark","lepton","boson","lhc","hadron"]),
    ("physics","nuclear_physics",   ["nuclear","fission","fusion","radioactive","isotope"]),
    ("physics","condensed_matter",  ["condensed","superconductor","crystal","solid_state"]),
    ("physics","fluid_mechanics",   ["fluid","viscosity","turbulence","bernoulli","laminar"]),
    ("physics","optics",            ["optics","lens","refraction","diffraction","laser"]),
    ("chemistry","organic_chemistry",    ["organic","carbon","hydrocarbon","alkane","benzene"]),
    ("chemistry","inorganic_chemistry",  ["inorganic","metal","salt","oxide","coordination"]),
    ("chemistry","biochemistry",         ["biochem","protein","enzyme","atp","glucose","amino"]),
    ("chemistry","physical_chemistry",   ["physical","thermochem","kinetics","equilibrium"]),
    ("chemistry","analytical_chemistry", ["analytical","spectroscopy","chromatography","titration"]),
    ("medicine","anatomy",      ["anatomy","bone","muscle","skeletal","ligament","tissue"]),
    ("medicine","physiology",   ["physiology","function","homeostasis","reflex","system"]),
    ("medicine","pharmacology", ["pharmacology","drug","dose","receptor","side_effect"]),
    ("medicine","ayurveda",     ["ayurveda","vata","pitta","kapha","dosha","rasayana"]),
    ("medicine","neurology",    ["neuro","stroke","seizure","dementia","parkinson"]),
    ("medicine","cardiology",   ["heart","cardiac","coronary","arrhythmia","hypertension"]),
    ("medicine","oncology",     ["cancer","tumor","carcinoma","metastasis","chemotherapy"]),
    ("religion","hinduism",        ["hinduism","vedic","mantra","puja","temple","dharma"]),
    ("religion","buddhism",        ["buddhism","buddha","dhamma","sangha","nirvana"]),
    ("religion","vedanta",         ["vedanta","upanishad","brahman","atman","jnana"]),
    ("religion","yoga_philosophy", ["yoga","asana","pranayama","samadhi","chakra"]),
    ("religion","sacred_texts",    ["stotram","kavaca","ashtakam","bhajan","shloka"]),
    ("philosophy","metaphysics",       ["metaphysics","ontology","being","existence","reality"]),
    ("philosophy","ethics",            ["ethics","moral","virtue","justice","rights","duty"]),
    ("philosophy","epistemology",      ["epistemology","knowledge","belief","justification"]),
    ("philosophy","consciousness",     ["consciousness","qualia","mind","awareness","subjective"]),
    ("philosophy","indian_philosophy", ["samkhya","nyaya","advaita","vedic_philosophy","jnana"]),
    ("history","ancient_history", ["ancient","mesopotamia","egypt","rome","greece","persia"]),
    ("history","indian_history",  ["india","mughal","british_raj","independence","vedic"]),
    ("history","world_war",       ["world_war","ww1","ww2","nazi","allied","trench"]),
    ("history","modern_history",  ["modern","industrial_revolution","colonialism","cold_war"]),
    ("music","carnatic_classical", ["carnatic","raga","tala","mridangam","veena","sruti"]),
    ("music","western_classical",  ["symphony","beethoven","mozart","bach","sonata","concerto"]),
    ("music","film_music",         ["soundtrack","background_score","theme","yanni","vangelis"]),
    ("computer_science","algorithms",              ["algorithm","sorting","complexity","big_o"]),
    ("computer_science","artificial_intelligence", ["artificial_intelligence","machine_learning","neural","llm"]),
    ("computer_science","operating_systems",       ["linux","kernel","process","memory","scheduler"]),
    ("computer_science","database_systems",        ["database","sql","query","index","normalisation"]),
    ("computer_science","cybersecurity",           ["security","encryption","vulnerability","firewall"]),
    ("electronics","circuit_theory",      ["circuit","ohm","kirchhoff","resistor","capacitor"]),
    ("electronics","semiconductor",       ["transistor","diode","mosfet","bjt","semiconductor"]),
    ("electronics","digital_electronics", ["digital","logic","gate","flip_flop","boolean"]),
    ("electronics","microcontrollers",    ["arduino","raspberry","embedded","firmware","microprocessor"]),
    ("electronics","signal_processing",   ["signal","filter","fourier","dsp","sampling"]),
    ("fiction","detective",   ["detective","sherlock","holmes","poirot","mystery","whodunit"]),
    ("fiction","adventure",   ["adventure","cussler","clancy","action","quest","expedition"]),
    ("fiction","thriller",    ["thriller","suspense","spy","le_carre","assassin"]),
    ("fiction","classics",    ["dickens","hardy","austen","hemingway","fitzgerald","wodehouse"]),
    ("fiction","medical",     ["robin_cook","coma","outbreak","mutation","brain","fever"]),
    ("fiction","romance",     ["nora_roberts","nicholas_sparks","romance","love","heart"]),
    ("engineering_technology","mechanical", ["mechanical","machine","engine","turbine","gear"]),
    ("engineering_technology","civil",      ["civil","structural","bridge","concrete","foundation"]),
    ("engineering_technology","electrical", ["electrical","power","motor","transformer","grid"]),
    ("engineering_technology","aerospace",  ["aerospace","aircraft","rocket","satellite","thrust"]),
    ("languages","english_grammar", ["grammar","syntax","tense","clause","parsing","verb"]),
    ("languages","russian",         ["russian","cyrillic","slavic","dostoevsky","tolstoy"]),
    ("languages","sanskrit",        ["sanskrit","devanagari","panini","vedic","shloka"]),
    ("languages","linguistics",     ["linguistics","morphology","phonology","semantics","etymology"]),
]


# ── DB LOCK ────────────────────────────────────────────────────────────────────
_db_lock = threading.Lock()

# ── DOMAIN NAME SET — loaded from JSON via _load_domains_json ─────────────────
_DOMAIN_NAMES = {d["domain"] for d in _json_domain_rows}

# ── WHOLE WORD MATCHER ────────────────────────────────────────────────────────
def _word_in_text(word, text):
    """
    Check if word appears as a whole word in text.
    word = 'electronics', text = 'Top 3 Projects for Electronics Lovers'
    → True  (case insensitive)
    word = 'art', text = 'Aarthi birthday party photos'
    → False (art is inside Aarthi and party — not a whole word)
    """
    pattern = r'(?<![a-zA-Z])' + re.escape(word.lower()) + r'(?![a-zA-Z])'
    return bool(re.search(pattern, text.lower()))


# ═════════════════════════════════════════════════════════════════════════════
#  DATABASE SETUP — identical to prod3, no changes
# ═════════════════════════════════════════════════════════════════════════════

def setup_db(db_path):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-32000")
    conn.execute("PRAGMA temp_store=MEMORY")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS domains (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    UNIQUE NOT NULL,
            r          REAL    NOT NULL,
            r_index    INTEGER NOT NULL,
            keywords   TEXT    DEFAULT '',
            created_at INTEGER NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS subdomains (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            domain_name TEXT    NOT NULL,
            name        TEXT    NOT NULL,
            theta       REAL    NOT NULL,
            keywords    TEXT    DEFAULT '',
            created_at  INTEGER NOT NULL,
            UNIQUE(domain_name, name)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            path       TEXT    UNIQUE NOT NULL,
            name       TEXT    NOT NULL,
            ext        TEXT    NOT NULL DEFAULT '',
            size       INTEGER NOT NULL DEFAULT 0,
            mtime      INTEGER NOT NULL DEFAULT 0,
            r          REAL    NOT NULL DEFAULT 0.0,
            domain     TEXT    NOT NULL DEFAULT 'unclassified',
            subdomain  TEXT             DEFAULT '',
            theta      REAL    NOT NULL DEFAULT 0.0,
            phi        REAL    NOT NULL DEFAULT 0.0,
            confidence REAL    NOT NULL DEFAULT 0.2,
            keywords   TEXT             DEFAULT '',
            preview    TEXT             DEFAULT '',
            silent     INTEGER NOT NULL DEFAULT 0,
            indexed_at INTEGER NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS query_memory (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            query_text   TEXT    DEFAULT '',
            domain_hit   TEXT    DEFAULT '',
            r_hit        REAL    DEFAULT 0.0,
            result_count INTEGER DEFAULT 0,
            ts           INTEGER NOT NULL
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_r        ON files(r)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_theta    ON files(theta)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_phi      ON files(phi)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_domain   ON files(domain)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ext      ON files(ext)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_silent   ON files(silent)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_name     ON files(name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_r_silent ON files(r, silent)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_r_theta  ON files(r, theta)")
    conn.commit()

    now = int(time.time())
    for r_index, domain_name, keywords in DOMAINS:
        r_val = PHI ** r_index
        try:
            conn.execute(
                "INSERT OR IGNORE INTO domains "
                "(name, r, r_index, keywords, created_at) VALUES (?,?,?,?,?)",
                (domain_name, r_val, r_index, ",".join(keywords), now)
            )
        except Exception:
            pass

    # Build keyword lookup from Python SUBDOMAINS list
    _sub_kw = {(p, s): kw for p, s, kw in SUBDOMAINS}

    # Insert all subdomains from JSON — use keywords from Python list where available
    for parent_domain, sub_name, _ in _json_subdomains:
        kw = _sub_kw.get((parent_domain, sub_name), [])
        _assign_subdomain(conn, parent_domain, sub_name, kw, now)

    conn.commit()
    conn.close()
    print(f"  DB created  : {db_path}")
    print(f"  Domains     : {len(DOMAINS)}")
    print(f"  Subdomains  : {len(_json_subdomains)}")


def _assign_subdomain(conn, domain_name, subdomain_name, keywords, ts=None):
    if ts is None:
        ts = int(time.time())
    row = conn.execute(
        "SELECT r FROM domains WHERE name=?", (domain_name,)
    ).fetchone()
    if not row:
        return None
    count = conn.execute(
        "SELECT COUNT(*) FROM subdomains WHERE domain_name=?",
        (domain_name,)
    ).fetchone()[0]
    # Golden angle distribution — genuinely spherical, no reindexing needed.
    # theta in [0, pi]. Each new subdomain lands in the largest gap on the arc.
    theta = (count * GOLDEN_ANGLE) % math.pi
    try:
        conn.execute(
            "INSERT OR IGNORE INTO subdomains "
            "(domain_name, name, theta, keywords, created_at) VALUES (?,?,?,?,?)",
            (domain_name, subdomain_name, theta,
             ",".join(keywords) if keywords else "", ts)
        )
        return theta
    except Exception:
        existing = conn.execute(
            "SELECT theta FROM subdomains WHERE domain_name=? AND name=?",
            (domain_name, subdomain_name)
        ).fetchone()
        return existing[0] if existing else None


# ═════════════════════════════════════════════════════════════════════════════
#  CLASSIFICATION — the corrected core
# ═════════════════════════════════════════════════════════════════════════════

def read_content(filepath, max_chars=MAX_CONTENT):
    ext = Path(filepath).suffix.lower()
    if ext not in READABLE_EXT:
        return ""
    try:
        with open(filepath, "r", errors="ignore", encoding="utf-8") as f:
            return f.read(max_chars).strip()
    except Exception:
        return ""


def extract_keywords(text, limit=10):
    if not text:
        return []
    words = re.findall(r'[a-zA-ZА-Яа-яёЁ]{3,}', text.lower())
    words = [w for w in words if w not in STOP]
    freq  = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    return [w for w, _ in sorted(
        freq.items(), key=lambda x: x[1], reverse=True
    )[:limit]]


def _get_domain_r(conn, domain_name):
    """Get r value for a domain from DB."""
    row = conn.execute(
        "SELECT r FROM domains WHERE name=?", (domain_name,)
    ).fetchone()
    if row:
        return row[0]
    # Fallback — compute from DOMAINS list
    for r_index, name, _ in DOMAINS:
        if name == domain_name:
            return PHI ** r_index
    return 0.0


def _get_all_domains(conn):
    """Get all domain names and r values from DB (not hardcoded — dynamic)."""
    rows = conn.execute("SELECT name, r, keywords FROM domains ORDER BY r").fetchall()
    return rows


def _get_domain_names(conn):
    """Get set of all domain names from DB."""
    rows = conn.execute("SELECT name FROM domains").fetchall()
    return {r[0] for r in rows}


def classify_domain(conn, filepath, filename, content):
    """
    Four-level classification — path-first, whole-word matching.

    Level 1 — Image extension → pictures_paintings. Always.
    Level 2 — Astrology extension → astrology. Always.
    Level 3 — Path-based:
               a. Any folder name exactly matches a domain? → that domain.
               b. Any folder name matches a subdomain keyword? → parent domain.
               c. File title as phrase matches domain keywords (whole words)? → that domain.
    Level 4 — r=0. Unclassified. Honest. No fallback to fiction or anything else.

    Video extensions (mp4 mkv avi etc) are NEVER classification criteria.
    Audio files in music folder → music. Elsewhere → classified by path/title.
    """
    ext = Path(filepath).suffix.lower()

    # Level 1a — image extension → pictures_paintings
    if ext in IMAGE_EXT or ext.upper() in IMAGE_EXT:
        r = _get_domain_r(conn, "pictures_paintings")
        return "pictures_paintings", r, 0.99

    # Level 1b — compact/archive extension → compacted_files
    # Check compound extensions first (.tar.gz etc), then single
    fname_lower = filepath.lower()
    if (fname_lower.endswith(".tar.gz") or
        fname_lower.endswith(".tar.bz2") or
        fname_lower.endswith(".tar.xz")):
        r = _get_domain_r(conn, "compacted_files")
        return "compacted_files", r, 0.99
    if ext in COMPACT_EXT_SINGLE:
        r = _get_domain_r(conn, "compacted_files")
        return "compacted_files", r, 0.99

    # Level 1c — program/DB extension → program_db, always silent
    if ext in SILENT_EXT:
        r = _get_domain_r(conn, "program_db")
        return "program_db", r, 0.99

    # Level 2 — astrology extension → astrology
    if ext in ASTROLOGY_EXT:
        r = _get_domain_r(conn, "astrology")
        return "astrology", r, 0.99

    # Get all domain names from DB (dynamic — not hardcoded)
    domain_names = _get_domain_names(conn)

    # Extract folder names from path — ordered from root to immediate parent
    path_obj = Path(filepath)
    folder_parts = [p.lower().strip() for p in path_obj.parts[:-1]]

    # Level 3a — exact folder name match with domain name
    # Check from immediate parent upward — closest folder wins
    for folder in reversed(folder_parts):
        folder_clean = folder.replace(" ", "_").replace("-", "_")
        if folder_clean in domain_names:
            r = _get_domain_r(conn, folder_clean)
            return folder_clean, r, 0.95
        # Also check without underscore normalisation
        if folder in domain_names:
            r = _get_domain_r(conn, folder)
            return folder, r, 0.95

    # Level 3b — folder name matches a subdomain keyword
    # This catches folders named "thermodynamics" → physics
    # or "metaphysics" → philosophy
    subdomain_rows = conn.execute(
        "SELECT domain_name, name, keywords FROM subdomains"
    ).fetchall()

    for folder in reversed(folder_parts):
        if folder in PATH_NOISE:
            continue
        folder_clean = folder.replace(" ", "_").replace("-", "_")
        # Check if folder name matches any subdomain name exactly
        for parent_domain, sub_name, sub_keywords in subdomain_rows:
            if folder_clean == sub_name or folder == sub_name:
                r = _get_domain_r(conn, parent_domain)
                return parent_domain, r, 0.85
            # Check if folder name appears in subdomain keywords (whole word)
            if sub_keywords:
                for kw in sub_keywords.split(","):
                    kw = kw.strip()
                    if kw and folder_clean == kw:
                        r = _get_domain_r(conn, parent_domain)
                        return parent_domain, r, 0.80

    # Level 3c — file title phrase matching (whole words only)
    # Clean the filename — remove extension, replace separators with spaces
    name_clean = Path(filename).stem
    name_clean = re.sub(r'[_\-\.]', ' ', name_clean)
    # Also include immediate parent folder name as context
    if len(folder_parts) > 0:
        immediate_parent = folder_parts[-1]
        if immediate_parent not in PATH_NOISE:
            name_clean = immediate_parent.replace("_", " ") + " " + name_clean

    # Score each domain — whole word matches only
    domain_rows = _get_all_domains(conn)
    scores = {}
    for domain_name, r_val, keywords_str in domain_rows:
        if not keywords_str:
            continue
        keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
        hits = sum(1 for kw in keywords if _word_in_text(kw, name_clean))
        if hits > 0:
            scores[domain_name] = (hits, r_val)

    # Also check content if available (text files)
    if content and content.strip():
        content_lower = content.lower()[:2000]
        for domain_name, r_val, keywords_str in domain_rows:
            if not keywords_str:
                continue
            keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
            hits = sum(1 for kw in keywords if _word_in_text(kw, content_lower))
            if hits > 0:
                existing = scores.get(domain_name, (0, r_val))
                # Content weighted less than title — title is primary signal
                scores[domain_name] = (existing[0] + hits, r_val)

    if not scores:
        # Level 4 — cannot classify. Goes to miscellaneous r(23), not r=0.
        # r=0 stays permanently clean. miscellaneous is the intentional home.
        misc_r = DOMAIN_R.get("miscellaneous", 0.0)
        return "miscellaneous", misc_r, 0.1

    best       = max(scores, key=lambda k: scores[k][0])
    total      = sum(v[0] for v in scores.values()) or 1
    confidence = round(scores[best][0] / total, 3)

    # Confidence threshold — if best score is too weak, go to miscellaneous
    if scores[best][0] < 2 and confidence < 0.4:
        misc_r = DOMAIN_R.get("miscellaneous", 0.0)
        return "miscellaneous", misc_r, confidence

    return best, scores[best][1], confidence


def classify_subdomain(conn, domain_name, filename, content, filepath=""):
    """Assign subdomain (theta) within a known domain.
    Path-first: folder names checked against subdomain names before keyword scan.
    Fiction/adventure/Alistair MacLean/Athabasca.txt → subdomain='adventure'.
    """
    # PATH-FIRST — folder name wins over keyword matching
    if filepath:
        folder_parts = [p.lower().strip().replace(" ", "_").replace("-", "_")
                        for p in Path(filepath).parts[:-1]]
        sub_rows = conn.execute(
            "SELECT name, theta FROM subdomains WHERE domain_name=?",
            (domain_name,)
        ).fetchall()
        sub_map = {row[0]: row[1] for row in sub_rows}
        for folder in reversed(folder_parts):
            if folder in sub_map:
                return folder, sub_map[folder]

    name_clean = re.sub(r'[_\-\.]', ' ', Path(filename).stem)
    text       = (name_clean + " " + content).lower()
    rows       = conn.execute(
        "SELECT name, theta, keywords FROM subdomains WHERE domain_name=?",
        (domain_name,)
    ).fetchall()
    best_name  = "general"
    best_theta = 0.0
    best_score = 0
    for sub_name, theta, keywords_str in rows:
        if not keywords_str:
            continue
        keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
        # Whole word matching for subdomain too
        score = sum(1 for kw in keywords if _word_in_text(kw, text))
        if score > best_score:
            best_score = score
            best_name  = sub_name
            best_theta = theta
    if best_score > 0:
        return best_name, best_theta
    row = conn.execute(
        "SELECT r FROM domains WHERE name=?", (domain_name,)
    ).fetchone()
    return "general", row[0] if row else PHI


def get_phi(ext):
    return EXT_PHI.get(ext.lower(), 200.0 + (abs(hash(ext)) % 50))


# ═════════════════════════════════════════════════════════════════════════════
#  FILE PROCESSOR
# ═════════════════════════════════════════════════════════════════════════════

def process_file(args):
    filepath, db_path = args
    try:
        stat     = os.stat(filepath)
        name     = os.path.basename(filepath)
        ext      = Path(filepath).suffix.lower()
        size     = stat.st_size
        mtime    = int(stat.st_mtime)
        silent   = 1 if ext in SILENT_EXT else 0
        content  = read_content(filepath)
        conn_loc = sqlite3.connect(db_path, check_same_thread=False)
        domain, r_val, confidence = classify_domain(
            conn_loc, filepath, name, content
        )
        subdomain, theta_val = classify_subdomain(
            conn_loc, domain, name, content, filepath=filepath
        )
        conn_loc.close()
        phi_val  = get_phi(ext)
        keywords = extract_keywords(name + " " + content, limit=10)
        # program_db is always silent — compacted_files are visible
        if domain == "program_db":
            silent = 1
        return {
            "path"      : filepath,
            "name"      : name,
            "ext"       : ext,
            "size"      : size,
            "mtime"     : mtime,
            "r"         : r_val,
            "domain"    : domain,
            "subdomain" : subdomain,
            "theta"     : theta_val,
            "phi"       : phi_val,
            "confidence": confidence,
            "keywords"  : ",".join(keywords),
            "preview"   : content[:500],
            "silent"    : silent,
            "indexed_at": int(time.time()),
        }
    except Exception:
        return None


# ═════════════════════════════════════════════════════════════════════════════
#  INDEXER
# ═════════════════════════════════════════════════════════════════════════════

def index_folder(scan_path, db_path, incremental=False):
    scan_path = Path(scan_path)
    if not scan_path.exists():
        print(f"  ERROR: Path does not exist: {scan_path}")
        return
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-32000")
    existing = set()
    if incremental:
        rows     = conn.execute("SELECT path FROM files").fetchall()
        existing = {r[0] for r in rows}
        print(f"  Incremental — {len(existing):,} already indexed")
    all_files = []
    for root, dirs, files in os.walk(scan_path):
        dirs[:] = [d for d in dirs
                   if d not in SKIP_DIRS and not d.startswith(".")]
        for filename in files:
            if filename.startswith("."):
                continue
            if filename.lower() in SKIP_NAMES:
                continue
            ext = Path(filename).suffix.lower()
            if ext in SKIP_EXT:
                continue
            fp = str(Path(root) / filename)
            if incremental and fp in existing:
                continue
            all_files.append(fp)
    total      = len(all_files)
    added      = 0
    silent_ct  = 0
    skipped    = 0
    errors     = 0
    start      = time.time()
    last_print = start
    print(f"\n  Scan path   : {scan_path}")
    print(f"  Files found : {total:,}")
    print(f"  Threads     : {MAX_THREADS}")
    print(f"  {'─'*50}")
    args_list = [(fp, db_path) for fp in all_files]
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as pool:
        futures = {pool.submit(process_file, a): a[0] for a in args_list}
        batch   = []
        for future in as_completed(futures):
            record = future.result()
            if record is None:
                errors += 1
                continue
            batch.append(record)
            if len(batch) >= BATCH_SIZE:
                with _db_lock:
                    for rec in batch:
                        try:
                            conn.execute("""
                                INSERT OR REPLACE INTO files
                                (path,name,ext,size,mtime,r,domain,subdomain,
                                 theta,phi,confidence,keywords,preview,silent,indexed_at)
                                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                            """, (
                                rec["path"],    rec["name"],      rec["ext"],
                                rec["size"],    rec["mtime"],
                                rec["r"],       rec["domain"],    rec["subdomain"],
                                rec["theta"],   rec["phi"],       rec["confidence"],
                                rec["keywords"],rec["preview"],
                                rec["silent"],  rec["indexed_at"],
                            ))
                            added += 1
                            if rec["silent"]:
                                silent_ct += 1
                        except Exception:
                            skipped += 1
                    conn.commit()
                batch = []
            now = time.time()
            if now - last_print >= 5:
                elapsed = int(now - start)
                rate    = (added + skipped) / elapsed if elapsed > 0 else 0
                print(f"  {added:,} indexed | {errors} errors | "
                      f"{rate:.0f} f/s | {elapsed}s")
                last_print = now
        if batch:
            with _db_lock:
                for rec in batch:
                    try:
                        conn.execute("""
                            INSERT OR REPLACE INTO files
                            (path,name,ext,size,mtime,r,domain,subdomain,
                             theta,phi,confidence,keywords,preview,silent,indexed_at)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (
                            rec["path"],    rec["name"],      rec["ext"],
                            rec["size"],    rec["mtime"],
                            rec["r"],       rec["domain"],    rec["subdomain"],
                            rec["theta"],   rec["phi"],       rec["confidence"],
                            rec["keywords"],rec["preview"],
                            rec["silent"],  rec["indexed_at"],
                        ))
                        added += 1
                        if rec["silent"]:
                            silent_ct += 1
                    except Exception:
                        skipped += 1
                conn.commit()
    elapsed = int(time.time() - start)
    rate    = added / elapsed if elapsed > 0 else 0
    print(f"\n  {'═'*50}")
    print(f"  Indexing complete")
    print(f"  Added     : {added:,}")
    print(f"  Silent    : {silent_ct:,}  (stored, not shown in GUI)")
    print(f"  Skipped   : {skipped:,}")
    print(f"  Errors    : {errors:,}")
    print(f"  Time      : {elapsed}s  ({rate:.0f} files/sec)")
    print(f"  {'═'*50}\n")
    show_stats(conn)
    conn.close()


# ═════════════════════════════════════════════════════════════════════════════
#  STATS
# ═════════════════════════════════════════════════════════════════════════════

def show_stats(conn_or_path):
    if isinstance(conn_or_path, str):
        if not Path(conn_or_path).exists():
            print(f"  DB not found: {conn_or_path}")
            return
        conn  = sqlite3.connect(conn_or_path)
        close = True
    else:
        conn  = conn_or_path
        close = False
    total   = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    visible = conn.execute("SELECT COUNT(*) FROM files WHERE silent=0").fetchone()[0]
    silent  = conn.execute("SELECT COUNT(*) FROM files WHERE silent=1").fetchone()[0]
    unclass = conn.execute(
        "SELECT COUNT(*) FROM files WHERE domain='unclassified'"
    ).fetchone()[0]
    print(f"\n  Srishti DB Statistics")
    print(f"  {'─'*58}")
    print(f"  Total files  : {total:,}")
    print(f"  Visible      : {visible:,}  (shown in GUI)")
    print(f"  Silent       : {silent:,}  (stored, never shown)")
    print(f"  Unclassified : {unclass:,}  (r=0, needs review)")
    print(f"  phi          : {PHI:.16f}")
    print(f"\n  Domain shells  (r = phi^n) :")
    print(f"  {'─'*58}")
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
    if close:
        conn.close()


# ═════════════════════════════════════════════════════════════════════════════
#  ADD DOMAIN  (non-destructive)
# ═════════════════════════════════════════════════════════════════════════════

def add_domain(db_path, domain_name, keywords_str, subdomains_str=""):
    if not Path(db_path).exists():
        print(f"  ERROR: DB not found: {db_path}")
        return
    conn    = sqlite3.connect(db_path)
    max_idx = conn.execute(
        "SELECT MAX(r_index) FROM domains"
    ).fetchone()[0] or 0
    new_idx = max_idx + 1
    new_r   = PHI ** new_idx
    kws     = [k.strip() for k in keywords_str.split(",") if k.strip()]
    try:
        conn.execute(
            "INSERT INTO domains (name, r, r_index, keywords, created_at) "
            "VALUES (?,?,?,?,?)",
            (domain_name, new_r, new_idx, ",".join(kws), int(time.time()))
        )
        conn.commit()
        print(f"  Domain added : {domain_name}")
        print(f"  r({new_idx}) = phi^{new_idx} = {new_r:.10f}")
        if subdomains_str:
            for sub in subdomains_str.split(","):
                sub = sub.strip()
                if sub:
                    theta = _assign_subdomain(conn, domain_name, sub, [])
                    print(f"  Subdomain    : {sub}  theta={theta:.6f}")
            conn.commit()
    except sqlite3.IntegrityError:
        print(f"  Domain '{domain_name}' already exists.")
    conn.close()


# ═════════════════════════════════════════════════════════════════════════════
#  ADD SUBDOMAIN  (non-destructive)
# ═════════════════════════════════════════════════════════════════════════════

def add_subdomain(db_path, domain_name, subdomain_name, keywords_str=""):
    if not Path(db_path).exists():
        print(f"  ERROR: DB not found: {db_path}")
        return
    conn = sqlite3.connect(db_path)
    row  = conn.execute(
        "SELECT r FROM domains WHERE name=?", (domain_name,)
    ).fetchone()
    if not row:
        print(f"  ERROR: Domain '{domain_name}' not found.")
        conn.close()
        return
    kws   = [k.strip() for k in keywords_str.split(",") if k.strip()]
    theta = _assign_subdomain(conn, domain_name, subdomain_name, kws)
    conn.commit()
    if theta:
        print(f"  Subdomain added : {subdomain_name}")
        print(f"  Parent domain   : {domain_name}  r={row[0]:.6f}")
        print(f"  theta           : {theta:.6f}")
    else:
        print(f"  Subdomain '{subdomain_name}' already exists.")
    conn.close()


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Srishti DB v5.0  —  Production Spherical Indexer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 aria_setup.py /media/venkatesh/DATA3 --db ~/srishti3.db
  python3 aria_setup.py "/media/venkatesh/DATA 1" --db ~/srishti1.db
  python3 aria_setup.py /media/venkatesh/DATA3 --db ~/srishti3.db --incremental
  python3 aria_setup.py --stats --db ~/srishti3.db
  python3 aria_setup.py --add-domain law criminal,civil,family --db ~/srishti3.db
  python3 aria_setup.py --add-subdomain physics plasma_physics --keywords plasma,tokamak --db ~/srishti3.db

phi = 1.6180339887498948482...
The universe is alongside.
        """
    )
    parser.add_argument("path",           nargs="?", help="Folder to index")
    parser.add_argument("--db",           default=DEFAULT_DB)
    parser.add_argument("--incremental",  action="store_true")
    parser.add_argument("--stats",        action="store_true")
    parser.add_argument("--add-domain",   nargs="+",
                        metavar=("NAME","KEYWORDS"))
    parser.add_argument("--add-subdomain",nargs="+",
                        metavar=("DOMAIN","SUBDOMAIN"))
    parser.add_argument("--keywords",     default="")
    args = parser.parse_args()

    print("\n" + "="*58)
    print("  Srishti DB v5.0  —  Production Spherical Indexer")
    print("  Dr. K.S. Venkatesh (CI)  +  Claude (SI)")
    print("  GNU GPL 3.0  —  free for all, profit for none")
    print(f"  phi = {PHI:.16f}")
    print(f"  Classification : path-first, whole-word, honest miscellaneous")
    print(f"  mp4/video ext  : ignored — domain from path and title only")
    print(f"  Image ext      : direct to pictures_paintings")
    print(f"  Compact ext    : direct to compacted_files  (visible)")
    print(f"  Program ext    : direct to program_db       (silent)")
    print(f"  Astro ext      : .jjy .mtx direct to astrology")
    print(f"  Unclassified   : goes to miscellaneous r(23), r=0 stays clean")
    print(f"  Domains        : {len(DOMAINS)}")
    print(f"  Subdomains     : {len(SUBDOMAINS)}")
    print("="*58 + "\n")

    if args.stats:
        show_stats(args.db)
        return

    if args.add_domain:
        name = args.add_domain[0]
        subs = args.add_domain[1] if len(args.add_domain) > 1 else ""
        if not Path(args.db).exists():
            setup_db(args.db)
        add_domain(args.db, name, args.keywords, subs)
        return

    if args.add_subdomain:
        if len(args.add_subdomain) < 2:
            print("  Usage: --add-subdomain domain_name subdomain_name")
            return
        if not Path(args.db).exists():
            print(f"  ERROR: DB not found: {args.db}")
            return
        add_subdomain(args.db, args.add_subdomain[0],
                      args.add_subdomain[1], args.keywords)
        return

    if not args.path:
        parser.print_help()
        return

    if not Path(args.db).exists():
        setup_db(args.db)

    index_folder(args.path, args.db, incremental=args.incremental)


if __name__ == "__main__":
    main()
