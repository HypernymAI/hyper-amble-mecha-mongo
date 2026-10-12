from __future__ import annotations
"""Distinct procedural residents/days with their own coherent integer economy.
Separate from the original demo simulation: no weighted-population equivalence.
"""
import argparse
import gzip
import hashlib
import json
import time
from pathlib import Path
import tiktoken

SIM='synthetic-life-scale-v1-seed-20261011'
METHOD='procedural_distinct_resident_days_v1'
PROFESSIONS=['construction','healthcare','finance']
TOPICS={'construction':['courtyard tile count','window frame checklist','brick pattern survey','roof panel inventory','garden path measurement'], 'healthcare':['fictional clinic shelf count','waiting-room chair checklist','toy appointment roster','blank label sorting','supply drawer inventory'], 'finance':['toy-town receipt tally','fictional budget check','credit ledger reconciliation','sandbox invoice sorting','model savings table']}
MOODS=['hopeful','thoughtful','sleepy','focused','curious','restless','calm','eager']
DETAILS=['the sun crossing the window','a soft tap at the doorway','the rhythm of footsteps outside','the edge of a folded note','the light on the work table','a small patch of blue sky','the quiet before the first task','the sound of a drawer closing']
QUESTIONS=['What helped you find your rhythm?','Which detail needed another look?','What made the task feel manageable?','What will you remember at home?','Where did you slow down today?','What would you check first tomorrow?']
ITEMS=['item-plant','item-mug','item-lamp','item-chair','item-books','item-rug','item-sofa']

def dump(row):return json.dumps(row,separators=(',',':'),ensure_ascii=False)
def save(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2));temp.replace(path)
def number(person,day,slot):
    # Independent deterministic arithmetic stream; no external model or entropy source.
    x=(person*2654435761+day*2246822519+slot*3266489917+20261011)&0xffffffff
    x^=x>>16;x=(x*2246822519)&0xffffffff;x^=x>>13
    return x

def person_days(person):
    rid=f'life-scale-{person:09d}';profession=PROFESSIONS[person%3]
    balance=12;inventory={};last_memory='my arrival in this separate fictional town'
    for day in range(1,51):
        opening=balance;jobs=1+number(person,day,0)%2;earned=sum(12+number(person,day,j+3)%9 for j in range(jobs));balance+=earned
        packs_count=balance//8;spent=packs_count*8;balance-=spent
        packs=[];received=[]
        for pack in range(packs_count):
            pack_id=f'{SIM}:{rid}:day:{day:03d}:pack:{pack:02d}'
            item=ITEMS[number(person,day,pack+25)%len(ITEMS)] if number(person,day,pack+15)%7==0 else None
            items=[]
            if item:
                instance=pack_id+':item:1';items=[{'item_id':item,'item_instance_id':instance}];inventory[item]=inventory.get(item,0)+1;received.append(item.removeprefix('item-'))
            packs.append({'event_id':pack_id+':opened','pack_instance_id':pack_id,'sku_id':'daily-breakfast','outcome':'one_item' if item else 'empty','items':items})
        mood=MOODS[number(person,day,70)%len(MOODS)];detail=DETAILS[number(person,day,71)%len(DETAILS)];topic=TOPICS[profession][number(person,day,72)%5];question=QUESTIONS[number(person,day,73)%len(QUESTIONS)]
        neighbor=f'life-scale-{((person+number(person,day,74)%17)%110000)+1:09d}'
        morning=f'Day {day}. I woke {mood} and noticed {detail}. I am {rid}, a {profession} resident in this separate synthetic town. I remembered {last_memory}. With {opening} credits at the start, I wanted to give the next task enough attention and leave room for a conversation.'
        conversation=[{'speaker':rid,'text':f'I finished {jobs} jobs today, working through the {topic}. I earned {earned} credits. The numbers are clear, but I want to remember what it felt like to do the work.'},{'speaker':neighbor,'text':question},{'speaker':rid,'text':f'I paused when I noticed {detail}. That pause helped me check the {topic} again. I would rather remember a careful moment than rush straight to opening the packs.'}]
        result='I found '+', '.join(received)+'.' if received else 'All the packs were empty.'
        memory=f'I remember day {day}: {jobs} jobs, {earned} earned credits, and the question "{question}". I spent {spent} credits on {packs_count} packs. {result} The outcome is part of this day; it does not change the work I completed. I want tomorrow to recall the conversation as well as the objects.'
        night=f'At night I felt {"pleased" if received else "a little disappointed"}, then settled into the quiet. {result} My wallet closes at {balance} credits, and my home holds {sum(inventory.values())} collected objects across {len(inventory)} kinds. I thought again about {detail}. Before sleeping, I kept the memory of the {topic} and the neighbor\'s question close.'
        row={'_id':f'{SIM}:{rid}:day:{day:03d}','simulation_id':SIM,'resident_id':rid,'amble_id':rid,'day':day,'synthetic':True,'generation_method':METHOD,'profession':profession,'morning':morning,'work_conversation':conversation,'memory':memory,'night':night,'pack_openings':packs,'inventory':dict(inventory),'home':{'owned_home_item_ids':sorted(inventory),'home_version':len(inventory)},'ledger':{'opening_balance':opening,'jobs_completed':jobs,'credits_earned':earned,'credits_spent':spent,'closing_balance':balance,'packs_opened':packs_count},'provenance':{'source':'independent_generated_integer_ledger','seed':20261011,'model_run':False,'not_original_demo_population':True}}
        assert opening+earned-spent==balance>=0
        yield row
        last_memory=f'yesterday\'s {topic} and {"the "+received[-1]+" from a pack" if received else "the empty packs"}'

