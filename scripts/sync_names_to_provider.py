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
    """provider -> id -> name"""
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
                idmap[sid] = name
        index[prov] = idmap
    return index


def load_extra_index(path):
    """id -> (name, provider|None)"""
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
            idmap[sid] = (name, current_provider)
    return idmap


def main():
    # Backup
    ts = __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = f"{CSV_PATH}.bak_{ts}"
    os.replace(CSV_PATH, backup)

    with open(backup, newline='', encoding='utf-8') as cf:
        rows = list(csv.DictReader(cf))
    headers = rows[0].keys() if rows else []

    provider_index = load_provider_index(PROVIDER_FILES)
    extra_index = load_extra_index(EXTRA_FILE)

    updated = 0
    for row in rows:
        provider_raw = str(row.get('Provider','')).strip()
        provider = PROVIDER_NORMALIZE.get(provider_raw, provider_raw)
        sid = str(row.get('ID','')).strip()
        if not sid.isdigit():
            continue
        found_name = None
        # Prefer provider file first
        if provider in provider_index and sid in provider_index[provider]:
            found_name = provider_index[provider][sid]
        else:
            # fall back to extra file if available and provider matches
            if sid in extra_index:
                name_extra, prov_extra = extra_index[sid]
                if prov_extra is None or prov_extra == provider:
                    found_name = name_extra
        if found_name and row.get('Name') != found_name:
            row['Name'] = found_name
            updated += 1

    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as wf:
        writer = csv.DictWriter(wf, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Backup: {backup}")
    print(f"Names updated: {updated}")


if __name__ == '__main__':
    main()
