import csv
import json
import os
from typing import Dict, List, Optional, Tuple, Any

try:
    from mongo_state import (
        load_services_from_mongo,
        save_services_to_mongo,
        update_service_in_mongo,
        clear_services_cache,
        is_mongo_available
    )
    MONGO_AVAILABLE = True
except ImportError:
    MONGO_AVAILABLE = False

try:
    import profile_manager
    PROFILE_MANAGER_AVAILABLE = True
except ImportError:
    PROFILE_MANAGER_AVAILABLE = False

# Service CSV columns:
# Platform,Service Category,Tier,Provider,ID,Name,Rate/1K,Min/Max,Time/Speed,Why Organic/Notes

_CSV_CACHE: Optional[List[Dict[str, str]]] = None
_OVERRIDES_CACHE: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None
_SERVICES_JSON_CACHE: Optional[List[Dict[str, Any]]] = None


def _project_root() -> str:
    """Return absolute path to project root (one level up from app_files)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


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


def _overrides_path() -> str:
    return os.path.join(_project_root(), 'config', 'service_overrides.json')


def _services_json_path() -> str:
    """Path to the dynamic services JSON file."""
    return os.path.join(_project_root(), 'config', 'services_catalog.json')


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
    if pr in ('morethanpanel', 'morethan panel', 'mtp'):
        return 'morethanpanel'
    return pr


def _migrate_csv_to_json() -> None:
    """One-time migration: convert CSV to JSON if JSON doesn't exist or is empty."""
    json_path = _services_json_path()
    if os.path.exists(json_path):
        # Check if JSON has services already - if so, never overwrite
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get('services') and len(data.get('services', [])) > 0:
                    return  # Already has services, don't migrate
        except Exception:
            pass  # If can't read, proceed with migration
    
    csv_path = _csv_path()
    if not os.path.exists(csv_path):
        return  # No CSV to migrate
    
    print(f"Migrating services from CSV to JSON: {csv_path} -> {json_path}")
    rows = load_services_csv(refresh=True)
    services_data = []
    for r in rows:
        services_data.append({
            'platform': r.get('Platform'),
            'service_category': r.get('Service Category'),
            'tier': r.get('Tier'),
            'provider': r.get('provider_canonical'),
            'provider_label': r.get('Provider'),
            'service_id': int(r.get('ID')) if r.get('ID') and r.get('ID').strip() else None,
            'name': r.get('Name'),
            'rate_per_1k': r.get('rate_value'),
            'min_qty': r.get('min_qty'),
            'max_qty': r.get('max_qty'),
            'notes': r.get('Why Organic/Notes'),
        })
    
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({'services': services_data, 'version': '1.0'}, f, indent=2)
    print(f"Migration complete. {len(services_data)} services migrated.")


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


def _normalize_key_pair(platform: str, engagement: str) -> Tuple[str, str]:
    return (platform or '').strip(), (engagement or '').strip()


