from __future__ import annotations
"""Validate every completed shard's identity, wallet, ownership and token receipts."""
import argparse
import gzip
import hashlib
import json
import time
from pathlib import Path

def validate(output):
    started=time.monotonic();manifest=json.loads((output/'scale-progress.json').read_text());total_tokens=total_records=total_bytes=0;expected_person=1
    for shard in manifest['shards']:
        path=output/shard['file'];assert path.stat().st_size==shard['bytes'];assert hashlib.sha256(path.read_bytes()).hexdigest()==shard['sha256']
        records=tokens=0;previous_id=None;balance=12;inventory={};day=0
        with gzip.open(path,'rt') as stream:
            for row in map(json.loads,stream):
                rid=row['resident_id']
                if rid != previous_id:
                    assert rid==f'life-scale-{expected_person:09d}'
                    if previous_id is not None:assert day==50
                    expected_person+=1;previous_id=rid;balance=12;inventory={};day=0
                day+=1;assert row['day']==day
                assert row['simulation_id']==manifest['simulation_id'] and row['synthetic'] is True
                ledger=row['ledger'];assert ledger['opening_balance']==balance
                balance+=ledger['credits_earned']-ledger['credits_spent'];assert ledger['closing_balance']==balance>=0
                assert ledger['credits_spent']==len(row['pack_openings'])*8
                assert ledger['packs_opened']==len(row['pack_openings'])
                for pack in row['pack_openings']:
                    assert pack['outcome']==('one_item' if pack['items'] else 'empty')
                    for item in pack['items']:inventory[item['item_id']]=inventory.get(item['item_id'],0)+1
                assert row['inventory']==inventory
                assert row['home']['owned_home_item_ids']==sorted(inventory)
                assert all(row[key] for key in ('morning','work_conversation','memory','night'))
                assert isinstance(row['narrative_token_count'],int) and row['narrative_token_count']>0
                tokens+=row['narrative_token_count'];records+=1
        assert day==50 and records==shard['records'] and tokens==shard['tokens']
        total_records+=records;total_tokens+=tokens;total_bytes+=shard['bytes']
    assert total_records==manifest['records'] and total_tokens==manifest['actual_tokens'] and total_bytes==manifest['compressed_bytes']
    assert expected_person-1==manifest['resident_count'] and total_records==(expected_person-1)*50
    report={'status':'PASS','simulation_id':manifest['simulation_id'],'actual_tokens':total_tokens,'resident_count':expected_person-1,'records':total_records,'compressed_bytes':total_bytes,'shards':len(manifest['shards']),'checks':'all shard hashes; every day ID, wallet chain, pack outcome and exact inventory; stored tokenizer receipts summed; first 50k rows separately retokenized by test_scale.py','elapsed_seconds':round(time.monotonic()-started,2)}
    (output/'validation_report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);validate(p.parse_args().output)
