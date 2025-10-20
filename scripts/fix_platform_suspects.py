import csv
import os
import re

CSV_PATH = r"c:\Users\369\Documents\Bots\Music Industry Machine\config\SMM_Services_Tiers.csv"
REPORT_PATH = r"c:\Users\369\Documents\Bots\Music Industry Machine\config\audit_report.txt"

PLATFORM_MAP = {
    'Instagram': 'Instagram',
    'Telegram': 'Telegram',
    'TikTok': 'TikTok',
    'YouTube': 'YouTube',
    'Spotify': 'Spotify',
}

suspect_re = re.compile(r"^\[PLATFORM_SUSPECT\] Line (\d+): .*? Platform=(?P<platform>\w+) .*? ID=(?P<id>[^ ]+) -> .* Name hint '(?P<hint>\w+)'\s*$")


def parse_suspects(report_path):
    suspects = []
    if not os.path.exists(report_path):
        return suspects
    with open(report_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            m = suspect_re.match(line.strip())
            if not m:
                continue
            csv_line = int(m.group(1))
            sid = m.group('id').strip()
            hint = m.group('hint').strip()
            suspects.append((csv_line, sid, hint))
    return suspects


def main():
    suspects = parse_suspects(REPORT_PATH)
    if not suspects:
        print('No platform suspects found.')
        return

    # Backup CSV
    ts = __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = f"{CSV_PATH}.bak_{ts}"
    os.replace(CSV_PATH, backup)

    # Load CSV rows
    with open(backup, newline='', encoding='utf-8') as cf:
        rows = list(csv.DictReader(cf))
    headers = rows[0].keys() if rows else []

    # Build quick index by ID -> indices (in case of duplicates)
    id_to_idxs = {}
    for idx, row in enumerate(rows):
        sid = str(row.get('ID','')).strip()
        id_to_idxs.setdefault(sid, []).append(idx)

    # Apply fixes
    applied = 0
    for _csv_line, sid, hint in suspects:
        target_platform = PLATFORM_MAP.get(hint, hint)
        for idx in id_to_idxs.get(sid, []):
            if rows[idx].get('Platform') != target_platform:
                rows[idx]['Platform'] = target_platform
                applied += 1

    # Write CSV back
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as wf:
        writer = csv.DictWriter(wf, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Backup: {backup}")
    print(f"Platform fixes applied: {applied}")


if __name__ == '__main__':
    main()
