import csv
import os
from typing import Dict, List, Optional, Tuple, Any

# Service CSV columns:
# Platform,Service Category,Tier,Provider,ID,Name,Rate/1K,Min/Max,Time/Speed,Why Organic/Notes

_CSV_CACHE: Optional[List[Dict[str, str]]] = None


def _project_root() -> str:
    """Return absolute path to project root (two levels up from this file)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def _csv_path() -> str:
    """Resolve the CSV path in a Render-friendly way.
    Priority:
    1) Env var SMM_CSV_PATH if set
    2) Repo path: <project_root>/config/SMM_Services_Tiers.csv
    3) Secret files path: /etc/secrets/SMM_Services_Tiers.csv
    """
    # 1) Environment variable override
    env_path = os.environ.get('SMM_CSV_PATH')
    if env_path and os.path.exists(env_path):
        return env_path
    # 2) Repo path
    repo_path = os.path.join(_project_root(), 'config', 'SMM_Services_Tiers.csv')
    if os.path.exists(repo_path):
        return repo_path
    # 3) Secret files default location
    secrets_path = os.path.join('/etc', 'secrets', 'SMM_Services_Tiers.csv')
    return secrets_path


def _parse_rate(rate_str: str) -> Optional[float]:
    if not rate_str:
        return None
    s = rate_str.strip().replace('$', '').replace(',', '')
    try:
        return float(s)
    except Exception:
        return None


def _normalize_provider(p: str) -> str:
    p = (p or '').strip()
    if p.upper() == 'JAP' or p.lower() == 'justanotherpanel':
        return 'justanotherpanel'
    if p.replace(' ', '').lower() in ('smmkings', 'smm kings'):
        return 'smmkings'
    if p.lower() == 'peakerr':
        return 'peakerr'
    # default pass-through lowercase no spaces
    pr = p.replace(' ', '').lower()
    if pr == 'mysocialsboost':
        return 'mysocialsboost'
    return pr


def load_services_csv(refresh: bool = False) -> List[Dict[str, str]]:
    global _CSV_CACHE
    if _CSV_CACHE is not None and not refresh:
        return _CSV_CACHE

    path = _csv_path()
    rows: List[Dict[str, str]] = []
    with open(path, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        for raw in reader:
            # Normalize keys/values and SKIP surplus columns that DictReader stores under key None
            cleaned: Dict[str, Any] = {}
            for k, v in raw.items():
                if k is None:
                    # Extra data beyond header columns -> ignore
                    continue
                key = k.strip() if isinstance(k, str) else k
                val = v.strip() if isinstance(v, str) else v
                cleaned[key] = val

            row = cleaned
            row['provider_canonical'] = _normalize_provider(row.get('Provider', ''))
            row['rate_value'] = _parse_rate(row.get('Rate/1K', ''))
            # parse min/max like "10/50,000"
            mm = (row.get('Min/Max') or '').replace(',', '')
            if '/' in mm:
                try:
                    m1, m2 = mm.split('/', 1)
                    row['min_qty'] = int(m1)
                    row['max_qty'] = int(m2)
                except Exception:
                    row['min_qty'] = None
                    row['max_qty'] = None
            else:
                row['min_qty'] = None
                row['max_qty'] = None
            rows.append(row)
    _CSV_CACHE = rows
    return rows


def get_platforms() -> List[str]:
    rows = load_services_csv()
    plats = sorted({r.get('Platform', '') for r in rows if r.get('Platform')})
    return plats


def get_engagements_by_platform(platform: str) -> List[str]:
    rows = load_services_csv()
    plat = (platform or '').strip()
    engs = sorted({r.get('Service Category', '') for r in rows if r.get('Platform') == plat and r.get('Service Category')})
    return engs


def list_services(platform: str, service_category: str) -> List[Dict[str, Any]]:
    """Return all services for a platform + service category with parsed numeric fields."""
    rows = load_services_csv()
    plat_raw = (platform or '').strip()
    cat_raw = (service_category or '').strip()
    plat_norm = plat_raw.lower()
    cat_norm = cat_raw.lower()
    matches: List[Dict[str, Any]] = []
    for r in rows:
        rp = (r.get('Platform') or '').strip().lower()
        rc = (r.get('Service Category') or '').strip().lower()
        if rp != plat_norm:
            continue
        if rc != cat_norm:
            continue
        sid_raw = (r.get('ID') or '').strip()
        try:
            sid = int(sid_raw)
        except Exception:
            # skip invalid or missing IDs
            continue
        matches.append({
            'platform': r.get('Platform'),
            'service_category': r.get('Service Category'),
            'tier': r.get('Tier'),
            'provider_label': r.get('Provider'),
            'provider': r.get('provider_canonical'),
            'service_id': sid,
            'name': r.get('Name'),
            'rate_per_1k': r.get('rate_value'),
            'min_qty': r.get('min_qty'),
            'max_qty': r.get('max_qty'),
            'notes': r.get('Why Organic/Notes'),
        })
    return matches


def find_service(platform: str, service_category: str, service_id: int) -> Optional[Dict[str, Any]]:
    """Find a specific service by platform/category/service_id from CSV."""
    try:
        sid = int(service_id)
    except Exception:
        return None
    for s in list_services(platform, service_category):
        if int(s.get('service_id')) == sid:
            return s
    return None


def select_service(platform: str, service_category: str, preferred_tier: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Pick a service for given platform/category.
    Strategy:
    - If preferred_tier provided, first try rows with that Tier and lowest rate.
    - Else pick the row with the lowest rate_per_1k among all providers.
    """
    services = list_services(platform, service_category)
    if not services:
        return None

    def sort_key(s: Dict[str, Any]):
        rv = s.get('rate_per_1k')
        return float(rv) if rv is not None else float('inf')

    # try preferred tier
    if preferred_tier:
        tiered = [s for s in services if (s.get('tier') or '').lower() == preferred_tier.lower()]
        if tiered:
            return sorted(tiered, key=sort_key)[0]

    # else cheapest
    return sorted(services, key=sort_key)[0]


def to_public_service_brief(platform: str) -> Dict[str, List[str]]:
    """Return a mapping {platform: [engagement categories]} for quick UI population."""
    rows = load_services_csv()
    res: Dict[str, set] = {}
    for r in rows:
        plat = r.get('Platform')
        cat = r.get('Service Category')
        if not plat or not cat:
            continue
        res.setdefault(plat, set()).add(cat)
    return {k: sorted(list(v)) for k, v in res.items()}
