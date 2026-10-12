// A local sandbox control surface on the existing Presents city. It does not
// create a second world, replace the renderer, or synthesize resident activity.
const $ = id => document.getElementById(`psw-${id}`);
const root = document.createElement('section');
root.id = 'presents-swarm';
root.setAttribute('aria-label', 'Sandbox swarm');
root.innerHTML = `
  <div class="psw-dock"><button id="psw-jobs-button" aria-controls="psw-drawer">Jobs</button><button id="psw-simulation-button" aria-controls="psw-drawer">Simulation</button><button id="psw-toggle" aria-expanded="false" aria-controls="psw-drawer"><span class="psw-dot"></span> Swarm <span id="psw-count"></span></button><button id="psw-run" disabled>Start</button></div>
  <aside id="psw-drawer" hidden aria-label="Swarm controls">
    <header class="psw-header"><div><h2 id="psw-title">Swarm</h2><p id="psw-status">Connecting to this city…</p></div><button id="psw-close" aria-label="Close swarm">×</button></header>
    <div class="psw-controls"><button id="psw-step" title="Runs the next queued job in the live town, across all professions">One real turn</button><button id="psw-add">+ Resident</button><button id="psw-setup">Setup</button></div>
    <p id="psw-error" role="status" hidden></p>
    <div id="psw-resident-view"><div id="psw-residents" class="psw-residents" aria-label="Residents"></div>
    <section id="psw-person" hidden><div class="psw-person-header"><div><h3 id="psw-name"></h3><p id="psw-role"></p></div><strong id="psw-credits"></strong></div><p id="psw-activity"></p><p id="psw-progress"></p>
      <nav class="psw-tabs" aria-label="Resident information"><button data-tab="home" aria-pressed="true">Home</button><button data-tab="memory" aria-pressed="false">Memory</button><button data-tab="chat" aria-pressed="false">Chat</button></nav>
      <section id="psw-home"><div id="psw-items" class="psw-items"></div><div id="psw-shops"></div></section>
      <section id="psw-memory" hidden><div class="psw-section-head"><h4>Individual memory</h4><button id="psw-refresh-memory">Refresh</button></div><section class="psw-mind" aria-label="Resident learning"><div class="psw-section-head"><h4>Learned memory</h4><button id="psw-dream" type="button" disabled>Dream now</button></div><p class="psw-help">Dreaming uses a model turn to review this resident’s recent history and learn from it.</p><p id="psw-mind-status" role="status" class="psw-help">Open Memory to read what this resident has learned.</p><p id="psw-dream-result" class="psw-help" role="status" hidden></p><div id="psw-mind-stats" class="psw-mind-stats" hidden></div><div id="psw-mind-content" hidden><details open><summary>Memories</summary><div id="psw-learned-memories" class="psw-learned-list"></div></details><details open><summary>Lessons</summary><div id="psw-lessons" class="psw-learned-list"></div></details><p id="psw-last-dream" class="psw-help" hidden></p></div></section><h4 class="psw-transcript-heading">Conversation history</h4><div id="psw-memories"></div><details class="psw-import"><summary>Import sandbox conversation</summary><p>Choose a JSON array of {role, text} messages, or an object with a messages array. Imported into this resident only.</p><input id="psw-import-file" type="file" accept=".json,application/json" aria-label="Sandbox conversation JSON"><button id="psw-import-button">Import messages</button></details></section>
      <section id="psw-chat" hidden><div id="psw-messages" aria-live="polite"></div><form id="psw-chat-form"><label class="psw-sr" for="psw-message">Message selected resident</label><textarea id="psw-message" rows="2" maxlength="4000" required placeholder="Say hello…"></textarea><button id="psw-send" type="submit">Send</button></form></section>
    </section>
    </div>
    <section id="psw-jobs-view" hidden aria-label="Live job site"><p class="psw-help">Residents earn town credits from accepted work. One real turn runs the next queued job across all professions.</p><div id="psw-job-sync" class="psw-job-sync" role="status"></div><nav id="psw-job-filters" class="psw-job-filters" aria-label="Filter jobs by profession"></nav><div id="psw-job-list"></div></section>
    <section id="psw-simulation-view" hidden aria-label="Synthetic economy demonstration"><div class="psw-synthetic-label">Synthetic demonstration</div><p class="psw-help">Synthetic economy and resident stories; balances here are separate from the live town.</p><div class="psw-section-head psw-economy-toolbar"><h3>Economy simulation</h3><button id="psw-economy-refresh" type="button">Refresh</button></div><p id="psw-economy-status" role="status" class="psw-help"></p><div id="psw-corpus-status" role="status" class="psw-corpus-counter"></div><p id="psw-corpus-help" class="psw-help"></p><div id="psw-economy-content" hidden><label for="psw-economy-day">Simulation day</label><select id="psw-economy-day"></select><div id="psw-economy-daily"></div><h4 class="psw-economy-heading">Residents by earnings</h4><div id="psw-economy-ranking"></div><div id="psw-economy-resident"></div><details class="psw-economy-provenance"><summary>About this demonstration</summary><div id="psw-economy-provenance"></div></details></div></section>
    <section id="psw-feed" class="psw-feed"><h3>City activity</h3><div id="psw-events"><p>The city is quiet.</p></div></section>
  </aside>
  <dialog id="psw-settings"><form id="psw-config-form"><header class="psw-header"><div><h2>Swarm setup</h2><p>This Mac hosts the shared city.</p></div><button type="button" data-close aria-label="Close setup">×</button></header><div id="psw-health"></div><label for="psw-backend">Resident model</label><select id="psw-backend" name="model_backend"><option value="claude-cli">Claude CLI</option><option value="sol">ChatGPT / Codex CLI</option><option value="openrouter">OpenRouter</option></select><div id="psw-openrouter-field" hidden><label for="psw-openrouter-key">OpenRouter key</label><input id="psw-openrouter-key" name="openrouter_api_key" type="password" autocomplete="off" placeholder="Keep saved key"></div><label for="psw-mongo-password">Atlas database password</label><input id="psw-mongo-password" name="mongodb_password" type="password" autocomplete="off" spellcheck="false" placeholder="Paste the exact database password" aria-describedby="psw-mongo-password-help"><p id="psw-mongo-password-help" class="psw-help">For the cluster already selected on this Mac. Paste the exact password from Chris.</p><details class="psw-advanced"><summary>Advanced connection settings</summary><label for="psw-mongo">MongoDB connection string (optional)</label><input id="psw-mongo" name="mongodb_uri" type="password" autocomplete="off" spellcheck="false" placeholder="Leave blank to keep saved connection"><label for="psw-database">Database</label><input id="psw-database" name="mongodb_database" placeholder="amble_sandbox"></details><label for="psw-embedding">Memory search</label><select id="psw-embedding" name="embedding_provider"><option value="local">Local embeddings</option><option value="voyage">Voyage embeddings</option></select><div id="psw-voyage-field" hidden><label for="psw-voyage-key">Voyage key</label><input id="psw-voyage-key" name="embedding_api_key" type="password" autocomplete="off" placeholder="Keep saved key"></div><p class="psw-help">Credentials are saved by the local server and never displayed back here.</p><button id="psw-save" type="submit">Save setup</button></form><div class="psw-worker-setup"><h3>Join from another computer</h3><p>Open this city on the same network.</p><code id="psw-join-address"></code><button id="psw-copy-link" type="button">Copy join link</button><p id="psw-copy-status" role="status"></p><p>Run in an Amble checkout. The worker prompts for the town’s join token.</p><code id="psw-worker-command"></code><div id="psw-workers"></div></div></dialog>
  <dialog id="psw-new-resident"><form id="psw-add-form"><header class="psw-header"><h2>Add resident</h2><button type="button" data-close aria-label="Close add resident">×</button></header><label for="psw-new-name">Name</label><input id="psw-new-name" name="name" required maxlength="40" autocomplete="off"><label for="psw-new-role">Work</label><select id="psw-new-role" name="role"><option value="healthcare">Healthcare</option><option value="finance">Finance</option><option value="construction">Construction</option></select><button type="submit" id="psw-add-submit">Add to city</button></form></dialog>
  <dialog id="psw-auth"><form id="psw-auth-form"><h2>Join this city</h2><label for="psw-token">Town access token</label><input id="psw-token" type="password" required autocomplete="off"><p class="psw-help">Stored in this browser on this computer.</p><button type="submit">Connect</button></form></dialog>
`;
document.body.append(root);
let state = null, selectedId = null, tab = 'home', selectedShop = null, pending = false, polling = false, connected = false, memoryVersion = 0;
let rosterKey = '', personKey = '', eventsKey = '';
const chats = new Map(), purchaseIds = new Map();
const minds = new Map(), mindRequests = new Map(), dreamRequests = new Set();
const residentLives=new Map();let lifeVersion=0,corpusStatus=null,corpusLoading=false;
let mindVersion = 0;
let mode='residents',jobFilter='all',jobSite=null,focusSite=null,jobsKey='',economy=null,economyLoading=false,economyDay=null,economyResident=null;
let token = '';
try { token = localStorage.getItem('swarm-token') || ''; } catch {}
const fragment = new URLSearchParams(location.hash.slice(1));
if (fragment.has('token')) {
  token = fragment.get('token');
  try { localStorage.setItem('swarm-token', token); } catch {}
  history.replaceState(null, '', location.pathname + location.search + '#now');
}
const roles = { healthcare:'Healthcare', finance:'Finance', construction:'Construction' };
const text = value => typeof value === 'string' ? value : value == null ? '' : String(value);
const date = value => new Date(typeof value === 'number' && value < 1e12 ? value * 1000 : value);
const node = (tag, className, value) => { const n=document.createElement(tag);if(className)n.className=className;if(value!==undefined)n.textContent=text(value);return n; };
const person = () => state?.residents?.find(value => value.id === selectedId);
const items = () => Array.isArray(state?.catalog) ? state.catalog : [];
function message(value, bad = false) {
  $('error').textContent=value;$('error').hidden=!value;$('error').classList.toggle('psw-bad',bad);
  const dialog=root.querySelector('dialog[open]');
  if(dialog){let status=dialog.querySelector('.psw-dialog-notice');if(!status){status=node('p','psw-dialog-notice');status.setAttribute('role','status');dialog.append(status);}status.textContent=value;status.hidden=!value;}
}
async function api(path, body) {
  const headers = { Accept:'application/json' };
  if (token) headers['X-Swarm-Token'] = token;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const response=await fetch(path,{method:body===undefined?'GET':'POST',headers,body:body===undefined?undefined:JSON.stringify(body),cache:'no-store'});
  let data;try{data=await response.json();}catch{throw new Error('The town server returned an unreadable response.');}
  if(response.status===401){if(!$('auth').open)$('auth').showModal();throw new Error('Enter the town access token to connect.');}
  if(!response.ok||data.ok===false)throw new Error(data.error||`Request failed (${response.status}).`);
  return data;
}
function open(value = true) {
  $('drawer').hidden=!value;$('toggle').setAttribute('aria-expanded',String(value));root.classList.toggle('psw-open',value);
  if(value&&document.body.dataset.view!=='now')document.querySelector('.studio-destinations [data-view="now"]')?.click();
  if(value&&mode==='residents'&&tab==='memory')loadMind();
}
function showMode(next) {
  mode=next;
  $('resident-view').hidden=mode!=='residents';$('jobs-view').hidden=mode!=='jobs';$('simulation-view').hidden=mode!=='simulation';
  $('feed').hidden=mode==='simulation';
  $('title').textContent={residents:'Swarm',jobs:'Job site',simulation:'Simulation'}[mode];
  $('jobs-button').setAttribute('aria-pressed',String(mode==='jobs'));
  $('simulation-button').setAttribute('aria-pressed',String(mode==='simulation'));
  open();if(mode==='jobs')renderJobs();if(mode==='simulation')loadEconomy();
}
function emit() {
  window.dispatchEvent(new CustomEvent('swarm:state',{detail:{...state,selected_resident_id:selectedId}}));
  window.dispatchEvent(new CustomEvent('amble:swarm-state',{detail:{...state,selected_resident_id:selectedId}}));
  window.PresentsExperience?.setSwarmState?.({...state,selected_resident_id:selectedId});
}
function select(id) {
  if(!state?.residents?.some(value=>value.id===id))return;
  if(mode!=='residents')showMode('residents');
  const changed=selectedId!==id;selectedId=id;personKey='';render();
  if(changed&&tab==='memory')memories();if(tab==='chat')renderChat();
  window.dispatchEvent(new CustomEvent('amble:swarm-select',{detail:{resident_id:id}}));
}
function render() {
  const residents=state.residents||[];
  if(!residents.some(value=>value.id===selectedId))selectedId=residents[0]?.id||null;
  const completed=residents.reduce((sum,value)=>sum+Number(value.jobs_completed||0),0);
  $('count').textContent=residents.length?`${residents.length}`:'';
  const hostWorkers=state.server?.local_workers,activeWorkers=state.stats?.active_workers??(state.workers||[]).filter(worker=>worker.status==='working').length;
  $('status').textContent=`${state.running?'Running':'Paused'} · ${completed} jobs · ${Number.isFinite(hostWorkers)?hostWorkers:'—'} host workers · ${activeWorkers} working`;
  root.classList.toggle('psw-running',!!state.running);
  $('run').textContent=state.running?'Pause':'Start';$('run').disabled=pending||!connected;
  $('step').disabled=pending||!!state.running||!connected;
  const key=JSON.stringify(residents.map(({id,name,role,color,status})=>({id,name,role,color,status})))+selectedId;
  if(key!==rosterKey){rosterKey=key;$('residents').replaceChildren(...residents.map(resident=>{
    const button=node('button','psw-resident');button.setAttribute('aria-pressed',String(resident.id===selectedId));
    const dot=node('span','psw-avatar','••');dot.style.setProperty('--resident-color',resident.color||'#8fabd1');
    const copy=node('span');copy.append(node('strong','',resident.name),node('small','',roles[resident.role]||resident.role));
    button.append(dot,copy);button.addEventListener('click',()=>select(resident.id));return button;
  }));}
  renderPerson();renderEvents();health();if(mode==='jobs')renderJobs();emit();
}
function renderJobs() {
  if(!state){$('job-list').replaceChildren(node('p','psw-help','Waiting for the live town.'));return;}
  const memory=state.health?.memory||state.health?.mongo||{},embedding=state.health?.embedding||{};
  const connection=!connected?'Town disconnected':memory.auth_failed?'Atlas authentication failed':memory.connected?'Atlas connected':memory.configured?'Atlas connection pending':'Atlas not configured';
  const reports=[`${connection} · ${memory.pending??'—'} queued writes`,`${embedding.semantic||memory.semantic?'Semantic recall':'Recall'}: ${embedding.model||memory.embedding_model||embedding.provider||memory.embedding_provider||'not reported'}`];
  if(memory.last_sync){const synced=date(memory.last_sync);if(!Number.isNaN(synced.getTime()))reports.push(`Last acknowledged write: ${synced.toLocaleTimeString([],{hour:'numeric',minute:'2-digit',second:'2-digit'})}`);}
  if(memory.error)reports.push(memory.error);
  reports.push('Atlas status is shared across all professions.');
  $('job-sync').replaceChildren(...reports.map(value=>node('p','',value)));
  const key=JSON.stringify([jobFilter,jobSite,state.jobs,state.worksites,(state.residents||[]).map(({id,name,role,jobs_completed,worker_id})=>({id,name,role,jobs_completed,worker_id})),(state.workers||[]).map(({id,status,resident_id})=>({id,status,resident_id}))]);
  if(key===jobsKey)return;jobsKey=key;
  $('job-filters').replaceChildren(...['all',...Object.keys(roles)].map(role=>{
    const button=node('button','',role==='all'?'All':roles[role]);button.dataset.role=role;button.setAttribute('aria-pressed',String(jobFilter===role));
    button.addEventListener('click',()=>{jobFilter=role;jobSite=null;renderJobs();});return button;
  }));
  const allResidents=state.residents||[];
  $('job-list').replaceChildren(...Object.keys(roles).filter(role=>jobFilter==='all'||role===jobFilter).map(role=>{
    const section=node('section','psw-job-group');section.dataset.role=role;
    const residents=allResidents.filter(value=>value.role===role),residentIds=new Set(residents.map(value=>value.id));
    const jobs=(state.jobs||[]).filter(value=>value.role===role&&['leased','available'].includes(value.status)).sort((a,b)=>(a.status==='leased'?0:1)-(b.status==='leased'?0:1));
    const working=jobs.filter(value=>value.status==='leased').length,available=jobs.filter(value=>value.status==='available').length;
    const workers=(state.workers||[]).filter(value=>value.status==='working'&&residentIds.has(value.resident_id));
    section.append(node('h3','',roles[role]),node('p','psw-job-totals',`${working} working · ${available} available · ${residents.reduce((sum,value)=>sum+Number(value.jobs_completed||0),0)} completed`));
    section.append(node('p','psw-help',workers.length?`Active workers: ${workers.map(value=>value.name||value.id).join(', ')}`:'No worker currently assigned.'));
    for(const job of jobs){
      const row=node('article','psw-job'),heading=node('div','psw-job-heading');
      heading.append(node('strong','',job.title),node('span','psw-wage',`${job.reward??'—'} credits`));row.append(heading);
      const assignment=node('div','psw-job-assignment'),resident=allResidents.find(value=>value.id===job.resident_id);
      assignment.append(node('span',`psw-job-state ${job.status}`,job.status==='leased'?'Working':'Available'));
      if(resident){const button=node('button','',resident.name);button.addEventListener('click',()=>select(resident.id));assignment.append(button);}
      if(job.status==='leased'&&resident?.worker_id)assignment.append(node('span','',resident.worker_id));row.append(assignment);
      const details=node('details','psw-task');details.append(node('summary','','Task details'),node('p','',job.description));
      const fields=node('dl');for(const [key,value] of Object.entries(job.task||{})){fields.append(node('dt','',key.replace(/_/g,' ')),node('dd','',typeof value==='object'?JSON.stringify(value):value));}details.append(fields);row.append(details);section.append(row);
    }
    if(!jobs.length)section.append(node('p','psw-help','No available or active jobs in this profession.'));
    return section;
  }));
  const incoming=(state.worksites||[]).filter(site=>jobFilter==='all'||site.profession===jobFilter);
  if(incoming.length){
    const section=node('section','psw-incoming-sites');section.append(node('h3','',incoming.some(site=>site.status==='replay_ready')?'Construction demonstrations':'Incoming worksites'));
    for(const site of incoming){
      const row=node('article','psw-incoming-site');row.dataset.siteId=site.id;row.classList.toggle('psw-site-selected',jobSite===site.id);row.tabIndex=-1;
      row.append(node('h4','',site.name),node('span','psw-site-status',site.status==='pending'?'Pending':site.status==='replay_ready'?'Replay ready':site.status),node('p','',site.detail));
      if(site.id==='arm-site'&&site.status==='replay_ready'){const launch=node('button','','Open conveyor lab');launch.addEventListener('click',()=>{location.hash='arm';});row.append(launch);}
      section.append(row);
    }
    $('job-list').append(section);
    if(focusSite){const target=[...section.children].find(child=>child.dataset?.siteId===focusSite);if(target){target.scrollIntoView({block:'nearest'});target.focus({preventScroll:true});focusSite=null;}}
  }
}
const count=value=>Number.isFinite(value)?value.toLocaleString():'—';
function economicTotals(values) {
  const list=node('div','psw-economic-totals');
  for(const [label,value] of values){const entry=node('span');entry.append(node('strong','',count(value)),document.createTextNode(label));list.append(entry);}
  return list;
}
async function loadEconomy(force=false) {
  loadCorpusStatus(force);
  if(economyLoading)return;
  if(economy&&!force){renderEconomy();return;}
  economyLoading=true;$('economy-refresh').disabled=true;$('economy-status').textContent='Loading the synthetic demonstration…';
  try{
    const result=await api('/api/economy');
    if(result.synthetic!==true)throw new Error('This view requires a labeled synthetic demonstration.');
    economy=result;
    if(!economy.available){$('economy-content').hidden=true;$('economy-status').textContent=economy.error||'The synthetic demonstration is unavailable.';return;}
    if(!Array.isArray(economy.days)||!Array.isArray(economy.residents))throw new Error('The simulation response is missing its days or residents.');
    if(!economy.days.some(day=>day.day===economyDay))economyDay=economy.days.at(-1)?.day;
    if(!economy.residents.some(resident=>resident.resident_id===economyResident))economyResident=rankedEconomyResidents()[0]?.resident_id;
    $('economy-day').replaceChildren(...economy.days.map(day=>{const option=node('option','',`Day ${day.day} · ${day.date}`);option.value=String(day.day);return option;}));
    renderEconomy();
  }catch(error){economy=null;$('economy-content').hidden=true;$('economy-status').textContent=error.message;}
  finally{economyLoading=false;$('economy-refresh').disabled=false;}
}
function rankedEconomyResidents() {
  return [...(economy?.residents||[])].sort((a,b)=>b.credits_earned-a.credits_earned||a.earnings_order_rank-b.earnings_order_rank);
}
function renderEconomy() {
  if(!economy?.available){$('economy-content').hidden=true;$('economy-status').textContent=economy?.error||'The synthetic demonstration is unavailable.';return;}
  const day=economy.days.find(value=>value.day===economyDay);if(!day)return;
  $('economy-content').hidden=false;$('economy-day').value=String(economyDay);
  $('economy-status').textContent=`${count(economy.summary?.population)} represented residents over ${count(economy.summary?.days)} days. Weighted cohort estimates${economy.provenance?.no_model_runs?'; no resident model runs':''}.`;
  const drops=day.item_drops_by_id?Object.values(day.item_drops_by_id).reduce((total,value)=>total+Number(value),0):undefined;
  $('economy-daily').replaceChildren(economicTotals([['credits earned today',day.credits_earned],['credits spent today',day.credits_spent],['packs opened today',day.packs_opened],['items dropped today',drops]]));
  const rolesTable=node('table','psw-economy-roles'),head=node('thead'),header=node('tr');
  for(const title of ['Profession','Jobs today','Credits earned'])header.append(node('th','',title));head.append(header);rolesTable.append(head);
  const body=node('tbody');for(const [role,details] of Object.entries(day.by_profession||{})){const row=node('tr');row.dataset.role=role;row.append(node('th','',roles[role]||role),node('td','',count(details.jobs_completed)),node('td','',count(details.credits_earned)));body.append(row);}rolesTable.append(body);$('economy-daily').append(rolesTable);
  const ranked=rankedEconomyResidents();
  $('economy-ranking').replaceChildren(node('p','psw-help',`Top earnings in the ${count(ranked.length)}-resident illustrative sample. Final states after day ${economy.summary?.days??'—'}; these residents are already included in the totals.`),...ranked.slice(0,12).map(resident=>{
    const row=node('div','psw-ranking');row.setAttribute('aria-current',String(resident.resident_id===economyResident));
    const button=node('button','',resident.resident_id);button.setAttribute('aria-label',`Inspect simulation resident ${resident.resident_id}`);button.addEventListener('click',()=>{economyResident=resident.resident_id;renderEconomy();$('economy-resident').scrollIntoView?.({block:'start'});});
    row.append(button,node('small','',roles[resident.profession]||resident.profession),node('strong','',count(resident.credits_earned)));return row;
  }));
  const picker=node('select');picker.id='psw-economy-resident-picker';picker.setAttribute('aria-label','Inspect any simulated resident');
  picker.append(...ranked.map(resident=>{const option=node('option','',`${resident.resident_id} · ${count(resident.credits_earned)} earned`);option.value=resident.resident_id;return option;}));picker.value=economyResident||'';picker.addEventListener('change',()=>{economyResident=picker.value;renderEconomy();$('economy-resident').scrollIntoView?.({block:'start'});});$('economy-ranking').append(picker);
  renderEconomyResident();
  const provenance=economy.provenance||{},notes=[`Simulation: ${economy.simulation_id}`,`World: ${economy.world_id}`,`Income model: ${provenance.income_mode||'not reported'}. Representative trajectories: ${count(provenance.representative_trajectories)}.`,provenance.sample_included_not_additive?'The detail sample is included in the population and loot totals.':'Sample accounting is not reported.',`Earnings source: ${provenance.source_earnings_sha256?'external source attached':'synthetic weighted cohort demonstration'}.`,provenance.validation_scope||'Validation scope not reported.'];
  $('economy-provenance').replaceChildren(...notes.map(value=>node('p','',value)));
  const catalog=node('details','psw-sim-catalog');catalog.append(node('summary','','Demonstration shop catalog'));
  for(const item of economy.catalog?.products||[])catalog.append(node('p','',`${item.display_name} · ${item.shop} · ${count(item.price_credits)} credits · ${item.kind}${item.kind==='pack'?' (repeatable pack)':''}`));$('economy-provenance').append(catalog);
}
function simulationAvatar(resident) {
  const avatar=node('div','psw-sim-avatar');avatar.setAttribute('aria-hidden','true');
  let seed=0;for(const letter of resident.resident_id)seed=(seed*31+letter.charCodeAt(0))>>>0;
  avatar.style.setProperty('--amble-color',`hsl(${seed%360} 48% 69%)`);
  avatar.style.setProperty('--amble-tilt',`${seed%9-4}deg`);
  avatar.append(node('span','psw-sim-creature'),node('span','psw-sim-shadow'));return avatar;
}
function itemBlock(id,quantity,catalog,atHome) {
  const item=catalog.get(id)||{},card=node('article','psw-item-block');card.dataset.itemId=id;
  const art=node('div','psw-item-art');art.dataset.item=id;art.setAttribute('aria-hidden','true');art.append(node('span','psw-item-object'));
  const caption=node('div','psw-item-caption');caption.append(node('strong','',item.display_name||id),node('span','psw-item-quantity',`× ${count(quantity)}`));
  card.append(art,caption);
  const duplicates=Number.isFinite(quantity)?Math.max(0,quantity-1):null;
  card.append(node('small','',atHome?`1 at home${duplicates?` · ${count(duplicates)} duplicate${duplicates===1?'':'s'}`:''}`:item.ownership==='consumable'?'Consumed immediately; not stored':'In inventory'));
  return card;
}
function renderEconomyResident() {
  const resident=economy.residents.find(value=>value.resident_id===economyResident);if(!resident){$('economy-resident').replaceChildren();return;}
  const catalog=new Map((economy.catalog?.items||[]).map(item=>[item.item_id,item]));
  const section=node('section','psw-sim-resident'),identity=node('div','psw-sim-identity'),copy=node('div');
  copy.append(node('h4','',resident.resident_id),node('p','',`${roles[resident.profession]||resident.profession} · synthetic resident`),node('p','',`Population earnings rank ${count(resident.earnings_order_rank)}`));
  identity.append(simulationAvatar(resident),copy);section.append(identity);
  section.append(node('p','',`Final state after day ${economy.summary?.days??'—'}. ${count(resident.jobs_completed)} jobs; ${count(resident.packs_opened)} packs opened.`));
  section.append(economicTotals([['credits earned',resident.credits_earned],['credits spent',resident.credits_spent],['credits remaining',resident.ending_balance],['home version',resident.home_version]]));
  section.append(node('h4','psw-economy-heading','Home & Inventory'),node('p','psw-help','Each block is one item type. Quantities include the first permanent copy placed at home; extra copies are duplicates.'));
  const owned=new Set(resident.owned_home_item_ids||[]),inventory=node('div','psw-item-grid');
  for(const [id,quantity] of Object.entries(resident.inventory_quantities||{}))inventory.append(itemBlock(id,quantity,catalog,owned.has(id)));
  if(!inventory.children.length)inventory.append(node('p','psw-help','No inventory items.'));section.append(inventory);
  const home=node('p','psw-sim-home');home.textContent=owned.size?`Placed at home: ${[...owned].map(id=>catalog.get(id)?.display_name||id).join(', ')}.`:'No permanent home items.';section.append(home);
  const life=node('section','psw-resident-life');life.id='psw-resident-life';life.setAttribute('aria-label','Synthetic resident day story');section.append(life);
  $('economy-resident').replaceChildren(section);loadResidentLife(resident.resident_id,economyDay,life);
}

