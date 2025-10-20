import datetime
import time
import random
import traceback
from typing import Optional, Callable

import services_catalog as sc
import providers_api as pa

# Type alias for callbacks
StatusCb = Callable[[str, str, Optional[str]], None]
SaveHistoryCb = Callable[[dict], None]


def run_single_api_order(platform: str, engagement: str, link: str, quantity: int,
                         job_id: str, status_update_callback: StatusCb,
                         save_history_callback: SaveHistoryCb, requested_stops: set):
    start_time = datetime.datetime.now()
    success = False
    message = ''

    try:
        status_update_callback(job_id, 'running', f"Selecting service for {platform} / {engagement}...")
        svc = sc.select_service(platform, engagement)
        if not svc:
            message = f"No service found for {platform} / {engagement} in CSV."
            status_update_callback(job_id, 'failed', message)
            return

        # Validate quantity against CSV min/max if available
        min_q = svc.get('min_qty')
        max_q = svc.get('max_qty')
        if min_q is not None and quantity < int(min_q):
            message = f"Minimum quantity for {platform} {engagement} is {min_q}."
            status_update_callback(job_id, 'failed', message)
            return
        if max_q is not None and quantity > int(max_q):
            message = f"Maximum quantity for {platform} {engagement} is {max_q}."
            status_update_callback(job_id, 'failed', message)
            return

        provider = svc['provider']
        service_id = int(svc['service_id'])
        status_update_callback(job_id, 'running', f"Ordering via {provider} (service {service_id})...")

        # Compute cost from CSV rate
        unit_rate = svc.get('rate_per_1k')
        try:
            unit_rate_f = float(unit_rate) if unit_rate is not None else None
        except Exception:
            unit_rate_f = None
        total_cost = round((unit_rate_f * int(quantity) / 1000.0), 6) if unit_rate_f is not None else None

        resp = pa.add_order(provider, service_id, link, int(quantity))
        # Many SMM panels return { "order": <id> } on success
        if isinstance(resp, dict) and 'order' in resp:
            success = True
            message = f"Order placed: {resp['order']} via {provider}."
            status_update_callback(job_id, 'success', message)
        else:
            # Record raw response for visibility
            message = f"Order response: {resp}"
            status_update_callback(job_id, 'failed', message)

    except Exception as e:
        message = f"API order error: {e}"
        traceback.print_exc()
        status_update_callback(job_id, 'failed', message)
    finally:
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        history_entry = {
            'job_id': job_id,
            'type': 'Single Promo (API)',
            'profile_name': f"{platform} - {engagement}",
            'link': link,
            'quantity': quantity,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': round(duration, 2),
            'status': 'Success' if success else 'Failed',
            'message': message,
            # Provider/order info for live-status polling
            'provider': provider if success else None,
            'order_id': (resp.get('order') if (isinstance(resp, dict) and 'order' in resp) else None) if 'resp' in locals() else None,
            'unit_rate_per_1k': unit_rate_f,
            'total_cost': total_cost,
        }
        try:
            save_history_callback(history_entry)
        except Exception:
            traceback.print_exc()


