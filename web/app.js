let state, page = 'overview', selectedTeam = null;
const $ = selector => document.querySelector(selector);
const money = number => new Intl.NumberFormat('en-CA', {style:'currency',currency:'USD',maximumFractionDigits:0}).format(number || 0);
const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));

async function load() {
  state = await fetch('/api/state').then(response => response.json());
  renderShell(); render();
}

function renderShell() {
  const simulation = state.simulation;
  $('#date').textContent = simulation?.simulation_date || 'No active simulation';
  $('#phase').textContent = `${simulation?.season || '—'} · ${simulation?.phase || '—'} · Day ${simulation?.day || 0}`;
  $('#cap').textContent = money(state.cap.cap_space);
  $('#size').textContent = state.cap.active_players ?? state.roster.length;
  $('#unread').textContent = state.inbox.filter(item => item.status === 'UNREAD').length;
  $('#nav').innerHTML = state.nav.map(item => `<button data-page="${item.id}" class="${page === item.id ? 'active' : ''}">${escapeHtml(item.label)}</button>`).join('');
  document.querySelectorAll('nav button').forEach(button => button.onclick = () => { page = button.dataset.page; renderShell(); render(); });
}

const card = (title,value,subtitle,target) => `<article class="card click" data-target="${target}"><span class="muted">${title}</span><div class="value">${value}</div><span class="muted">${subtitle}</span></article>`;

function overview() {
  return `<h1>Good morning, General Manager</h1><p class="subtitle">Your Edmonton Oilers control room · Next deadline: Free agency</p><div class="grid">
    ${card('CAP SPACE',money(state.cap.cap_space),`${money(state.cap.total_cap_charge)} committed`,'cap')}
    ${card('ACTIVE ROSTER',state.roster.filter(player => player.level === 'NHL').length,'Maximum 23 players','roster')}
    ${card('UNREAD DECISIONS',state.inbox.filter(item => item.status === 'UNREAD').length,'Inbox and offers','inbox')}
    ${card('DATA STATUS',state.audit.ok ? 'Passed' : 'Action required',`${state.audit.failures?.length || 0} verification items`,'settings')}
    <article class="card wide"><h2>Priority GM actions</h2>${state.inbox.slice(0,4).map(item => `<p><span class="tag">${escapeHtml(item.priority)}</span> <b>${escapeHtml(item.subject)}</b><br><span class="muted">${escapeHtml(item.sender)}</span></p>`).join('')}</article>
    <article class="card wide"><h2>Latest news</h2>${state.news.slice(0,4).map(item => `<p><b>${escapeHtml(item.headline)}</b><br><span class="muted">${escapeHtml(item.kind)}</span></p>`).join('')}</article>
  </div>`;
}

function roster(level='NHL', team='EDM') {
  const source = team === 'EDM' ? state.roster : state.league_rosters.filter(player => player.team_id === team);
  const players = source.filter(player => player.level === level);
  return `<h1>${team === 'EDM' ? (level === 'NHL' ? 'Roster' : 'AHL / Farm Team') : `${team} Roster`}</h1>
    <p class="subtitle">Real-world baseline copied into isolated simulation state.</p>
    <div class="toolbar"><input id="search" placeholder="Search players"><select id="pos"><option value="">All positions</option><option>F</option><option>D</option><option>G</option></select></div>
    <table><thead><tr><th>#</th><th>Player</th><th>Pos</th><th>Age</th><th>Status</th><th>Cap hit</th><th>Expiry</th>${team === 'EDM' ? '<th>Actions</th>' : ''}</tr></thead><tbody>
    ${players.map(player => `<tr data-name="${escapeHtml(player.full_name.toLowerCase())}" data-pos="${escapeHtml(player.primary_position)}"><td>${player.jersey_number || '—'}</td><td>${escapeHtml(player.full_name)}</td><td>${escapeHtml(player.primary_position || 'UNKNOWN')}</td><td>${player.age_at_start || '—'}</td><td><span class="tag">${escapeHtml(player.status)}</span></td><td>${money(player.cap_hit)}</td><td>${escapeHtml(player.expiry_status || 'UNKNOWN')}</td>${team === 'EDM' ? `<td class="actions"><button onclick="act('${player.id}','${level === 'NHL' ? 'AHL' : 'NHL'}')">${level === 'NHL' ? 'Assign to AHL' : 'Recall'}</button><button onclick="act('${player.id}','TRADE_BLOCK')">Trade block</button><button onclick="act('${player.id}','WAIVERS')">Waivers</button></td>` : ''}</tr>`).join('')}
    </tbody></table>`;
}

