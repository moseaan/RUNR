import os
from typing import Dict, Optional, Any
import requests

# Base URLs for providers
BASE_URLS = {
    'justanotherpanel': 'https://justanotherpanel.com/api/v2',
    'peakerr': 'https://peakerr.com/api/v2',
    'smmkings': 'https://smmkings.com/api/v2',
    'mysocialsboost': 'https://mysocialsboost.com/api/v2',
}

_KEY_CACHE: Dict[str, Optional[str]] = {}


def _project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def _config_path(filename: str) -> str:
    return os.path.join(_project_root(), 'config', filename)


def _normalize_provider(p: str) -> str:
    p = (p or '').strip()
    if p.upper() == 'JAP' or p.lower() == 'justanotherpanel':
        return 'justanotherpanel'
    if p.replace(' ', '').lower() in ('smmkings', 'smm kings'):
        return 'smmkings'
    if p.lower() == 'peakerr':
        return 'peakerr'
    if p.replace(' ', '').lower() == 'mysocialsboost':
        return 'mysocialsboost'
    return p.replace(' ', '').lower()


def _read_key_from_file(path: str) -> Optional[str]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            key = f.read().strip()
            return key or None
    except Exception:
        return None


def get_api_key(provider: str) -> Optional[str]:
    prov = _normalize_provider(provider)
    if prov in _KEY_CACHE:
        return _KEY_CACHE[prov]

    key: Optional[str] = None
    if prov == 'justanotherpanel':
        key = _read_key_from_file(_config_path('justanotherpanel_api_key.txt'))
    elif prov == 'peakerr':
        key = _read_key_from_file(_config_path('peakerr_api_key.txt'))
    elif prov == 'smmkings':
        key = _read_key_from_file(_config_path('smm_kings_api_key.txt'))
    elif prov == 'mysocialsboost':
        key = _read_key_from_file(_config_path('mysocialsboost_api_key.txt'))

    _KEY_CACHE[prov] = key
    return key


def _post(provider: str, data: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
    prov = _normalize_provider(provider)
    base = BASE_URLS.get(prov)
    if not base:
        raise ValueError(f"Unknown provider: {provider}")
    key = get_api_key(prov)
    if not key:
        raise ValueError(f"Missing API key for provider: {provider}")

    payload = {
        'key': key,
        **data,
    }
    # Most SMM panels expect form-encoded POST
    resp = requests.post(base, data=payload, timeout=timeout)
    resp.raise_for_status()
    try:
        return resp.json()
    except Exception:
        # Return text fallback
        return {'raw': resp.text}


def get_balance(provider: str) -> Dict[str, Any]:
    return _post(provider, {'action': 'balance'})


def add_order(provider: str, service_id: int, link: str, quantity: int, runs: Optional[int] = None, interval: Optional[int] = None) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        'action': 'add',
        'service': service_id,
        'link': link,
        'quantity': quantity,
    }
    if runs is not None:
        data['runs'] = runs
    if interval is not None:
        data['interval'] = interval
    return _post(provider, data)


def order_status(provider: str, order_id: int) -> Dict[str, Any]:
    return _post(provider, {'action': 'status', 'order': order_id})


# --- Extended helpers supported by most SMM panels ---
def order_status_multiple(provider: str, order_ids: Any) -> Dict[str, Any]:
    """Query multiple orders' status. order_ids can be a list/tuple or comma string."""
    if isinstance(order_ids, (list, tuple)):
        ids_val = ','.join(str(int(i)) for i in order_ids)
    else:
        ids_val = str(order_ids)
    return _post(provider, {'action': 'status', 'orders': ids_val})


def list_services(provider: str) -> Any:
    """Fetch services list for a provider."""
    return _post(provider, {'action': 'services'})


def create_refill(provider: str, order_id: int) -> Dict[str, Any]:
    return _post(provider, {'action': 'refill', 'order': int(order_id)})


def create_refill_multiple(provider: str, order_ids: Any) -> Any:
    if isinstance(order_ids, (list, tuple)):
        ids_val = ','.join(str(int(i)) for i in order_ids)
    else:
        ids_val = str(order_ids)
    return _post(provider, {'action': 'refill', 'orders': ids_val})


def refill_status(provider: str, refill_id: int) -> Dict[str, Any]:
    return _post(provider, {'action': 'refill_status', 'refill': int(refill_id)})


def refill_status_multiple(provider: str, refill_ids: Any) -> Any:
    if isinstance(refill_ids, (list, tuple)):
        ids_val = ','.join(str(int(i)) for i in refill_ids)
    else:
        ids_val = str(refill_ids)
    return _post(provider, {'action': 'refill_status', 'refills': ids_val})


def cancel_orders(provider: str, order_ids: Any) -> Any:
    if isinstance(order_ids, (list, tuple)):
        ids_val = ','.join(str(int(i)) for i in order_ids)
    else:
        ids_val = str(order_ids)
    return _post(provider, {'action': 'cancel', 'orders': ids_val})
