"""Isolated HTTP/worker integration; no real model account or Atlas calls."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.swarm_server import Town, Handler, ThreadingHTTPServer, private_json
from sandbox import provider


def main():
    old_answer=provider.answer
    def answer(prompt, config):
        if not prompt.startswith('Complete'):
            return 'Hello from a test resident.'
        payload,_=json.JSONDecoder().raw_decode(prompt[prompt.index('{'):])
        task=payload['job']['task']
        if 'boxes' in task: value={'packs_total':task['boxes']*task['packs_per_box']+task['loose_packs']}
        elif 'sales_credits' in task:value={'remaining_credits':task['sales_credits']-task['supply_cost']-task['stall_cost']}
        else:value={'tiles_needed':task['rows']*task['tiles_per_row']+task['spare_tiles']}
        assert 'embedding' not in payload['your_memories'].__repr__()
        return json.dumps({'answer':value,'message':'Checked the task data.','buy_item_id':'daily-breakfast'})
    provider.answer=answer
    with tempfile.TemporaryDirectory(prefix='amble-swarm-http-') as tmp:
        directory=Path(tmp)
        private_json(directory/'config.json',{'embedding_provider':'lexical','model_backend':'claude-cli'})
        town=Town(directory,concurrency=1)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.town=town
        town.port=server.server_port;town.lan_address='127.0.0.1'
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def call(path, body=None, token=True):
            req=urllib.request.Request('http://127.0.0.1:%s%s'%(town.port,path),
                data=json.dumps(body).encode() if body is not None else None,
                headers={'Content-Type':'application/json',**({'X-Swarm-Token':town.token} if token else {})})
            try:
                with urllib.request.urlopen(req,timeout=5) as response:return response.status,json.load(response)
            except urllib.error.HTTPError as exc:return exc.code,json.load(exc)
        try:
            assert call('/api/state',token=False)[0]==401
            assert call('/api/economy',token=False)[0]==401
            economy=call('/api/economy')[1]
            assert economy['synthetic'] is True and economy['available'] is True
            assert len(economy['days'])==50 and len(economy['residents'])==200
            sites=call('/api/state')[1]['worksites']
            assert {site['id'] for site in sites}=={'arm-site'}
            assert all(site['status']=='replay_ready' for site in sites)
            assert call('/api/state')[1]['stats']['jobs_completed']==0
            status,result=call('/api/control',{'action':'step'});assert status==200 and result['ok']
            deadline=time.monotonic()+5
            # State payment commits before the worker records its memory. Wait
            # for that whole turn before comparing counts around a forged claim.
            while time.monotonic()<deadline:
                with town.lock:
                    settled=not town.inflight
                if settled and town.state.snapshot()['stats']['jobs_completed']>=1:break
                time.sleep(.03)
            assert settled, 'The test worker did not finish its memory writes'
            snap=town.state.snapshot();assert snap['stats']['jobs_completed']==1 and not snap['running']
            assert sum(len(r['home']['items']) for r in snap['residents'])==1
            before=town.memory.status()['memories']
            assert not call('/api/complete',{'worker_id':'impostor','lease_id':'unknown','resident_id':'aya','raw':'fake','result':{'answer':{}}})[1]['ok']
            assert town.memory.status()['memories']==before
            status,result=call('/api/chat',{'resident_id':'aya','message':'Remember my blue lantern.'})
            assert status==200 and result['reply']=='Hello from a test resident.'
            records=call('/api/memories?resident_id=aya')[1]['memories']
            assert any(row['text']=='Remember my blue lantern.' for row in records)
            assert all(row['resident_id']=='aya' for row in records)
            assert call('/api/import',{'resident_id':'missing','messages':[]})[0]==400
            assert call('/api/import',{'resident_id':'milo','messages':[{'role':'user','text':'A sandbox finance note.'}]})[1]['imported']==1
            assert 'join_token' not in json.dumps(call('/api/state')[1])
            assert call('/api/control',{'action':'invalid'})[0]==400
            assert call('/api/mind?resident_id=missing')[0]==400
            assert call('/api/memories?resident_id=missing')[0]==400
            assert call('/api/mind?resident_id=aya')[1]['enabled'] is False
            assert call('/api/dream',{'resident_id':'aya'})[0]==400
            town.config['mongodb_uri']='mongodb+srv://test:old@cluster.invalid/test'
            town.state.set_running(True)
            assert call('/api/config',{'model_backend':'claude-cli','mongodb_password':'test @/ value'})[1]['ok']
            assert 'test%20%40%2F%20value' in town.config['mongodb_uri']
            assert call('/api/config',{'model_backend':'sol'})[0]==400
            saved_before=(directory/'config.json').read_bytes()
            config_before=dict(town.config)
            town.memory.atlas._busy=1
            try:
                assert call('/api/config',{'mongodb_database':'rejected_while_dreaming'})[0]==400
                assert town.config==config_before
                assert (directory/'config.json').read_bytes()==saved_before
            finally:
                town.memory.atlas._busy=0
            assert 'test%20%40%2F%20value' not in json.dumps(call('/api/state')[1])
            print('PASS swarm HTTP: auth, one-turn pause, wages/home, worker identity, chat, private recall, import, secret-free status')
        finally:
            server.shutdown();server.server_close();town.closed.set();town.pool.shutdown(wait=True)
            town.state.close();town.memory.close();provider.answer=old_answer
    return 0


if __name__=='__main__':
    raise SystemExit(main())