function inbox() {
  return `<h1>Inbox</h1><p class="subtitle">Decisions update the simulation event log.</p><div class="grid">${state.inbox.map(message => `<article class="card wide"><span class="tag">${escapeHtml(message.priority)}</span><h2>${escapeHtml(message.subject)}</h2><p class="muted">${escapeHtml(message.sender)} · ${escapeHtml(message.category)}</p><p>${escapeHtml(message.content)}</p><div class="actions">${JSON.parse(message.actions).map(action => `<button onclick="msg(${message.id},'${escapeHtml(action)}')">${escapeHtml(action)}</button>`).join('')}</div></article>`).join('')}</div>`;
}

function contractsPage() {
  const contracts=state.contracts.filter(contract=>contract.team_id==='EDM');
  return `<h1>Contracts</h1><p class="subtitle">Simulation contracts move with players after completed trades.</p><table><thead><tr><th>Player</th><th>Position</th><th>Cap hit</th><th>Salary</th><th>Expires</th><th>Status</th><th>Clause</th></tr></thead><tbody>${contracts.map(contract=>`<tr><td>${escapeHtml(contract.full_name)}</td><td>${escapeHtml(contract.primary_position)}</td><td>${money(contract.cap_hit)}</td><td>${money(contract.salary)}</td><td>${contract.end_season || 'UNKNOWN'}</td><td>${escapeHtml(contract.expiry_status || 'UNKNOWN')}</td><td>${contract.nmc?'NMC':escapeHtml(contract.ntc || '—')}</td></tr>`).join('')}</tbody></table>`;
}

function otherTeams() {
  if (selectedTeam) return teamDetail(selectedTeam);
  return `<h1>Other Teams</h1><p class="subtitle">Browse every NHL roster, contract, and cap position.</p><table><thead><tr><th>Team</th><th>Roster</th><th>Cap charge</th><th>Cap space</th><th></th></tr></thead><tbody>${state.teams.filter(team => team.id !== 'EDM').map(team => { const cap=state.team_caps[team.id] || {}; return `<tr><td>${escapeHtml(team.name)} (${team.abbreviation})</td><td>${cap.active_players || 0}</td><td>${money(cap.total_cap_charge)}</td><td>${money(cap.cap_space)}</td><td class="actions"><button onclick="openTeam('${team.id}')">View roster</button><button onclick="openTrade('${team.id}')">Propose trade</button></td></tr>`; }).join('')}</tbody></table>`;
}

function teamDetail(teamId) {
  const team = state.teams.find(item => item.id === teamId); const cap=state.team_caps[teamId] || {};
  return `<div class="toolbar"><button class="primary" onclick="selectedTeam=null;render()">← All teams</button><button class="primary" onclick="openTrade('${teamId}')">Propose trade</button></div><h1>${escapeHtml(team?.name || teamId)}</h1><p class="subtitle">Cap charge ${money(cap.total_cap_charge)} · Cap space ${money(cap.cap_space)} · ${cap.active_players || 0} active players</p>${roster('NHL',teamId)}`;
}

const assetChecks = (team, side) => {
  const players=state.league_rosters.filter(player => player.team_id===team && player.status==='ACTIVE');
  const picks=state.draft_picks.filter(pick => pick.current_owner_id===team);
  return `<h2>${team} assets</h2>${players.map(player=>`<label class="asset"><input type="checkbox" data-${side}-player value="${player.id}"> ${escapeHtml(player.full_name)} · ${escapeHtml(player.primary_position)} · ${money(player.cap_hit)}</label>`).join('') || '<p class="muted">No active players loaded.</p>'}<h2>Draft picks</h2>${picks.map(pick=>`<label class="asset"><input type="checkbox" data-${side}-pick value="${pick.pick_id}"> ${pick.draft_year} Round ${pick.round} (${escapeHtml(pick.status)})</label>`).join('') || '<p class="muted">No verified tradeable picks loaded.</p>'}`;
};