def run(output,target,residents,shard_residents,disk_cap,benchmark=False):
    output.mkdir(parents=True,exist_ok=True);encoding=tiktoken.get_encoding('cl100k_base');path=output/'scale-progress.json'
    progress=json.loads(path.read_text()) if path.exists() else {'simulation_id':SIM,'synthetic':True,'generation_method':METHOD,'target_tokens':target,'actual_tokens':0,'records':0,'resident_count':0,'tokenizer':'tiktoken 0.14.0 cl100k_base','token_count_scope':'morning, work_conversation text, memory, night; excludes JSON metadata','status':'partial','shards':[],'compressed_bytes':0}
    progress['target_tokens']=target;started=time.monotonic();initial=progress['actual_tokens']
    while progress['resident_count']<residents and progress['actual_tokens']<target:
        if progress['compressed_bytes']>=disk_cap:progress['status']='disk_cap_reached';save(path,progress);break
        first=progress['resident_count']+1;last=min(residents,first+shard_residents-1);shard=output/f'scale-{first:09d}-{last:09d}.jsonl.gz';temporary=shard.with_suffix('.partial');tokens=0;records=0
        with gzip.open(temporary,'wt',compresslevel=1) as stream:
            for person in range(first,last+1):
                for row in person_days(person):
                    text='\n'.join([row['morning'],*(r['text'] for r in row['work_conversation']),row['memory'],row['night']]);n=len(encoding.encode(text));tokens+=n;records+=1;row['narrative_token_count']=n;stream.write(dump(row)+'\n')
        temporary.replace(shard);size=shard.stat().st_size
        progress['actual_tokens']+=tokens;progress['records']+=records;progress['resident_count']=last;progress['compressed_bytes']+=size
        progress['shards'].append({'file':shard.name,'resident_first':first,'resident_last':last,'records':records,'tokens':tokens,'bytes':size,'sha256':hashlib.sha256(shard.read_bytes()).hexdigest()})
        elapsed=time.monotonic()-started;rate=(progress['actual_tokens']-initial)/elapsed;progress.update(tokens_per_second=round(rate,1),eta_seconds=round(max(0,target-progress['actual_tokens'])/rate,1),status='complete' if progress['actual_tokens']>=target else 'partial')
        save(path,progress);print(dump({k:v for k,v in progress.items() if k!='shards'}),flush=True)
        if benchmark:break
    if progress['resident_count']>=residents and progress['actual_tokens']<target:progress['status']='resident_limit_target_not_met';save(path,progress)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--target-tokens',type=int,default=1_000_000_000);p.add_argument('--residents',type=int,default=110000);p.add_argument('--shard-residents',type=int,default=1000);p.add_argument('--disk-cap-bytes',type=int,default=2_000_000_000);p.add_argument('--benchmark',action='store_true');a=p.parse_args();run(a.output,a.target_tokens,a.residents,a.shard_residents,a.disk_cap_bytes,a.benchmark)