def run_order_by_service(platform: str, engagement: str, service_id: int, link: str, quantity: int,
                         job_id: str, status_update_callback: StatusCb,
                         save_history_callback: SaveHistoryCb, requested_stops: set):
    """Place an order for an explicitly selected service with strict min/max validation."""
    start_time = datetime.datetime.now()
    success = False
    message = ''

    try:
        status_update_callback(job_id, 'running', f"Validating service {service_id} for {platform}/{engagement}...")
        svc = sc.find_service(platform, engagement, service_id)
        if not svc:
            message = f"Service {service_id} not found for {platform}/{engagement}."
            status_update_callback(job_id, 'failed', message)
            return

        # Strict min/max bounds from CSV
        min_q = svc.get('min_qty')
        max_q = svc.get('max_qty')
        if min_q is not None and quantity < int(min_q):
            message = f"Minimum quantity for this service is {min_q}."
            status_update_callback(job_id, 'failed', message)
            return
        if max_q is not None and quantity > int(max_q):
            message = f"Maximum quantity for this service is {max_q}."
            status_update_callback(job_id, 'failed', message)
            return

        provider = svc['provider']
        sid = int(svc['service_id'])
        status_update_callback(job_id, 'running', f"Ordering via {provider} (service {sid})...")

        # Compute cost from CSV rate
        unit_rate = svc.get('rate_per_1k')
        try:
            unit_rate_f = float(unit_rate) if unit_rate is not None else None
        except Exception:
            unit_rate_f = None
        total_cost = round((unit_rate_f * int(quantity) / 1000.0), 6) if unit_rate_f is not None else None

        resp = pa.add_order(provider, sid, link, int(quantity))
        if isinstance(resp, dict) and 'order' in resp:
            success = True
            message = f"Order placed: {resp['order']} via {provider}."
            status_update_callback(job_id, 'success', message)
        else:
            message = f"Order response: {resp}"
            status_update_callback(job_id, 'failed', message)

    except Exception as e:
        message = f"API order error: {e}"
        traceback.print_exc()
        status_update_callback(job_id, 'failed', message)
    finally:
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        history_entry = {
            'job_id': job_id,
            'type': 'Single Promo (API by service)',
            'profile_name': f"{platform} - {engagement} - #{service_id}",
            'link': link,
            'quantity': quantity,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': round(duration, 2),
            'status': 'Success' if success else 'Failed',
            'message': message,
            'provider': provider if success else None,
            'order_id': (resp.get('order') if (isinstance(resp, dict) and 'order' in resp) else None) if 'resp' in locals() else None,
            'unit_rate_per_1k': unit_rate_f,
            'total_cost': total_cost,
        }
        try:
            save_history_callback(history_entry)
        except Exception:
            traceback.print_exc()


