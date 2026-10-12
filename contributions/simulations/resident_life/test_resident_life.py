from __future__ import annotations
import gzip
import hashlib
import json
from pathlib import Path
from generate import get_resident_day
HERE=Path(__file__).resolve().parent
residents=[json.loads(line) for line in (HERE.parent/'economy/demo/sample_residents.jsonl').read_text().splitlines()]
rows=[json.loads(line) for line in gzip.open(HERE/'resident_days.jsonl.gz','rt')]
assert len(rows)==10000
assert len({r['_id'] for r in rows})==10000
for resident in residents:
    for day in range(1,51):
        row=get_resident_day(resident['resident_id'],day)
        assert row and row['synthetic'] and row['amble_id']==resident['resident_id']
        assert row['ledger']['opening_balance']+row['ledger']['credits_earned']-row['ledger']['credits_spent']==row['ledger']['closing_balance']
        assert len(row['pack_openings'])==row['ledger']['packs_opened']
        assert sorted(row['inventory'])==sorted(row['home']['owned_home_item_ids'])
        assert all(p['event_id'] in row['provenance']['event_ids'] for p in row['pack_openings'])
        assert row['morning'] and row['memory'] and row['night'] and row['work_conversation']
    final=get_resident_day(resident['resident_id'],50)
    assert final['inventory']==resident['inventory_quantities']
    assert final['ledger']['closing_balance']==resident['ending_balance']
assert get_resident_day('not-a-resident',1) is None
assert get_resident_day(residents[0]['resident_id'],51) is None
print('PASS 10,000 linked days, 200 exact ending inventories, wallet arithmetic, pack event links, missing selectors')
for name in ('generate.py','reader.py','resident_days.jsonl.gz','demo.json'):
    print(hashlib.sha256((HERE/name).read_bytes()).hexdigest(), name)
