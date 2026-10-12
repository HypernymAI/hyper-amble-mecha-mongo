from __future__ import annotations
import gzip
import hashlib
import json
from pathlib import Path
import tiktoken
from scale import SIM, person_days
HERE=Path(__file__).resolve().parent
for person in (1,2,999,110000):
    previous=12;inventory={};days=list(person_days(person))
    assert len(days)==50
    for day,row in enumerate(days,1):
        ledger=row['ledger'];assert row['day']==day and row['resident_id']==f'life-scale-{person:09d}'
        assert row['simulation_id']==SIM and row['synthetic']
        assert ledger['opening_balance']==previous
        assert ledger['closing_balance']==previous+ledger['credits_earned']-ledger['credits_spent']>=0
        assert ledger['credits_spent']==ledger['packs_opened']*8
        assert len(row['pack_openings'])==ledger['packs_opened']
        for pack in row['pack_openings']:
            assert pack['outcome']==('one_item' if pack['items'] else 'empty')
            for item in pack['items']:inventory[item['item_id']]=inventory.get(item['item_id'],0)+1
        assert row['inventory']==inventory and row['home']['owned_home_item_ids']==sorted(inventory)
        previous=ledger['closing_balance']
output=HERE.parents[1]/'data/synthetic-resident-life/scale'
manifest=json.loads((output/'scale-progress.json').read_text())
shard=manifest['shards'][0];path=output/shard['file'];assert hashlib.sha256(path.read_bytes()).hexdigest()==shard['sha256']
encoder=tiktoken.get_encoding('cl100k_base');count=0;records=0
for row in map(json.loads,gzip.open(path,'rt')):
    text='\n'.join([row['morning'],*(r['text'] for r in row['work_conversation']),row['memory'],row['night']])
    actual=len(encoder.encode(text));assert actual==row['narrative_token_count'];count+=actual;records+=1
assert count==shard['tokens'] and records==shard['records']==50000
print('PASS 4 boundary residents ×50days integer wallet/inventory chains, complete first-shard SHA256, independently retokenized 50,000 rows:',count)
print('scale.py SHA256',hashlib.sha256((HERE/'scale.py').read_bytes()).hexdigest())