async function loadCorpusStatus(force=false) {
  if(corpusLoading||corpusStatus&&!force)return;
  corpusLoading=true;$('corpus-status').textContent='Reading procedural corpus progress…';
  try{
    const result=await api('/api/resident-life/status');
    if(!Number.isFinite(result.actual_tokens)||!Number.isFinite(result.target_tokens))throw new Error(result.error||'Corpus token progress is not available.');
    corpusStatus=result;
    $('corpus-help').textContent=`Separate generated scenario: ${count(result.scale_resident_count)} distinct residents and ${count(result.scale_tokens)} tokens. The original economy has 200 linked sample residents (${count(result.original_demo_tokens)} story tokens). Its 5 million weighted population is not a count of individual narrative people.`;
    $('corpus-status').replaceChildren(node('span','psw-corpus-label','Measured synthetic tokens'),node('strong','psw-corpus-total',count(result.actual_tokens)),node('span','psw-corpus-details',`Target: ${count(result.target_tokens)} tokens · ${result.status||'status not reported'} · ${count(result.records)} day records. Tokenizer: ${result.tokenizer||'not reported'}.`));
    const archiveAvailable=result.local_scale_archive_available??result.archive_included_in_package;
    if(archiveAvailable===true)$('corpus-status').append(node('span','psw-corpus-archive','Full corpus stored on this host; Atlas contains the linked sample.'));
    else if(archiveAvailable===false)$('corpus-status').append(node('span','psw-corpus-archive','Measured on host; full corpus archive is not included in this copy.'));
  }catch(error){$('corpus-status').textContent=`Corpus progress unavailable. ${error.message}`;}
  finally{corpusLoading=false;}
}

