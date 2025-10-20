import csv
import os
import re
from collections import defaultdict

CSV_PATH = r"c:\Users\369\Documents\Bots\Music Industry Machine\config\SMM_Services_Tiers.csv"
PROVIDER_FILES = {
    "JustAnotherPanel": r"c:\Users\369\Documents\Bots\Music Industry Machine\config\justanotherpanel services list.txt",
    "Peakerr": r"c:\Users\369\Documents\Bots\Music Industry Machine\config\peakerr services list.txt",
    "SMMKings": r"c:\Users\369\Documents\Bots\Music Industry Machine\config\smmkings services list.txt",
}
EXTRA_FILE = r"c:\Users\369\Documents\Bots\Music Industry Machine\config\extra services.txt"
REPORT_PATH = r"c:\Users\369\Documents\Bots\Music Industry Machine\config\audit_report.txt"

# Normalize provider aliases
PROVIDER_NORMALIZE = {
    "JAP": "JustAnotherPanel",
    "jap": "JustAnotherPanel",
    "JustAnotherPanel": "JustAnotherPanel",
    "justanotherpanel": "JustAnotherPanel",
    "Peakerr": "Peakerr",
    "peakerr": "Peakerr",
    "SMMKings": "SMMKings",
    "smmkings": "SMMKings",
}

PLATFORM_HINTS = {
    "Instagram": ["Instagram", "Threads"],
    "Telegram": ["Telegram"],
    "TikTok": ["TikTok", "Tiktok"],
    "Spotify": ["Spotify"],
    "YouTube": ["Youtube", "YouTube"],
}

id_line_regex = re.compile(r"^\s*(\d{1,7})\s*[\t ]+")

# Remove emojis/special symbols and normalize spacing/brackets for name comparison
def normalize_name(s: str) -> str:
    if not s:
        return ""
    # Remove most emoji/symbols by keeping common ASCII and selected punctuation
    s2 = re.sub(r"[^A-Za-z0-9\[\]\(\)\-:_',.&/ +]", " ", s)
    # Normalize bracket spacing like "[ X ]" -> "[X]"
    s2 = re.sub(r"\[\s+", "[", s2)
    s2 = re.sub(r"\s+\]", "]", s2)
    # Collapse whitespace
    s2 = re.sub(r"\s+", " ", s2).strip().lower()
    return s2


def load_provider_index(paths):
    """Build index: provider -> id -> (line, name_fragment)
    name_fragment is the service name part after the ID column (best effort).
    """
    index = {}
    for prov, path in paths.items():
        idmap = {}
        if not os.path.exists(path):
            continue
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for raw in f:
                m = id_line_regex.match(raw)
                if not m:
                    continue
                sid = m.group(1)
                # Try to parse name after ID and some separators
                # Split by tabs first; fallback to multiple spaces
                parts = re.split(r"\t+|\s{2,}", raw.strip())
                # Heuristic: first token may be ID; next token(s) until price is name
                name = ""
                if parts and parts[0].isdigit():
                    # find the first token that looks like a price like $...
                    name_tokens = []
                    for tok in parts[1:]:
                        if tok.startswith("$"):
                            break
                        name_tokens.append(tok)
                    name = " ".join(name_tokens).strip()
                else:
                    # Fallback to the raw line without the numeric ID prefix
                    name = raw.strip()
                idmap[sid] = (raw.rstrip("\n"), name)
        index[prov] = idmap
    return index


def load_extra_index(path):
    """Parse extra services file with provider sections like 'peakerr:'
    Returns dict: id -> (line, name, provider)
    """
    idmap = {}
    if not os.path.exists(path):
        return idmap
    current_provider = None
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for raw in f:
            line = raw.strip()
            # Detect provider section headers like 'peakerr:' or 'JustAnotherPanel:'
            mprov = re.match(r"^([A-Za-z][A-Za-z ]+):\s*$", line)
            if mprov:
                prov_label = mprov.group(1).strip()
                prov_norm = PROVIDER_NORMALIZE.get(prov_label, PROVIDER_NORMALIZE.get(prov_label.lower(), prov_label))
                current_provider = prov_norm
                continue

            m = id_line_regex.match(raw)
            if not m:
                continue
            sid = m.group(1)
            parts = re.split(r"\t+|\s{2,}", raw.strip())
            name = ""
            if parts and parts[0].isdigit():
                name_tokens = []
                for tok in parts[1:]:
                    if tok.startswith("$"):
                        break
                    name_tokens.append(tok)
                name = " ".join(name_tokens).strip()
            else:
                name = raw.strip()
            idmap[sid] = (raw.rstrip("\n"), name, current_provider)
    return idmap