def _load_overrides_cache(refresh: bool = False) -> Dict[str, Dict[str, Dict[str, Any]]]:
    global _OVERRIDES_CACHE
    if _OVERRIDES_CACHE is not None and not refresh:
        return _OVERRIDES_CACHE

    path = _overrides_path()
    if not os.path.exists(path):
        _OVERRIDES_CACHE = {}
        return _OVERRIDES_CACHE

    try:
        with open(path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
            # Ensure keys remain str->dict->dict with normalized structure
            normalized: Dict[str, Dict[str, Dict[str, Any]]] = {}
            for plat, engagements in (raw or {}).items():
                if not isinstance(engagements, dict):
                    continue
                for eng, data in engagements.items():
                    if not isinstance(data, dict):
                        continue
                    plat_norm, eng_norm = _normalize_key_pair(plat, eng)
                    entry = {
                        'service_id': int(data.get('service_id')) if data.get('service_id') is not None else None,
                        'provider': data.get('provider'),
                        'provider_label': data.get('provider_label'),
                        'name': data.get('name'),
                    }
                    normalized.setdefault(plat_norm, {})[eng_norm] = entry
            _OVERRIDES_CACHE = normalized
    except (json.JSONDecodeError, OSError):
        _OVERRIDES_CACHE = {}
    return _OVERRIDES_CACHE


def _save_overrides_cache(data: Dict[str, Dict[str, Dict[str, Any]]]) -> None:
    path = _overrides_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    global _OVERRIDES_CACHE
    _OVERRIDES_CACHE = data


def clear_overrides_cache() -> None:
    global _OVERRIDES_CACHE
    _OVERRIDES_CACHE = None


def _load_services_json(refresh: bool = False) -> List[Dict[str, Any]]:
    """Load services from MongoDB (primary) or JSON catalog (fallback). Migrates data if needed."""
    global _SERVICES_JSON_CACHE
    if _SERVICES_JSON_CACHE is not None and not refresh:
        return _SERVICES_JSON_CACHE
    
    # Try MongoDB first
    if MONGO_AVAILABLE and is_mongo_available():
        mongo_services = load_services_from_mongo(refresh=refresh)
        if mongo_services is not None and len(mongo_services) > 0:
            _SERVICES_JSON_CACHE = _normalize_services(mongo_services)
            return _SERVICES_JSON_CACHE
        # MongoDB available but empty - try to migrate from JSON
        json_services = _load_services_from_json_file()
        if json_services:
            save_services_to_mongo(json_services)
            _SERVICES_JSON_CACHE = json_services
            print(f"✅ Migrated {len(json_services)} services from JSON to MongoDB")
            return _SERVICES_JSON_CACHE
    
    # Fallback to JSON file
    json_services = _load_services_from_json_file()
    _SERVICES_JSON_CACHE = json_services
    return _SERVICES_JSON_CACHE


def _normalize_services(services: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure all services have proper types."""
    normalized = []
    for svc in services:
        if not isinstance(svc, dict):
            continue
        normalized.append({
            'platform': svc.get('platform'),
            'service_category': svc.get('service_category'),
            'tier': svc.get('tier'),
            'provider': svc.get('provider'),
            'provider_label': svc.get('provider_label'),
            'service_id': int(svc['service_id']) if svc.get('service_id') is not None else None,
            'name': svc.get('name'),
            'rate_per_1k': float(svc['rate_per_1k']) if svc.get('rate_per_1k') is not None else None,
            'min_qty': int(svc['min_qty']) if svc.get('min_qty') is not None else None,
            'max_qty': int(svc['max_qty']) if svc.get('max_qty') is not None else None,
            'notes': svc.get('notes'),
        })
    return normalized


def _load_services_from_json_file() -> List[Dict[str, Any]]:
    """Load services directly from JSON file (without MongoDB)."""
    # Ensure migration from CSV happened
    _migrate_csv_to_json()
    
    json_path = _services_json_path()
    if not os.path.exists(json_path):
        return []
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            services = data.get('services', [])
            return _normalize_services(services)
    except (json.JSONDecodeError, OSError, KeyError, ValueError) as e:
        print(f"Error loading services JSON: {e}")
        return []


def _save_services_json(services: List[Dict[str, Any]]) -> None:
    """Save services to MongoDB (primary) and JSON catalog (backup)."""
    global _SERVICES_JSON_CACHE
    
    # Save to MongoDB first (primary storage)
    if MONGO_AVAILABLE and is_mongo_available():
        save_services_to_mongo(services)
    
    # Also save to JSON file as backup
    json_path = _services_json_path()
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({'services': services, 'version': '1.0'}, f, indent=2)
    _SERVICES_JSON_CACHE = services


def get_override(platform: str, engagement: str) -> Optional[Dict[str, Any]]:
    plat_norm, eng_norm = _normalize_key_pair(platform, engagement)
    overrides = _load_overrides_cache()
    return overrides.get(plat_norm, {}).get(eng_norm)


def set_override(platform: str, engagement: str, service: Dict[str, Any]) -> Dict[str, Any]:
    """Update the main services catalog directly - replaces the selected service for this platform/engagement."""
    services = _load_services_json(refresh=True)
    
    service_id = int(service.get('service_id')) if service.get('service_id') is not None else None
    provider = service.get('provider')
    
    # STRATEGY: For a given platform+engagement, we want ONE preferred service
    # Remove any existing entries for this platform+engagement, then add the new one
    # This ensures the catalog always reflects your current choice
    
    # Remove all existing entries for this platform+engagement combo
    services = [s for s in services if not (
        s.get('platform') == platform and 
        s.get('service_category') == engagement
    )]
    
    # Add the new service entry
    new_service = {
        'platform': platform,
        'service_category': engagement,
        'tier': service.get('tier'),
        'provider': provider,
        'provider_label': service.get('provider_label') or provider,
        'service_id': service_id,
        'name': service.get('name'),
        'rate_per_1k': float(service.get('rate_per_1k')) if service.get('rate_per_1k') is not None else None,
        'min_qty': service.get('min_qty'),
        'max_qty': service.get('max_qty'),
        'notes': service.get('notes'),
    }
    services.append(new_service)
    
    _save_services_json(services)
    
    # Auto-update all profiles that use this platform+engagement
    updated_profiles = update_profiles_for_service_change(platform, engagement, new_service)
    if updated_profiles:
        print(f"✅ Auto-updated {len(updated_profiles)} profile(s) for {platform}/{engagement}")
    
    # Return the created service for API response
    return {
        'service_id': service_id,
        'provider': provider,
        'provider_label': new_service.get('provider_label'),
        'name': new_service.get('name'),
        'min_qty': new_service.get('min_qty'),
        'max_qty': new_service.get('max_qty'),
        'rate_per_1k': new_service.get('rate_per_1k'),
    }


def update_profiles_for_service_change(platform: str, engagement: str, new_service: Dict[str, Any]) -> List[str]:
    """
    Update all profiles that have engagements matching the given platform+engagement.
    Updates service_id, rate_per_1k, and enforces min_quantity >= service min_qty.
    Returns list of updated profile names.
    """
    if not PROFILE_MANAGER_AVAILABLE:
        print("Warning: profile_manager not available, cannot auto-update profiles")
        return []
    
    try:
        profiles = profile_manager.load_profiles()
    except Exception as e:
        print(f"Warning: Could not load profiles for auto-update: {e}")
        return []
    
    if not profiles:
        return []
    
    updated_profile_names = []
    new_service_id = new_service.get('service_id')
    new_rate = new_service.get('rate_per_1k')
    new_min_qty = new_service.get('min_qty')
    
    # Normalize engagement name for comparison (case-insensitive)
    engagement_lower = (engagement or '').lower()
    platform_lower = (platform or '').lower()
    
    for profile_name, profile_data in profiles.items():
        if not isinstance(profile_data, dict):
            continue
        
        engagements = profile_data.get('engagements', [])
        if not isinstance(engagements, list):
            continue
        
        profile_modified = False
        
        for eng in engagements:
            if not isinstance(eng, dict):
                continue
            
            eng_type = (eng.get('type') or '').lower()
            eng_platform = (eng.get('platform') or '').lower()
            
            # Check if this engagement matches the updated service
            if eng_type == engagement_lower and eng_platform == platform_lower:
                # Update service_id
                if new_service_id is not None:
                    eng['service_id'] = new_service_id
                    profile_modified = True
                
                # Update rate_per_1k
                if new_rate is not None:
                    eng['rate_per_1k'] = new_rate
                    profile_modified = True
                
                # Enforce minimum quantity
                if new_min_qty is not None:
                    new_min_qty_int = int(new_min_qty)
                    
                    # Update min_quantity if it's less than service minimum
                    current_min = eng.get('min_quantity')
                    if current_min is not None and int(current_min) < new_min_qty_int:
                        eng['min_quantity'] = new_min_qty_int
                        profile_modified = True
                        print(f"  - {profile_name}: Updated min_quantity for {engagement} from {current_min} to {new_min_qty_int}")
                    
                    # Update fixed_quantity if it's less than service minimum
                    fixed_qty = eng.get('fixed_quantity')
                    if fixed_qty is not None and int(fixed_qty) < new_min_qty_int:
                        eng['fixed_quantity'] = new_min_qty_int
                        profile_modified = True
                        print(f"  - {profile_name}: Updated fixed_quantity for {engagement} from {fixed_qty} to {new_min_qty_int}")
                    
                    # Update max_quantity if it's less than min_quantity (to keep valid range)
                    current_max = eng.get('max_quantity')
                    if current_max is not None and eng.get('min_quantity') is not None:
                        if int(current_max) < int(eng.get('min_quantity')):
                            eng['max_quantity'] = int(eng.get('min_quantity'))
                            profile_modified = True
                            print(f"  - {profile_name}: Updated max_quantity for {engagement} to match min_quantity")
        
        if profile_modified:
            updated_profile_names.append(profile_name)
    
    # Save profiles if any were modified
    if updated_profile_names:
        try:
            profile_manager.save_profiles(profiles)
            print(f"✅ Saved updated profiles: {', '.join(updated_profile_names)}")
        except Exception as e:
            print(f"Warning: Could not save updated profiles: {e}")
            return []
    
    return updated_profile_names


def _service_to_public(service: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not service:
        return None
    return {
        'platform': service.get('platform'),
        'engagement': service.get('service_category'),
        'provider': service.get('provider'),
        'provider_label': service.get('provider_label'),
        'service_id': service.get('service_id'),
        'name': service.get('name'),
        'rate_per_1k': service.get('rate_per_1k'),
        'min_qty': service.get('min_qty'),
        'max_qty': service.get('max_qty'),
        'notes': service.get('notes'),
    }


def clear_override_entry(platform: str, engagement: str) -> bool:
    plat_norm, eng_norm = _normalize_key_pair(platform, engagement)
    overrides = _load_overrides_cache()
    if plat_norm not in overrides:
        return False
    if eng_norm not in overrides[plat_norm]:
        return False
    del overrides[plat_norm][eng_norm]
    if not overrides[plat_norm]:
        del overrides[plat_norm]
    _save_overrides_cache(overrides)
    return True


def list_provider_options(platform: str, engagement: str) -> List[Dict[str, Any]]:
    services = list_services(platform, engagement)
    options: Dict[Tuple[str, int], Dict[str, Any]] = {}
    for svc in services:
        key = (svc.get('provider'), int(svc.get('service_id')))
        if key in options:
            continue
        options[key] = {
            'provider': svc.get('provider'),
            'provider_label': svc.get('provider_label'),
            'service_id': int(svc.get('service_id')),
            'name': svc.get('name'),
            'rate_per_1k': svc.get('rate_per_1k'),
            'min_qty': svc.get('min_qty'),
            'max_qty': svc.get('max_qty'),
            'notes': svc.get('notes'),
        }
    return sorted(options.values(), key=lambda item: (item.get('provider') or '', item.get('service_id') or 0))


def get_effective_service(platform: str, engagement: str, preferred_tier: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get the best matching service from the catalog (JSON-based)."""
    # Simply use select_service which now reads from JSON
    if preferred_tier:
        svc = select_service(platform, engagement, preferred_tier)
        if svc:
            return svc
    return select_service(platform, engagement)


def get_default_service_for_display(platform: str, engagement: str) -> Optional[Dict[str, Any]]:
    """Get the default service (cheapest from CSV) for display purposes on Services page."""
    return select_service(platform, engagement)


def get_platforms() -> List[str]:
    services = _load_services_json()
    plats = sorted({s.get('platform', '') for s in services if s.get('platform')})
    return plats


def get_engagements_by_platform(platform: str) -> List[str]:
    services = _load_services_json()
    plat = (platform or '').strip()
    engs = sorted({s.get('service_category', '') for s in services if s.get('platform') == plat and s.get('service_category')})
    return engs


def list_services(platform: str, service_category: str) -> List[Dict[str, Any]]:
    """Return all services for a platform + service category with parsed numeric fields."""
    # Use JSON catalog instead of CSV
    services = _load_services_json()
    plat_raw = (platform or '').strip()
    cat_raw = (service_category or '').strip()
    plat_norm = plat_raw.lower()
    cat_norm = cat_raw.lower()
    
    matches = []
    for svc in services:
        rp = (svc.get('platform') or '').strip().lower()
        rc = (svc.get('service_category') or '').strip().lower()
        if rp != plat_norm:
            continue
        if rc != cat_norm:
            continue
        if svc.get('service_id') is None:
            continue
        matches.append(svc)
    
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
    services = _load_services_json()
    res: Dict[str, set] = {}
    for s in services:
        plat = s.get('platform')
        cat = s.get('service_category')
        if not plat or not cat:
            continue
        res.setdefault(plat, set()).add(cat)
    return {k: sorted(list(v)) for k, v in res.items()}