def run_profile_api_promo(profile_name: str, profile_data: dict, link: str,
                          job_id: str, status_update_callback: StatusCb,
                          save_history_callback: SaveHistoryCb, requested_stops: set,
                          platform_filter: Optional[str] = None):
    """API-based auto-promo job using CSV providers/services.

    profile_data schema (from frontend):
      {
        engagements: [
          { type, platform?, use_random_quantity, fixed_quantity, min_quantity, max_quantity, loops }
        ],
        loop_settings: { loops, delay, random_delay, min_delay, max_delay }
      }
    """
    start_time = datetime.datetime.now()
    success = True
    messages = []
    total_orders = 0
    placed_orders = []  # list of {provider, order_id, engagement, quantity}

    def stopped():
        return job_id in requested_stops

    try:
        status_update_callback(job_id, 'running', f"Starting API auto promo: {profile_name}")

        engagements = list(profile_data.get('engagements') or [])
        loop_settings = dict(profile_data.get('loop_settings') or {})
        main_loops = int(loop_settings.get('loops') or 1)
        fixed_delay = float(loop_settings.get('delay') or 0)
        use_random_delay = bool(loop_settings.get('random_delay') or False)
        min_delay = float(loop_settings.get('min_delay') or 0)
        max_delay = float(loop_settings.get('max_delay') or 0)

        for loop_num in range(1, main_loops + 1):
            if stopped():
                messages.append(f"Stopped before loop {loop_num}")
                success = False
                break
            status_update_callback(job_id, 'running', f"Loop {loop_num}/{main_loops}...")

            for eng in engagements:
                if stopped():
                    messages.append(f"Stopped during loop {loop_num}")
                    success = False
                    break

                eng_type = (eng.get('type') or '').strip()
                if not eng_type:
                    continue

                # Respect per-engagement participation limit
                participation_loops = int(eng.get('loops') or 1)
                if loop_num > participation_loops:
                    continue

                # Platform from saved engagement; fallback to Instagram
                platform = (eng.get('platform') or '').strip() or 'Instagram'
                if platform_filter and platform != platform_filter:
                    continue

                # Determine quantity
                qty = 0
                if eng.get('use_random_quantity'):
                    try:
                        mn = int(eng.get('min_quantity') or 0)
                        mx = int(eng.get('max_quantity') or 0)
                        if mn > 0 and mx >= mn:
                            qty = random.randint(mn, mx)
                    except Exception:
                        qty = 0
                else:
                    try:
                        qf = int(eng.get('fixed_quantity') or 0)
                        if qf > 0:
                            qty = qf
                    except Exception:
                        qty = 0

                if qty <= 0:
                    messages.append(f"Skip {eng_type}: no valid quantity in loop {loop_num}")
                    continue

                status_update_callback(job_id, 'running', f"Ordering {qty} {eng_type} on {platform}...")

                # Select service from CSV
                svc = sc.select_service(platform, eng_type)
                if not svc:
                    messages.append(f"No CSV service for {platform}/{eng_type}")
                    success = False
                    continue

                # Validate against selected service min/max
                min_q = svc.get('min_qty')
                max_q = svc.get('max_qty')
                if min_q is not None and qty < int(min_q):
                    messages.append(f"Qty {qty} < min {min_q} for {platform}/{eng_type}")
                    success = False
                    continue
                if max_q is not None and qty > int(max_q):
                    messages.append(f"Qty {qty} > max {max_q} for {platform}/{eng_type}")
                    success = False
                    continue

                provider = svc['provider']
                service_id = int(svc['service_id'])
                try:
                    # Compute estimated cost
                    unit_rate = svc.get('rate_per_1k')
                    try:
                        unit_rate_f = float(unit_rate) if unit_rate is not None else None
                    except Exception:
                        unit_rate_f = None
                    item_cost = round((unit_rate_f * int(qty) / 1000.0), 6) if unit_rate_f is not None else None

                    resp = pa.add_order(provider, service_id, link, int(qty))
                    if isinstance(resp, dict) and 'order' in resp:
                        total_orders += 1
                        messages.append(f"OK {eng_type} -> {resp['order']}@{provider}")
                        try:
                            placed_orders.append({'provider': provider, 'order_id': resp['order'], 'engagement': eng_type, 'quantity': int(qty), 'unit_rate_per_1k': unit_rate_f, 'cost': item_cost})
                        except Exception:
                            pass
                    else:
                        messages.append(f"Failed {eng_type} -> {resp}")
                        success = False
                except Exception as e:
                    messages.append(f"Error {eng_type}: {e}")
                    success = False

            if stopped():
                break

            # Delay between loops
            if loop_num < main_loops:
                delay_sec = 0.0
                if use_random_delay and max_delay >= min_delay and max_delay > 0:
                    delay_sec = random.uniform(min_delay, max_delay)
                else:
                    delay_sec = max(0.0, fixed_delay)

                if delay_sec > 0:
                    status_update_callback(job_id, 'running', f"Delay {delay_sec:.1f}s before next loop...")
                    slept = 0.0
                    step = 0.5
                    while slept < delay_sec:
                        if stopped():
                            break
                        time.sleep(step)
                        slept += step
                if stopped():
                    messages.append("Stopped during delay")
                    success = False
                    break

        final_msg = f"Orders: {total_orders}. " + "; ".join(messages[-10:])
        status_update_callback(job_id, 'success' if success else 'failed', final_msg)
    except Exception as e:
        success = False
        final_msg = f"Auto API error: {e}"
        traceback.print_exc()
        status_update_callback(job_id, 'failed', final_msg)
    finally:
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        # Aggregate cost
        try:
            total_cost_sum = round(sum([o.get('cost') or 0 for o in placed_orders]), 6)
        except Exception:
            total_cost_sum = None

        history_entry = {
            'job_id': job_id,
            'type': 'Auto Promo (API)',
            'profile_name': profile_name,
            'link': link,
            'quantity': None,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': round(duration, 2),
            'status': 'Success' if success else 'Failed',
            'message': final_msg,
            'orders': placed_orders,
            'total_cost': total_cost_sum,
        }
        try:
            save_history_callback(history_entry)
        except Exception:
            traceback.print_exc()
