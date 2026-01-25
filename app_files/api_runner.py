import datetime
import time
import random
import traceback
import os
import json
from typing import Optional, Callable

import services_catalog as sc
import providers_api as pa

# Type alias for callbacks
StatusCb = Callable[[str, str, Optional[str]], None]
SaveHistoryCb = Callable[[dict], None]

# MongoDB state persistence - import with fallback to file-based
try:
    import mongo_state
    USE_MONGO = mongo_state.is_mongo_available()
except ImportError:
    USE_MONGO = False
    mongo_state = None

# Fallback file-based state persistence
STATE_FILE = os.path.join(os.path.dirname(__file__), 'data', 'job_states.json')

def save_job_state(job_id: str, state: dict):
    """Save job execution state for resume on restart (uses MongoDB if available)."""
    # Try MongoDB first
    if USE_MONGO and mongo_state:
        if mongo_state.save_job_state(job_id, state):
            return
    
    # Fallback to file-based storage
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        states = {}
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                states = json.load(f)
        states[job_id] = {
            **state,
            'last_updated': datetime.datetime.now().isoformat()
        }
        with open(STATE_FILE, 'w') as f:
            json.dump(states, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save job state for {job_id}: {e}")

def load_job_state(job_id: str) -> dict:
    """Load saved job execution state (uses MongoDB if available)."""
    # Try MongoDB first
    if USE_MONGO and mongo_state:
        state = mongo_state.load_job_state(job_id)
        if state:
            return state
    
    # Fallback to file-based storage
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                states = json.load(f)
            return states.get(job_id, {})
    except Exception as e:
        print(f"Warning: Could not load job state for {job_id}: {e}")
    return {}

def clear_job_state(job_id: str):
    """Clear job state after completion (uses MongoDB if available)."""
    # Try MongoDB first
    if USE_MONGO and mongo_state:
        mongo_state.clear_job_state(job_id)
    
    # Also clear from file-based storage for consistency
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                states = json.load(f)
            if job_id in states:
                del states[job_id]
                with open(STATE_FILE, 'w') as f:
                    json.dump(states, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not clear job state for {job_id}: {e}")


def run_single_api_order(platform: str, engagement: str, link: str, quantity: int,
                         job_id: str, status_update_callback: StatusCb,
                         save_history_callback: SaveHistoryCb, requested_stops: set):
    start_time = datetime.datetime.now()
    success = False
    message = ''

    try:
        status_update_callback(job_id, 'running', f"Selecting service for {platform} / {engagement}...")
        svc = sc.get_effective_service(platform, engagement)
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
            'type': 'Single Promo',
            'profile_name': f"{platform} - {engagement}",
            'platform': platform,
            'engagement': engagement,
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
            'type': 'Single Promo',
            'profile_name': f"{platform} - {engagement} - #{service_id}",
            'platform': platform,
            'engagement': engagement,
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
    # Load saved state for resume capability
    saved_state = load_job_state(job_id)
    start_loop = saved_state.get('current_loop', 1) if saved_state else 1
    start_time = datetime.datetime.fromisoformat(saved_state['start_time']) if saved_state.get('start_time') else datetime.datetime.now()
    
    success = True
    final_success = False  # Will be set properly at end of try block
    messages = saved_state.get('messages', []) if saved_state else []
    total_orders = saved_state.get('total_orders', 0) if saved_state else 0
    placed_orders = saved_state.get('placed_orders', []) if saved_state else []

    def stopped():
        return job_id in requested_stops

    try:
        if start_loop == 1:
            status_update_callback(job_id, 'running', f"Starting API auto promo: {profile_name}")
        else:
            status_update_callback(job_id, 'running', f"Resuming API auto promo: {profile_name} from loop {start_loop}")
            print(f"[Resume] Job {job_id} resuming from loop {start_loop}")

        engagements = list(profile_data.get('engagements') or [])
        loop_settings = dict(profile_data.get('loop_settings') or {})
        main_loops = int(loop_settings.get('loops') or 1)
        fixed_delay = float(loop_settings.get('delay') or 0)
        use_random_delay = bool(loop_settings.get('random_delay') or False)
        min_delay = float(loop_settings.get('min_delay') or 0)
        max_delay = float(loop_settings.get('max_delay') or 0)

        for loop_num in range(start_loop, main_loops + 1):
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

                # Select service using explicit service_id if provided; else use effective service (respects overrides)
                svc = None
                sid_val = eng.get('service_id')
                if sid_val is not None:
                    try:
                        sid_int = int(sid_val)
                        svc = sc.find_service(platform, eng_type, sid_int)
                    except Exception:
                        svc = None
                if not svc:
                    svc = sc.get_effective_service(platform, eng_type)
                if not svc:
                    messages.append(f"No CSV service for {platform}/{eng_type}")
                    # Don't fail the whole job - just skip this engagement
                    continue

                # Validate against selected service min/max
                min_q = svc.get('min_qty')
                max_q = svc.get('max_qty')
                if min_q is not None and qty < int(min_q):
                    messages.append(f"Qty {qty} < min {min_q} for {platform}/{eng_type}")
                    # Don't fail the whole job - just skip this engagement
                    continue
                if max_q is not None and qty > int(max_q):
                    messages.append(f"Qty {qty} > max {max_q} for {platform}/{eng_type}")
                    # Don't fail the whole job - just skip this engagement
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

                    order_start = datetime.datetime.now()
                    resp = pa.add_order(provider, service_id, link, int(qty))
                    order_end = datetime.datetime.now()
                    if isinstance(resp, dict) and 'order' in resp:
                        total_orders += 1
                        order_id_str = str(resp['order'])
                        messages.append(f"OK {eng_type} -> {order_id_str}@{provider}")
                        try:
                            placed_orders.append({'provider': provider, 'order_id': order_id_str, 'engagement': eng_type, 'quantity': int(qty), 'unit_rate_per_1k': unit_rate_f, 'cost': item_cost})
                        except Exception:
                            pass
                        # Save state after each order
                        save_job_state(job_id, {
                            'current_loop': loop_num,
                            'total_loops': main_loops,
                            'start_time': start_time.isoformat(),
                            'messages': messages,
                            'total_orders': total_orders,
                            'placed_orders': placed_orders,
                            'profile_name': profile_name,
                            'link': link,
                            'platform_filter': platform_filter
                        })
                        try:
                            order_history_entry = {
                                'job_id': f"{job_id}::order::{order_id_str}",
                                'parent_job_id': job_id,
                                'type': 'single',
                                'profile_name': profile_name,
                                'platform': platform,
                                'engagement': eng_type,
                                'link': link,
                                'quantity': int(qty),
                                'start_time': order_start.isoformat(),
                                'end_time': order_end.isoformat(),
                                'timestamp': order_end.isoformat(),
                                'duration_seconds': round((order_end - order_start).total_seconds(), 2),
                                'status': 'Success',
                                'message': f"Auto promo order placed via {provider} (service {service_id}).",
                                'provider': provider,
                                'order_id': order_id_str,
                                'unit_rate_per_1k': unit_rate_f,
                                'total_cost': item_cost
                            }
                            save_history_callback(order_history_entry)
                        except Exception:
                            traceback.print_exc()
                    else:
                        messages.append(f"Failed {eng_type} -> {resp}")
                        # API returned error - log but continue with other engagements
                        # Don't break the entire loop for one failed order
                        continue
                except Exception as e:
                    messages.append(f"Error {eng_type}: {e}")
                    # Log the error but continue with other engagements
                    # Don't break the entire loop for one failed order
                    continue

            if stopped():
                break
            # Removed: if not success: break
            # We no longer break on individual engagement failures
            # The job continues through all loops even if some orders fail

            # Delay between loops
            if loop_num < main_loops:
                delay_sec = 0.0
                if use_random_delay and max_delay >= min_delay and max_delay > 0:
                    delay_sec = random.uniform(min_delay, max_delay)
                else:
                    delay_sec = max(0.0, fixed_delay)

                if delay_sec > 0:
                    # Check if resuming from a delay
                    delay_start = datetime.datetime.now()
                    if saved_state and saved_state.get('in_delay') and saved_state.get('current_loop') == loop_num:
                        # Calculate remaining delay
                        original_delay_start = datetime.datetime.fromisoformat(saved_state['delay_start'])
                        elapsed = (delay_start - original_delay_start).total_seconds()
                        remaining_delay = max(0, delay_sec - elapsed)
                        if remaining_delay > 0:
                            status_update_callback(job_id, 'running', f"Resuming delay: {remaining_delay:.1f}s remaining -- {loop_num}/{main_loops} loops completed")
                            print(f"[Resume] Job {job_id} resuming delay with {remaining_delay:.1f}s remaining")
                            delay_sec = remaining_delay
                        saved_state = None  # Clear to prevent re-processing
                    else:
                        status_update_callback(job_id, 'running', f"Delay {delay_sec:.1f}s before next loop -- {loop_num}/{main_loops} loops completed")
                    
                    slept = 0.0
                    step = 0.5
                    while slept < delay_sec:
                        if stopped():
                            break
                        # Save state during delay every 2 seconds for resume
                        if int(slept) % 2 == 0 and slept > 0:
                            save_job_state(job_id, {
                                'current_loop': loop_num,
                                'total_loops': main_loops,
                                'start_time': start_time.isoformat(),
                                'in_delay': True,
                                'delay_start': delay_start.isoformat(),
                                'delay_duration': delay_sec + slept,
                                'messages': messages,
                                'total_orders': total_orders,
                                'placed_orders': placed_orders,
                                'profile_name': profile_name,
                                'link': link,
                                'platform_filter': platform_filter
                            })
                        time.sleep(step)
                        slept += step
                if stopped():
                    messages.append("Stopped during delay")
                    success = False
                    break

        # Determine final success: at least one order placed and not stopped
        final_success = success and total_orders > 0
        final_msg = f"Orders: {total_orders}. " + "; ".join(messages[-10:])
        status_update_callback(job_id, 'success' if final_success else 'failed', final_msg)
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
            'type': 'Auto Promo',
            'profile_name': profile_name,
            'link': link,
            'quantity': None,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': round(duration, 2),
            'status': 'Success' if final_success else 'Failed',
            'message': final_msg,
            'order_count': total_orders,
            'total_cost': total_cost_sum,
        }
        try:
            save_history_callback(history_entry)
        except Exception:
            traceback.print_exc()
        
        # Clear job state after completion
        clear_job_state(job_id)
