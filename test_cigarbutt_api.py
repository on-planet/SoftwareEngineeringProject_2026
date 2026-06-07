import urllib.request, json
try:
    req = urllib.request.Request('http://localhost:8000/api/strategy/cigarbutt/0700.HK')
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
        print('Symbol:', data.get('symbol'))
        print('Stock price:', data.get('stock_price'))
        analysis = data.get('analysis', {})
        print('Best T level:', analysis.get('best_t_level'))
        print('Fact check rating:', analysis.get('fact_check_rating'))
        print('Bonus adjusted rating:', analysis.get('bonus_adjusted_rating'))
except Exception as e:
    print('Error:', e)
