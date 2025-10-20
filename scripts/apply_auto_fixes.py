import csv
import os
import re
from collections import defaultdict

CSV_PATH = r"c:\Users\369\Documents\Bots\Music Industry Machine\config\SMM_Services_Tiers.csv"
MISSING_OUT = r"c:\Users\369\Documents\Bots\Music Industry Machine\config\missing_rows.csv"
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
                idmap[sid] = raw.rstrip("\n")
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

    # Reverse map: id -> list of providers that contain it
    id_providers = defaultdict(list)
    for prov, idmap in provider_index.items():
        for sid in idmap.keys():
            id_providers[sid].append(prov)
    for sid, prov in extra_index.items():
        if prov:
            id_providers[sid].append(prov)

    new_rows = []
    missing_rows = []

    for row in rows:
        sid = str(row.get('ID','')).strip()
        provider_raw = str(row.get('Provider','')).strip()
        provider_norm = PROVIDER_NORMALIZE.get(provider_raw, provider_raw)

        # Remove non-numeric ID rows
        if not sid.isdigit():
            # skip adding to new_rows
            continue

        # Determine presence
        providers_with_id = id_providers.get(sid, [])
        if not providers_with_id:
            # Missing: export for review, keep in main CSV per user request? We will not delete
            missing_rows.append(row.copy())
            new_rows.append(row)
            continue

        # Auto-correct provider when unambiguous
        unique_providers = sorted(set(providers_with_id))
        if provider_norm not in unique_providers and len(unique_providers) == 1:
            corrected = unique_providers[0]
            row['Provider'] = corrected
        new_rows.append(row)

    # Write main CSV back
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as wf:
        writer = csv.DictWriter(wf, fieldnames=headers)
        writer.writeheader()
        writer.writerows(new_rows)

    # Write missing rows export
    if missing_rows:
        with open(MISSING_OUT, 'w', newline='', encoding='utf-8') as mf:
            writer = csv.DictWriter(mf, fieldnames=headers)
            writer.writeheader()
            writer.writerows(missing_rows)

    print(f"Backup: {backup}")
    print(f"Updated CSV rows: {len(new_rows)} (removed {len(rows)-len(new_rows)} non-numeric)")
    print(f"Missing rows exported: {len(missing_rows)} -> {MISSING_OUT}")


if __name__ == '__main__':
    main()
