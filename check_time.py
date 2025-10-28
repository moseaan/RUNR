import json, os, datetime, pytz

history_file = os.path.join('app_files', 'history.json')
if os.path.exists(history_file):
    with open(history_file, 'r') as f:
        data = json.load(f)
    if data:
        sample = data[0]
        timestamp = sample.get('start_time')
        print('Sample timestamp:', timestamp)
        if timestamp:
            # Try parsing as is (assume EST)
            try:
                dt = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                print('Parsed datetime:', dt)

                # Assume it's EST if naive
                if dt.tzinfo is None:
                    est = pytz.timezone('America/New_York')
                    dt = est.localize(dt)
                    print('Localized to EST:', dt)

                # Format
                date_str = dt.strftime('%m/%d/%Y').lstrip('0').replace('/0', '/')
                time_str = dt.strftime('%I:%M:%S %p').lstrip('0')
                print('Formatted result:', f"{date_str}<br>{time_str}")
                print('Current time should be around:', datetime.datetime.now().strftime('%I:%M %p'))

            except Exception as e:
                print('Parse error:', e)
else:
    print('No history file')
