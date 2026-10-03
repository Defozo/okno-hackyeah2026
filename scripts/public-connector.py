"""Keep the fixed public demo address connected after an ngrok restart. No request logs."""
import json
import os
import time
import urllib.request
from datetime import datetime, timezone

origin = os.environ['OKNO_DEMO_ORIGIN'].rstrip('/')
key = os.environ['OKNO_DEMO_GATEWAY_KEY']
last_url = None
last_refresh = 0

while True:
    try:
        with urllib.request.urlopen('http://tunnel:4040/api/tunnels', timeout=5) as response:
            tunnels = json.load(response)['tunnels']
        url = next(t['public_url'] for t in tunnels if t['public_url'].startswith('https://'))
        if url != last_url or time.monotonic() - last_refresh > 60:
            request = urllib.request.Request(origin + '/_ops/tunnel',
                data=json.dumps({'url': url}).encode(), method='PUT',
                headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json',
                         'User-Agent': 'Mozilla/5.0 (compatible; OknoDemoConnector/1.0)'})
            with urllib.request.urlopen(request, timeout=45) as response:
                assert response.status == 200
            if url != last_url:
                print(json.dumps({'event': 'connection_registered', 'at': datetime.now(timezone.utc).isoformat()}), flush=True)
            last_url = url
            last_refresh = time.monotonic()
    except Exception as exc:
        # Error bodies, URLs and credentials are deliberately excluded from logs.
        print(json.dumps({'event': 'connection_retry', 'kind': type(exc).__name__,
                          'status': getattr(exc, 'code', None)}), flush=True)
    time.sleep(10)