async function loadResidentLife(residentId,day,target) {
  const version=++lifeVersion,key=`${residentId}:${day}`;
  target.replaceChildren(node('h4','psw-economy-heading','A day in this Amble’s life'),node('p','psw-life-label',`Day ${day} · synthetic procedural story`));
  const status=node('p','psw-help','Loading this resident’s day…');status.setAttribute('role','status');target.append(status);
  try{
    let story=residentLives.get(key);
    if(!story){story=await api(`/api/resident-life?resident_id=${encodeURIComponent(residentId)}&day=${encodeURIComponent(day)}`);if(story.synthetic===true&&story.available!==false&&story.resident_id===residentId&&Number(story.day)===day)residentLives.set(key,story);}
    if(version!==lifeVersion||residentId!==economyResident||day!==economyDay)return;
    if(story.available===false){status.textContent=story.error||story.reason||'No source ledger day is available for this resident.';return;}
    if(story.synthetic!==true||story.resident_id!==residentId||Number(story.day)!==day)throw new Error('The day story does not match this synthetic resident and day.');
    status.textContent='Procedural illustration grounded in simulation records. These are not lived agent memories.';
    const scenes=[['Morning',story.morning],['At work',null],['Memory note',story.memory],['Night',story.night]];
    for(const [title,body] of scenes){
      const scene=node('section','psw-life-scene');scene.append(node('h5','',title));
      if(title==='At work'){
        for(const line of story.work_conversation||[]){const speech=node('p','psw-life-speech');speech.append(node('strong','',`${line.speaker}: `),document.createTextNode(text(line.text)));scene.append(speech);}
        if(!story.work_conversation?.length)scene.append(node('p','psw-help','No work conversation recorded in this procedural day.'));
      }else scene.append(node('p','',body||'No passage available for this day.'));
      target.append(scene);
    }
    const ledger=story.ledger||{};target.append(economicTotals([['credits earned this day',ledger.credits_earned],['credits spent this day',ledger.credits_spent],['closing credits',ledger.closing_balance],['packs opened this day',ledger.packs_opened]]));
    const packs=node('details','psw-life-packs');packs.append(node('summary','',`Pack results · ${count(story.pack_openings?.length)} openings`));
    const names=new Map((economy.catalog?.items||[]).map(item=>[item.item_id,item.display_name])),products=new Map((economy.catalog?.products||[]).map(item=>[item.sku_id,item.display_name]));
    for(const pack of story.pack_openings||[]){
      const row=node('article','psw-life-pack');row.append(node('strong','',products.get(pack.sku_id)||pack.sku_id));
      const quantities=new Map();
      if(Array.isArray(pack.items)){for(const item of pack.items){const id=typeof item==='string'?item:item.item_id,quantity=typeof item==='string'?1:(item.quantity??(item.item_instance_id?1:null));quantities.set(id,(quantities.get(id)||0)+(quantity??NaN));}}
      else for(const [id,quantity] of Object.entries(pack.items||{}))quantities.set(id,quantity);
      const contents=[...quantities].map(([id,quantity])=>`${names.get(id)||id} × ${count(quantity)}`);
      row.append(node('p','',contents.length?contents.join(', '):pack.outcome==='empty'?'Empty pack':text(pack.outcome)));packs.append(row);
    }
    if(!story.pack_openings?.length)packs.append(node('p','psw-help','No pack openings in this source day.'));target.append(packs);
    const provenance=node('p','psw-life-provenance');provenance.textContent=`${story.resident_id} · day ${story.day} · ${story.generation_method||'procedural source'}`;target.append(provenance);
  }catch(error){if(version===lifeVersion&&residentId===economyResident&&day===economyDay)status.textContent=error.message;}
}

