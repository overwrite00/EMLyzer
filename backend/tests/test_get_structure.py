import asyncio, sys
sys.path.insert(0, '.')

async def test():
    from httpx import AsyncClient, ASGITransport
    from main import app
    from models.database import init_db
    await init_db()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Upload e analisi (POST)
        with open('../samples/phishing_sample.eml', 'rb') as f:
            r = await c.post('/api/upload/', files={'file': ('phishing.eml', f, 'application/octet-stream')})
        job_id = r.json()['job_id']

        post_resp = await c.post(f'/api/analysis/{job_id}')
        assert post_resp.status_code == 200
        post_data = post_resp.json()

        # GET stesso job_id
        get_resp = await c.get(f'/api/analysis/{job_id}')
        assert get_resp.status_code == 200
        get_data = get_resp.json()

        # Chiavi di primo livello
        required_keys = ['job_id', 'email', 'risk', 'header_analysis',
                         'body_analysis', 'url_analysis', 'attachment_analysis']
        for key in required_keys:
            in_post = key in post_data
            in_get  = key in get_data
            ok = in_post and in_get
            print(f"  {'OK' if ok else 'FAIL'} chiave '{key}': POST={in_post} GET={in_get}")
            assert ok, f"Chiave '{key}' mancante"

        # Sotto-struttura email
        for sub in ['subject', 'from', 'to', 'date', 'message_id', 'file_hash_sha256']:
            assert sub in post_data['email'], f'POST email manca: {sub}'
            assert sub in get_data['email'],  f'GET email manca: {sub}'

        # Sotto-struttura risk
        for sub in ['score', 'label', 'explanation', 'contributions']:
            assert sub in post_data['risk'], f'POST risk manca: {sub}'
            assert sub in get_data['risk'],  f'GET risk manca: {sub}'

        # Valori coerenti tra POST e GET
        assert post_data['email']['subject'] == get_data['email']['subject']
        assert post_data['risk']['label'] == get_data['risk']['label']
        assert abs((post_data['risk']['score'] or 0) - (get_data['risk']['score'] or 0)) < 0.1

        subj = get_data['email']['subject']
        score = get_data['risk']['score']
        label = get_data['risk']['label']
        hf = len(get_data['header_analysis'].get('findings', []))
        forms = get_data['body_analysis']['forms_found']
        urls = get_data['url_analysis']['total_urls']

        print(f"  OK Subject:         {subj}")
        print(f"  OK Risk score:      {score} ({label})")
        print(f"  OK Header findings: {hf}")
        print(f"  OK Forms found:     {forms}")
        print(f"  OK URLs:            {urls}")

        # NLP presente
        assert 'nlp' in get_data['body_analysis']
        print(f"  OK NLP presente:    {get_data['body_analysis']['nlp'] is not None}")

        # Note analista
        await c.patch(
            f'/api/analysis/{job_id}/notes',
            json={'notes': 'Test nota GET'},
            headers={'Content-Type': 'application/json'}
        )
        r2 = await c.get(f'/api/analysis/{job_id}')
        assert r2.json()['analyst_notes'] == 'Test nota GET'
        print(f"  OK Note analista:   presenti e corrette")

        # Verifica email PULITA (clean)
        with open('../samples/clean_sample.eml', 'rb') as f:
            r = await c.post('/api/upload/', files={'file': ('clean.eml', f, 'application/octet-stream')})
        job_id2 = r.json()['job_id']
        await c.post(f'/api/analysis/{job_id2}')

        get2 = await c.get(f'/api/analysis/{job_id2}')
        assert get2.status_code == 200
        d2 = get2.json()
        assert d2['risk']['label'] == 'low', f"Atteso low, ottenuto {d2['risk']['label']}"
        print(f"  OK Clean email GET: score={d2['risk']['score']} ({d2['risk']['label']})")

        print()
        print("GET e POST restituiscono struttura identica - PASS")

asyncio.run(test())
