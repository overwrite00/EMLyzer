import asyncio, sys
sys.path.insert(0, '.')

async def test_list():
    from httpx import AsyncClient, ASGITransport
    from main import app
    from models.database import init_db
    await init_db()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Carica 3 email
        for name in ['phishing_sample.eml', 'clean_sample.eml', 'phishing_sample.eml']:
            with open(f'../samples/{name}', 'rb') as f:
                r = await c.post('/api/upload/', files={'file': (name, f, 'application/octet-stream')})
            await c.post(f'/api/analysis/{r.json()["job_id"]}')

        # 1. lista base
        r = await c.get('/api/analysis/')
        assert r.status_code == 200
        data = r.json()
        assert 'items' in data and 'total' in data and 'pages' in data
        total = data['total']
        pages = data['pages']
        print(f"OK lista base: {total} analisi, {pages} pagine")

        # 2. ricerca soggetto
        r = await c.get('/api/analysis/?q=URGENT')
        items = r.json()['items']
        print(f"OK ricerca q=URGENT: {len(items)} risultati")

        # 3. filtro risk
        r = await c.get('/api/analysis/?risk=high,critical')
        for item in r.json()['items']:
            assert item['risk_label'] in ('high', 'critical')
        print(f"OK filtro risk=high,critical: {r.json()['total']} risultati")

        r2 = await c.get('/api/analysis/?risk=low')
        print(f"OK filtro risk=low: {r2.json()['total']} risultati")

        # 4. paginazione
        r = await c.get('/api/analysis/?page=1&page_size=2')
        d = r.json()
        assert len(d['items']) <= 2
        print(f"OK paginazione page_size=2: {len(d['items'])} items")

        # 5. pagina fuori range
        r = await c.get('/api/analysis/?page=9999')
        assert r.status_code == 200
        assert r.json()['items'] == []
        print("OK pagina fuori range: lista vuota")

        # 6. ricerca senza risultati
        r = await c.get('/api/analysis/?q=NESSUNRISULTATO12345XYZ')
        assert r.json()['total'] == 0
        print("OK ricerca senza risultati: total=0")

        # 7. combinazione filtri
        r = await c.get('/api/analysis/?q=urgent&risk=high,critical&page=1&page_size=10')
        assert r.status_code == 200
        print(f"OK combinazione filtri: {r.json()['total']} risultati")

    print("\nLISTA/FILTRO/PAGINAZIONE - tutti i test passati OK")

asyncio.run(test_list())
