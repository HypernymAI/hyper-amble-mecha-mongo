from __future__ import annotations
"""Read bounded synthetic fixture days and completed-only corpus progress."""
import json
from pathlib import Path
from .generate import get_resident_day

def _read(path):
    try:
        if path.is_file() and path.stat().st_size <= 1_000_000:
            value=json.loads(path.read_text())
            return value if isinstance(value,dict) else {}
    except (OSError,ValueError):
        pass
    return {}

def corpus_status():
    here=Path(__file__).resolve().parent
    output=here.parents[1]/'data/synthetic-resident-life'
    original=_read(output/'progress.json') or _read(here/'measurements.json')
    local_scale=_read(output/'scale/scale-progress.json')
    scale=local_scale or _read(here/'scale-proof.json')
    def count(row,key):
        value=row.get(key,0)
        return value if isinstance(value,int) and not isinstance(value,bool) and value>=0 else 0
    original_tokens=count(original,'actual_tokens');scale_tokens=count(scale,'actual_tokens')
    total=original_tokens+scale_tokens;target=1_000_000_000
    return {'synthetic':True,'generation_method':'procedural_multiple_separate_scenarios_v1','actual_tokens':total,'target_tokens':target,'tokenizer':original.get('tokenizer','tiktoken 0.14.0 cl100k_base'),'records':count(original,'records')+count(scale,'records'),'status':'complete' if total>=target else ('partial' if scale else 'source_exhausted_target_not_met'),'original_demo_tokens':original_tokens,'original_demo_records':count(original,'records'),'scale_tokens':scale_tokens,'scale_records':count(scale,'records'),'scale_resident_count':count(scale,'resident_count'),'scale_status':scale.get('status','not_available'),'local_scale_archive_available':bool(local_scale),'scale_archive_included_in_package':False,'separate_simulation_ids':['sim-db75377af60bd6c8b7d6']+([scale['simulation_id']] if isinstance(scale.get('simulation_id'),str) else []),'scale_tokens_per_second':scale.get('tokens_per_second'),'scale_eta_seconds':scale.get('eta_seconds'),'token_count_scope':'narrative fields only, excludes JSON metadata; distinct separate scenarios; completed shards only','quality_note':'Original demo residents retain their exact wallets. Scale residents use a separate generated economy; no weighted-population equivalence or model runs.'}
