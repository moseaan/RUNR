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

id_line_regex = re.compile(r"^\s*(\d{1,7})\s*[\t ]+")


def load_provider_index(paths):
    index = {}
    for prov, path in paths.items():
        idmap = {}
        if not os.path.exists(path):
            index[prov] = idmap
            continue
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for raw in f:
                m = id_line_regex.match(raw)
                if not m:
                    continue
                sid = m.group(1)
                idmap[sid] = True
        index[prov] = idmap
    return index


def load_extra_index(path):
    idmap = {}
    if not os.path.exists(path):
        return idmap
    current_provider = None
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for raw in f:
            line = raw.strip()
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
            idmap[sid] = current_provider or 'Extra'
    return idmap


def main():
    # Backup
    ts = __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = f"{CSV_PATH}.bak_{ts}"
    os.replace(CSV_PATH, backup)

    # Load data
    with open(backup, newline='', encoding='utf-8') as cf:
        rows = list(csv.DictReader(cf))
    headers = rows[0].keys() if rows else [
        "Platform","Service Category","Tier","Provider","ID","Name","Rate/1K","Min/Max","Time/Speed","Why Organic/Notes"
    ]

    provider_index = load_provider_index(PROVIDER_FILES)
    extra_index = load_extra_index(EXTRA_FILE)

    # Build set of all known IDs
    known_ids = set()
    for idmap in provider_index.values():
        known_ids.update(idmap.keys())
    known_ids.update(extra_index.keys())

    kept = []
    removed = []

    for row in rows:
        sid = str(row.get('ID','')).strip()
        if not sid.isdigit():
            # drop non-numeric IDs (already handled earlier but keep consistent)
            removed.append(row)
            continue
        if sid in known_ids:
            kept.append(row)
        else:
            removed.append(row)

    # Write filtered CSV
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as wf:
        writer = csv.DictWriter(wf, fieldnames=headers)
        writer.writeheader()
        writer.writerows(kept)

    # Write removed rows snapshot for reference
    removed_path = CSV_PATH.replace('.csv', f'.removed_{ts}.csv')
    with open(removed_path, 'w', newline='', encoding='utf-8') as rf:
        writer = csv.DictWriter(rf, fieldnames=headers)
        writer.writeheader()
        writer.writerows(removed)

    print(f"Backup: {backup}")
    print(f"Kept rows: {len(kept)} | Removed rows: {len(removed)}")
    print(f"Removed rows saved to: {removed_path}")


if __name__ == '__main__':
    main()