function trades() {
  const partner=selectedTeam || state.teams.find(team=>team.id!=='EDM')?.id;
  return `<h1>Trade Centre</h1><p class="subtitle">CPU teams demand balanced value, legal cap outcomes, and reasonable roster construction.</p><div class="toolbar"><label>Trade partner <select id="trade-team" onchange="selectedTeam=this.value;render()">${state.teams.filter(team=>team.id!=='EDM').map(team=>`<option value="${team.id}" ${team.id===partner?'selected':''}>${escapeHtml(team.name)}</option>`).join('')}</select></label></div><div class="grid"><article class="card wide">${assetChecks('EDM','user')}</article><article class="card wide">${assetChecks(partner,'cpu')}</article><article class="card full"><div class="actions"><button onclick="tradeRequest(false)">Evaluate trade</button><button class="primary" onclick="tradeRequest(true)">Submit to CPU GM</button></div><div id="trade-result" class="subtitle"></div></article><article class="card full"><h2>Recent negotiations</h2>${state.trade_history.map(item=>`<p><span class="tag">${escapeHtml(item.status)}</span> ${escapeHtml(item.from_team)} → ${escapeHtml(item.to_team)}</p>`).join('')||'<p class="muted">No negotiations yet.</p>'}</article></div>`;
}

function generic() {
  const label=state.nav.find(item=>item.id===page)?.label;
  const data=page==='news'?state.news:page==='gms'?state.gms:page==='draft'?state.draft:[];
  return `<h1>${escapeHtml(label)}</h1><p class="subtitle">Database-connected module · simulation ${state.simulation?.id?.slice(0,8) || '—'}</p>${data.length?`<table><tbody>${data.map(item=>`<tr>${Object.values(item).slice(0,7).map(value=>`<td>${escapeHtml(value ?? 'UNKNOWN')}</td>`).join('')}</tr>`).join('')}</tbody></table>`:`<div class="card"><h2>No verified records yet</h2><p class="muted">UNKNOWN — DATA VERIFICATION REQUIRED. The module is active and populated only by verified sync or simulation events; no facts are fabricated.</p></div>`}`;
}

function cap() { return `<h1>Salary Cap</h1><p class="subtitle">Always calculated from active roster and contract records.</p><div class="grid">${Object.entries(state.cap).map(([key,value])=>card(key.replaceAll('_',' ').toUpperCase(),typeof value==='number'?money(value):String(value),'Data-driven','cap')).join('')}</div>`; }

function render() {
  const label=state.nav.find(item=>item.id===page)?.label || 'Overview'; $('#crumb').textContent=label;
  $('#content').innerHTML=page==='overview'?overview():page==='roster'?roster():page==='ahl'?roster('AHL'):page==='inbox'?inbox():page==='contracts'?contractsPage():page==='cap'?cap():page==='teams'?otherTeams():page==='trades'?trades():generic();
  document.querySelectorAll('[data-target]').forEach(item=>item.onclick=()=>{page=item.dataset.target;renderShell();render();});
  const query=$('#search'),position=$('#pos'); if(query) for(const element of [query,position]) element.oninput=()=>document.querySelectorAll('tbody tr').forEach(row=>row.hidden=!row.dataset.name.includes(query.value.toLowerCase())||(position.value&&!row.dataset.pos.includes(position.value)));
}

async function post(url,body={}) { const response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json; charset=utf-8'},body:JSON.stringify(body)}); const result=await response.json(); if(!response.ok) throw new Error(result.error); return result; }
async function act(player_id,action){if(confirm(`Confirm ${action}?`)){try{await post('/api/roster-action',{player_id,action});await load();}catch(error){alert(error.message);}}}
async function msg(id,action){try{await post(`/api/inbox/${id}`,{action});await load();}catch(error){alert(error.message);}}
function openTeam(team){selectedTeam=team;page='teams';renderShell();render();}
function openTrade(team){selectedTeam=team;page='trades';renderShell();render();}
const checked = selector => [...document.querySelectorAll(selector+':checked')].map(input=>input.value);
async function tradeRequest(submit){const body={cpu_team:$('#trade-team').value,user_players:checked('[data-user-player]'),cpu_players:checked('[data-cpu-player]'),user_picks:checked('[data-user-pick]').map(Number),cpu_picks:checked('[data-cpu-pick]').map(Number)};const target=$('#trade-result');try{const result=await post(submit?'/api/trades/submit':'/api/trades/evaluate',body);target.innerHTML=`<b class="${result.accepted?'':'danger'}">${result.accepted?'CPU GM accepts the value':'CPU GM rejects the proposal'}</b><br>${result.reasons.map(escapeHtml).join('<br>')||'Balanced value and cap-compliant for both teams.'}`;if(submit&&result.accepted)await load();}catch(error){target.innerHTML=`<span class="danger">${escapeHtml(error.message)}</span>`;}}
$('#advance').onclick=async()=>{try{await post('/api/advance');await load();}catch(error){alert(error.message);}};
load();
