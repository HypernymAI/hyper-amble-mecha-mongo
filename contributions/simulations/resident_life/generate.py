from __future__ import annotations
"""Deterministic synthetic stories; economy ledger remains the sole factual source."""
import argparse
import collections
import functools
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
METHOD = 'procedural_ledger_grounded_v1'

def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))

@functools.lru_cache(maxsize=1)
def _records():
    with gzip.open(HERE / 'resident_days.jsonl.gz', 'rt') as stream:
        return {(row['resident_id'], row['day']): row for row in map(json.loads, stream)}

def get_resident_day(resident_id, day):
    """Read one immutable synthetic day, or return None. No database writes."""
    return _records().get((resident_id, int(day)))

def narrative_text(row):
    return '\n'.join([row['morning'], *(line['text'] for line in row['work_conversation']), row['memory'], row['night']])

def build(source):
    daily = [json.loads(line) for line in (source / 'sample_daily.jsonl').read_text().splitlines()]
    events = collections.defaultdict(list)
    with gzip.open(source / 'sample_events.jsonl.gz', 'rt') as stream:
        for event in map(json.loads, stream):
            events[(event['resident_id'], event['day'])].append(event)
    inventory = collections.defaultdict(collections.Counter)
    records = []
    moods = ['quietly hopeful', 'restless', 'curious', 'steady', 'a little tired', 'determined']
    for day in daily:
        rid, number = day['resident_id'], day['day']
        ev = events[(rid, number)]
        packs = [{key: e[key] for key in ('event_id','pack_instance_id','sku_id','outcome','items')} for e in ev if e['event_type']=='pack_opening']
        for event in ev:
            if event['event_type'] == 'item_received':
                if event['inventory_quantity_after']:
                    inventory[rid][event['item_id']] = event['inventory_quantity_after']
                else:
                    inventory[rid].pop(event['item_id'], None)
        jobs = [e for e in ev if e['event_type']=='job_completed']
        task = ', '.join(sorted({e['job_kind'].removeprefix('fictional_').replace('_',' ') for e in jobs})) or 'a day without a completed job'
        items = ', '.join(item['item_id'].removeprefix('item-') for p in packs for item in p['items'])
        feeling = moods[int(hashlib.sha256(f'{rid}:{number}'.encode()).hexdigest()[:8],16)%len(moods)]
        home_items = ', '.join(day['owned_home_item_ids']) or 'no collected home items yet'
        previous = 'the first morning in this little town' if number == 1 else f'yesterday, day {number-1}, and the routine I am learning'
        row = {'_id':day['_id']+':life:v1','resident_id':rid,'simulation_id':day['simulation_id'],'amble_id':rid,'day':number,'date':day['date'],'profession':day['profession'],'synthetic':True,'generation_method':METHOD,
          'morning':f'I woke {feeling}, thinking about {previous}. My wallet opens at {day["opening_balance"]} credits. I want to pay attention to the {day["profession"]} work in front of me instead of counting the day before it happens.',
          'work_conversation':[{'speaker':rid,'text':f'Today my recorded work is {task}. I completed {day["jobs_completed"]} jobs.'},{'speaker':'fictional_workmate','text':'What part of the routine will you remember when you get home?'},{'speaker':rid,'text':f'The moment I stopped rushing and checked the work. The ledger records {day["credits_earned"]} earned credits; I can connect that number with the time I spent here.'}],
          'memory':f'Day {number}: {day["packs_opened"]} packs opened after spending {day["credits_spent"]} credits. '+(f'The openings contained {items}. I remember noticing the difference between an object arriving and my hope for one.' if items else 'Every opening was empty. I remember the little pause after the last wrapper; wanting an item did not make one appear.'),
          'night':f'I feel {"pleased and settled" if items else "disappointed but ready to rest"}. My closing balance is {day["closing_balance"]} credits. My home now has {home_items}. Tomorrow I want to remember the work as well as the packs.',
          'pack_openings':packs,'packs':packs,'inventory':dict(inventory[rid]),'home':{'home_version':day['home_version'],'owned_home_item_ids':day['owned_home_item_ids']},
          'ledger':{k:day[k] for k in ('opening_balance','credits_earned','credits_spent','closing_balance','jobs_completed','packs_opened')},
          'provenance':{'daily_record_id':day['_id'],'event_ids':[e['event_id'] for e in ev],'source_dataset':'target-demo','dialogue_is_synthetic':True}}
        assert len(packs)==day['packs_opened']
        assert sorted(inventory[rid]) == sorted(day['owned_home_item_ids'])
        records.append(row)
    with gzip.open(HERE / 'resident_days.jsonl.gz','wt',compresslevel=6) as out:
        for row in records: out.write(dumps(row)+'\n')
    preview = [row for row in records if row['day'] in (1,50)]
    (HERE/'demo.json').write_text(dumps({'synthetic':True,'generation_method':METHOD,'resident_days':preview}))
    return records

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path)
    args=parser.parse_args()
    records=build(args.source) if args.source else list(_records().values())