function renderPerson() {
  const resident=person();$('person').hidden=!resident;if(!resident)return;
  const key=JSON.stringify(resident)+JSON.stringify(state.catalog);if(key===personKey)return;personKey=key;
  $('name').textContent=resident.name;$('role').textContent=roles[resident.role]||resident.role;
  $('credits').textContent=`✦ ${resident.credits||0} credits`;
  const job=state.jobs?.find(value=>value.resident_id===resident.id&&value.status==='leased');
  $('activity').textContent=job?job.title:resident.status==='idle'?'At home, ready for the next turn':text(resident.status);
  $('progress').textContent=`${resident.jobs_completed||0} jobs completed${resident.worker_id?` · ${resident.worker_id}`:''}`;
  const home=(resident.home?.items||[]).map(item=>typeof item==='string'?items().find(value=>value.id===item)||{id:item,name:item}:item);
  $('items').replaceChildren(...(home.length?home.map(item=>node('span','',`${item.icon||'✦'} ${item.name||item.id}`)):[node('p','psw-help','Home is a fresh start. Purchases from Daily and Convenience appear here.')]));
  $('shops').replaceChildren(...['Daily','Convenience'].map(shop=>{
    const section=node('section','psw-shop');section.append(node('h4','',shop));
    section.dataset.shop=shop;section.hidden=!!selectedShop&&selectedShop!==shop;
    for(const item of items().filter(value=>(value.shop||value.store||'Daily').toLowerCase()===shop.toLowerCase())){
      const row=node('div','psw-product');row.append(node('span','psw-product-icon',item.icon||'✦'));
      const copy=node('span');copy.append(node('strong','',item.name),node('small','',item.description||''));row.append(copy);
      const owned=home.some(value=>(value.id||value.item_id)===item.id);
      const button=node('button','',owned?'At home':`✦ ${item.price}`);button.disabled=owned||Number(resident.credits)<item.price;
      button.setAttribute('aria-label',owned?`${item.name} is at home`:`Buy ${item.name} for ${item.price} credits`);
      button.addEventListener('click',()=>buy(resident.id,item.id,button));row.append(button);section.append(row);
    }
    return section;
  }));
}
function renderEvents() {
  const feed=state.feed||[],key=JSON.stringify(feed);if(key===eventsKey)return;eventsKey=key;
  $('events').replaceChildren(...(feed.length?feed.slice(0,12).map(event=>{
    const item=node('article','psw-event');item.append(node('p','',event.text||event.message));
    if(event.created_at){const time=date(event.created_at);if(!Number.isNaN(time.getTime()))item.append(node('time','',time.toLocaleTimeString([],{hour:'numeric',minute:'2-digit'})));}return item;
  }):[node('p','psw-help','No activity yet. One turn runs one resident’s real model task.')]));
}
function health() {
  const value=state?.health||{},model=value.model||{},memory=value.memory||value.mongo||{},embedding=value.embedding||{};
  const reports=[`Model: ${model.backend||'not configured'}${model.available===false?' unavailable':''}`,`MongoDB: ${memory.connected?'connected':memory.configured?'connection pending':'local memory active'}`,`Recall: ${embedding.provider||memory.embedding_provider||'starting'}${embedding.semantic?' semantic':''}`,`${memory.memories||0} memories · ${memory.pending||0} waiting to sync`];
  if(memory.error)reports.push(memory.error);if(memory.embedding_error)reports.push(memory.embedding_error);
  $('health').replaceChildren(...reports.map(value=>node('p','',value)));
  const server=state?.server||{},address=server.lan_address||location.hostname;
  const origin=/^https?:\/\//.test(address)?address:`http://${address}:${server.port||3190}`;
  $('join-address').textContent=`${origin}/hypernym/presents/`;
  $('copy-link').disabled=!token;
  $('worker-command').textContent=`venv/bin/python3 scripts/swarm_worker.py --server ${origin} --backend ${model.backend||'claude-cli'}`;
  $('workers').replaceChildren(...(state?.workers||[]).map(worker=>node('p','',`${worker.name||worker.id}: ${worker.status}${worker.error?' · '+worker.error:''}`)));
}
async function refresh() {
  if(polling)return;polling=true;
  try{state=await api('/api/state');connected=true;render();if(state.health?.error)message(state.health.error,true);
    if(mode==='residents'&&tab==='memory'&&!$('drawer').hidden&&minds.get(selectedId)?.data?.dreaming)loadMind();
  }
  catch(error){connected=false;$('status').textContent='Disconnected';$('run').disabled=true;$('step').disabled=true;if(mode==='jobs')renderJobs();message(error.message,true);}
  finally{polling=false;}
}
async function control(action) {
  if(pending)return;pending=true;$('run').disabled=true;$('step').disabled=true;
  try{await api('/api/control',{action});message(action==='step'?'One real model turn is underway.':'');await refresh();}
  catch(error){message(error.message,true);open();}
  finally{pending=false;if(state)render();}
}
async function buy(residentId,itemId,button) {
  const key=`${residentId}:${itemId}`;if(!purchaseIds.has(key))purchaseIds.set(key,crypto.randomUUID());
  button.disabled=true;button.textContent='Buying…';
  try{await api('/api/purchase',{resident_id:residentId,item_id:itemId,request_id:purchaseIds.get(key)});purchaseIds.delete(key);message('Purchase added to their home.');await refresh();}
  catch(error){message(error.message,true);button.disabled=false;button.textContent='Retry';}
}
function showTab(next) {
  tab=next;root.querySelectorAll('[data-tab]').forEach(button=>{const active=button.dataset.tab===tab;button.setAttribute('aria-pressed',String(active));$(button.dataset.tab).hidden=!active;});
  if(tab==='memory')memories();if(tab==='chat')renderChat();
}
async function memories() {
  if(!selectedId)return;const id=selectedId,version=++memoryVersion;
  loadMind(id);
  $('memories').replaceChildren(node('p','psw-help','Loading memories…'));
  try{const result=await api(`/api/memories?resident_id=${encodeURIComponent(id)}`);if(version!==memoryVersion||id!==selectedId)return;
    $('memories').replaceChildren(...(result.memories.length?result.memories.map(memory=>{const card=node('article','psw-memory');card.append(node('p','',memory.text||memory.content||memory.summary));card.append(node('small','',memory.kind||memory.scope||'memory'));return card;}):[node('p','psw-help','Work and conversations will leave memories here.')]));
  }catch(error){if(version===memoryVersion)$('memories').replaceChildren(node('p','psw-help',error.message));}
}
function renderMind() {
  const record=minds.get(selectedId),data=record?.data,busy=dreamRequests.has(selectedId);
  const enabled=data?.enabled===true,dreaming=data?.dreaming===true;
  $('dream').disabled=!enabled||dreaming||busy||!!record?.error;
  $('dream').textContent=busy?'Requesting…':dreaming?'Dreaming…':'Dream now';
  $('mind-status').textContent=record?.error||(!data?'Reading learned memory…':!enabled?'Learned memory is unavailable for this resident.':busy?'Requesting a dream for this resident…':dreaming?'This resident is dreaming. Learned memories will refresh as it finishes.':'No dream is running.');
  const result=data?.last_result,failed=result?.ok===false||!!result?.error;
  $('dream-result').hidden=!result||(!failed&&!result.skipped);
  $('dream-result').classList.toggle('psw-mind-error',failed);
  if(failed)$('dream-result').textContent=`Last dream did not finish: ${text(result.error||result.skipped||'No result was saved.')}`;
  else if(result?.skipped)$('dream-result').textContent=`Last dream skipped: ${text(result.skipped)}.`;
  $('mind-stats').hidden=!enabled;$('mind-content').hidden=!enabled;
  if(!enabled)return;
  const stats=data.stats||{};
  $('mind-stats').replaceChildren(...[['turns','turns'],['memories','memories'],['lessons','active lessons'],['dreams','dreams']].map(([key,label])=>node('span','',`${stats[key]??0} ${label}`)));
  function learned(rows,lesson=false){
    if(!Array.isArray(rows)||!rows.length)return [node('p','psw-help',lesson?'No lessons learned yet.':'No learned memories yet.')];
    return rows.map(value=>{
      const retired=lesson&&value.active===false,card=node('article',`psw-learned${retired?' psw-retired':''}`);
      card.append(node('p','',value.text));
      const when=value.when?date(value.when):null;
      const parts=[lesson?(retired?'Retired lesson':'Active lesson'):value.kind||'memory'];
      if(when&&!Number.isNaN(when.getTime()))parts.push(when.toLocaleDateString());
      card.append(node('small','',parts.join(' · ')));return card;
    });
  }
  $('learned-memories').replaceChildren(...learned(data.memories));$('lessons').replaceChildren(...learned(data.lessons,true));
  const last=Array.isArray(data.dreams)?data.dreams[0]:null;$('last-dream').hidden=!last;
  if(last)$('last-dream').textContent=`Last saved dream: ${last.turns??0} turns reviewed, ${last.memories??0} memories and ${last.lessons??0} lessons added, ${last.retired??0} lessons retired.`;
}
async function loadMind(id=selectedId,force=false) {
  if(!id||!state?.residents?.some(value=>value.id===id))return;
  if(mindRequests.has(id)&&!force){if(id===selectedId)renderMind();return;}
  const version=++mindVersion;mindRequests.set(id,version);
  if(!minds.has(id))minds.set(id,{data:null,error:''});
  if(id===selectedId)renderMind();
  try{
    const data=await api(`/api/mind?resident_id=${encodeURIComponent(id)}`);
    if(mindRequests.get(id)!==version)return;
    minds.set(id,{data,error:''});
  }catch(error){if(mindRequests.get(id)===version)minds.set(id,{data:minds.get(id)?.data,error:error.message});}
  finally{if(mindRequests.get(id)===version){mindRequests.delete(id);if(id===selectedId)renderMind();}}
}
async function dream() {
  const id=selectedId,record=minds.get(id);
  if(!id||record?.data?.enabled!==true||record.data.dreaming||record.error||dreamRequests.has(id))return;
  dreamRequests.add(id);renderMind();
  try{
    const result=await api('/api/dream',{resident_id:id});
    if(['working','already_working'].includes(result.status))minds.set(id,{data:{...record.data,dreaming:true},error:''});
    await loadMind(id,true);
  }catch(error){minds.set(id,{data:minds.get(id)?.data,error:error.message});}
  finally{dreamRequests.delete(id);if(id===selectedId)renderMind();}
}
function renderChat() {
  const history=chats.get(selectedId)||[];
  $('messages').replaceChildren(...(history.length?history.map(value=>node('p',`psw-chat-message psw-${value.role}`,value.text)):[node('p','psw-help','Talk with this resident. Their memory is their own.')]));
  $('messages').scrollTop=$('messages').scrollHeight;
}
$('toggle').addEventListener('click',()=>{if(mode!=='residents')showMode('residents');else open($('drawer').hidden);});$('close').addEventListener('click',()=>{open(false);$('toggle').focus();});
$('jobs-button').addEventListener('click',()=>{jobFilter='all';jobSite=null;showMode('jobs');});
$('simulation-button').addEventListener('click',()=>showMode('simulation'));
$('economy-refresh').addEventListener('click',()=>loadEconomy(true));
$('economy-day').addEventListener('change',()=>{economyDay=Number($('economy-day').value);renderEconomy();});
$('run').addEventListener('click',()=>control(state?.running?'pause':'start'));$('step').addEventListener('click',()=>control('step'));
$('drawer').addEventListener('keydown',event=>{if(event.key==='Escape'){open(false);$('toggle').focus();}});
root.querySelectorAll('[data-tab]').forEach(button=>button.addEventListener('click',()=>{selectedShop=null;personKey='';renderPerson();showTab(button.dataset.tab);}));
root.querySelectorAll('[data-close]').forEach(button=>button.addEventListener('click',()=>button.closest('dialog').close()));
$('refresh-memory').addEventListener('click',memories);
$('dream').addEventListener('click',dream);
$('add').addEventListener('click',()=>$('new-resident').showModal());
function configFields(){ $('voyage-field').hidden=$('embedding').value!=='voyage';$('openrouter-field').hidden=$('backend').value!=='openrouter'; }
$('backend').addEventListener('change',configFields);$('embedding').addEventListener('change',configFields);
$('copy-link').addEventListener('click',async()=>{
  const button=$('copy-link');button.disabled=true;
  try{
    if(!token)throw new Error('Connect with this town’s access token before copying a join link.');
    const address=$('join-address').textContent;
    if(!address)throw new Error('Wait for the city server to connect, then try again.');
    await navigator.clipboard.writeText(`${address}#token=${encodeURIComponent(token)}`);
    $('copy-status').textContent='Join link copied. It includes this town’s access token.';
  }catch(error){$('copy-status').textContent=error.message||'The clipboard is unavailable. Open this page on the host computer and try again.';}
  finally{button.disabled=!token;}
});
$('setup').addEventListener('click',()=>{const backend=state?.health?.model?.backend;if(backend)$('backend').value=backend;$('embedding').value=state?.health?.embedding?.provider==='voyage'?'voyage':'local';configFields();health();$('settings').showModal();});
$('auth-form').addEventListener('submit',event=>{event.preventDefault();token=$('token').value.trim();try{localStorage.setItem('swarm-token',token);}catch{}$('token').value='';$('auth').close();refresh();});
$('config-form').addEventListener('submit',async event=>{event.preventDefault();$('save').disabled=true;const body=Object.fromEntries(new FormData(event.target));for(const key of Object.keys(body))if(!String(body[key]).trim())delete body[key];try{await api('/api/config',body);$('mongo').value='';$('mongo-password').value='';$('voyage-key').value='';$('openrouter-key').value='';message('Swarm setup saved.');await refresh();$('settings').close();}catch(error){message(error.message,true);open();}finally{$('save').disabled=false;}});
$('add-form').addEventListener('submit',async event=>{event.preventDefault();$('add-submit').disabled=true;try{const result=await api('/api/residents',Object.fromEntries(new FormData(event.target)));$('new-resident').close();event.target.reset();await refresh();select(result.resident?.id||result.id);message('Resident added to the city.');}catch(error){message(error.message,true);}finally{$('add-submit').disabled=false;}});
$('chat-form').addEventListener('submit',async event=>{
  event.preventDefault();const id=selectedId,value=$('message').value.trim();if(!id||!value)return;
  const history=chats.get(id)||[];chats.set(id,history);history.push({role:'user',text:value});const reply={role:'assistant',text:'Thinking…'};history.push(reply);$('message').value='';$('send').disabled=true;renderChat();
  try{const result=await api('/api/chat',{resident_id:id,message:value});reply.text=result.reply||result.response||'No text reply was returned.';await refresh();}
  catch(error){reply.text=`This turn could not be completed: ${error.message}`;}
  finally{$('send').disabled=false;if(id===selectedId)renderChat();}
});
$('import-button').addEventListener('click',async()=>{
  const file=$('import-file').files[0];if(!file){message('Choose a sandbox conversation JSON file first.',true);return;}if(file.size>95000){message('Choose a JSON file smaller than 95 KB.',true);return;}
  const id=selectedId;$('import-button').disabled=true;
  try{const parsed=JSON.parse(await file.text()),rows=Array.isArray(parsed)?parsed:parsed.messages;if(!Array.isArray(rows))throw new Error('The JSON needs a messages array.');const result=await api('/api/import',{resident_id:id,messages:rows});message(`${result.imported} messages imported.`);$('import-file').value='';if(selectedId===id)memories();await refresh();}
  catch(error){message(error.message,true);}finally{$('import-button').disabled=false;}
});
window.addEventListener('amble:swarm-resident-click',event=>{select(event.detail?.resident_id);open();});
window.addEventListener('presents:resident',event=>{select(event.detail?.resident_id);open();});
window.addEventListener('presents:place',event=>{
  const place=event.detail?.place;if(!['store','casino','house'].includes(place))return;
  showMode('residents');selectedShop=place==='store'?'Convenience':place==='casino'?'Daily':null;
  personKey='';renderPerson();showTab('home');open();
  if(selectedShop)root.querySelector(`[data-shop="${selectedShop}"]`)?.scrollIntoView({block:'nearest'});
});
window.addEventListener('swarm:workplace-select',event=>{jobFilter=Object.hasOwn(roles,event.detail?.role)?event.detail.role:'all';jobSite=typeof event.detail?.site_id==='string'?event.detail.site_id:null;focusSite=jobSite;jobsKey='';showMode('jobs');});
window.AmbleSwarm={get state(){return state;},get selectedId(){return selectedId;},select,open,refresh};
refresh();
const interval=setInterval(()=>{if(!document.hidden)refresh();},2000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
window.addEventListener('pagehide',()=>clearInterval(interval),{once:true});
