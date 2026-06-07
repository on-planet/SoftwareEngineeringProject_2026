import urllib.request, json
try:
    req = urllib.request.Request('http://localhost:8000/api/futures?frequency=day&limit=10')
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
        print('Total:', data.get('total'))
        for item in data.get('items', [])[:3]:
            print(item)
except Exception as e:
    print('Error:', e)