def guess_platform_from_name(name: str) -> str | None:
    n = name or ""
    for platform, hints in PLATFORM_HINTS.items():
        for h in hints:
            if h.lower() in n.lower():
                return platform
    return None


def audit():
    provider_index = load_provider_index(PROVIDER_FILES)
    extra_index = load_extra_index(EXTRA_FILE)

    report_lines = []
    summary = defaultdict(int)

    # Load CSV
    with open(CSV_PATH, newline='', encoding='utf-8') as cf:
        reader = csv.DictReader(cf)
        rows = list(reader)

    # Build reverse index across all providers to detect provider mismatches
    global_id_locations = defaultdict(list)
    for prov, idmap in provider_index.items():
        for sid in idmap.keys():
            global_id_locations[sid].append(prov)
    for sid, (_line, _name, prov) in extra_index.items():
        global_id_locations[sid].append(prov or 'Extra')

    for i, row in enumerate(rows, start=2):  # start=2 to account for header line numbering
        platform = row.get('Platform', '').strip()
        service_cat = row.get('Service Category', '').strip()
        provider_raw = row.get('Provider', '').strip()
        sid = str(row.get('ID', '')).strip()
        name_csv = row.get('Name', '').strip()

        provider = PROVIDER_NORMALIZE.get(provider_raw, provider_raw)
        expected_file = provider_index.get(provider)

        row_header = f"Line {i}: Provider={provider_raw} Platform={platform} Cat={service_cat} ID={sid}"
        # Skip if ID empty or non-numeric
        if not sid.isdigit():
            report_lines.append(f"[WARN] {row_header} -> Non-numeric ID in CSV")
            summary['non_numeric_id'] += 1
            continue

        found = False
        found_name = None
        found_provider = None

        # 1) Try expected provider file
        if expected_file and sid in expected_file:
            found = True
            found_provider = provider
            found_name = expected_file[sid][1]
        else:
            # 2) Try extra file
            if sid in extra_index:
                found = True
                _line, _name, prov = extra_index[sid]
                found_provider = prov or 'Extra'
                found_name = _name
            else:
                # 3) Search other providers to detect provider mismatch
                for prov, idmap in provider_index.items():
                    if prov == provider:
                        continue
                    if sid in idmap:
                        found = True
                        found_provider = prov
                        found_name = idmap[sid][1]
                        break

        if not found:
            report_lines.append(f"[MISSING] {row_header} -> ID not found in provider lists or extra services")
            summary['missing'] += 1
            continue

        # If provider mismatch
        if provider not in (found_provider, 'Extra'):
            report_lines.append(f"[PROVIDER_MISMATCH] {row_header} -> CSV provider '{provider_raw}' but ID found under provider '{found_provider}'")
            summary['provider_mismatch'] += 1

        # Name similarity check (basic): exact match or case-insensitive containment either way
        name_ok = False
        if name_csv and found_name:
            a = normalize_name(name_csv)
            b = normalize_name(found_name)
            if a == b or a in b or b in a:
                name_ok = True
        else:
            name_ok = True  # if either missing, skip
        if not name_ok:
            report_lines.append(f"[NAME_MISMATCH] {row_header} -> CSV name '{name_csv}' vs Provider name '{found_name}'")
            summary['name_mismatch'] += 1

        # Platform hint check
        hint = guess_platform_from_name(found_name or name_csv)
        if hint and platform and hint != platform:
            report_lines.append(f"[PLATFORM_SUSPECT] {row_header} -> CSV platform '{platform}' vs Name hint '{hint}'")
            summary['platform_suspect'] += 1

    # Write report
    with open(REPORT_PATH, 'w', encoding='utf-8') as rf:
        rf.write("Full Audit Report\n")
        rf.write("="*80 + "\n\n")
        rf.write("Summary:\n")
        for k in sorted(summary.keys()):
            rf.write(f"  {k}: {summary[k]}\n")
        rf.write("\nDetails:\n")
        for line in report_lines:
            rf.write(line + "\n")

    # Print concise summary to stdout
    print("Audit complete.")
    for k in sorted(summary.keys()):
        print(f"{k}: {summary[k]}")
    print(f"Report saved to: {REPORT_PATH}")


if __name__ == '__main__':
    audit()
