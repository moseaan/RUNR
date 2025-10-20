import csv
import os
import re

CSV_PATH = r"c:\Users\369\Documents\Bots\Music Industry Machine\config\SMM_Services_Tiers.csv"
REPORT_PATH = r"c:\Users\369\Documents\Bots\Music Industry Machine\config\audit_report.txt"

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

# Example line:
# [PROVIDER_MISMATCH] Line 82: Provider=SMMKings Platform=Spotify Cat=Plays Free/Premium ID=569 -> CSV provider 'SMMKings' but ID found under provider 'Extra'
# or Found provider is a real provider name
re_pm = re.compile(r"^\[PROVIDER_MISMATCH\] Line (\d+): .*? ID=(?P<id>\d+) -> .* found under provider '(?P<found>[^']+)'")


def parse_provider_mismatches(report_path):
    items = []
    if not os.path.exists(report_path):
        return items
    with open(report_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            m = re_pm.match(line.strip())
            if m:
                sid = m.group('id').strip()
                found = m.group('found').strip()
                # Skip if found provider is 'Extra' (ambiguous)
                if found.lower() == 'extra':
                    continue
                found_norm = PROVIDER_NORMALIZE.get(found, PROVIDER_NORMALIZE.get(found.lower(), found))
                items.append((sid, found_norm))
    return items


def main():
    mismatches = parse_provider_mismatches(REPORT_PATH)
    if not mismatches:
        print('No actionable provider mismatches found.')
        return

    # Map by ID -> provider (prefer first; if conflicting, skip)
    id_target = {}
    conflicts = set()
    for sid, prov in mismatches:
        if sid in id_target and id_target[sid] != prov:
            conflicts.add(sid)
        else:
            id_target[sid] = prov

    for sid in conflicts:
        id_target.pop(sid, None)

    # Backup CSV
    ts = __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = f"{CSV_PATH}.bak_{ts}"
    os.replace(CSV_PATH, backup)

    with open(backup, newline='', encoding='utf-8') as cf:
        rows = list(csv.DictReader(cf))
    headers = rows[0].keys() if rows else []

    changed = 0
    for row in rows:
        sid = str(row.get('ID','')).strip()
        if sid in id_target:
            target_prov = id_target[sid]
            if row.get('Provider') != target_prov:
                row['Provider'] = target_prov
                changed += 1

    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as wf:
        writer = csv.DictWriter(wf, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Backup: {backup}")
    print(f"Provider fixes applied: {changed}")


if __name__ == '__main__':
    main()
