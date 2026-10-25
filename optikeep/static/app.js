/* Copyright (C) 2026 Jason Froebe. GPL-3.0-only. */
const byId = id => document.getElementById(id);
async function request(path, method = 'GET', body) {
  byId('status').textContent = 'Working…';
  try {
    const response = await fetch('/api/v1/' + path, {method, headers: {'Authorization': 'Bearer ' + byId('token').value, 'Content-Type': 'application/json'}, body: body ? JSON.stringify(body) : undefined});
    if (!response.ok) throw new Error('Request failed (' + response.status + ')');
    const data = await response.json();
    byId('results').replaceChildren();
    const entries = Array.isArray(data) ? data : [data];
    for (const entry of entries) {
      const card = document.createElement('article'); card.className = 'card';
      const pre = document.createElement('pre'); pre.textContent = JSON.stringify(entry, null, 2); card.append(pre);
      if (entry.id) { const button = document.createElement('button'); button.textContent = 'View analysis progress'; button.onclick = () => request('runs/' + entry.id); card.append(button); const duplicates = document.createElement('button'); duplicates.textContent = 'Review exact candidates'; duplicates.onclick = () => request('runs/' + entry.id + '/exact-candidates'); card.append(duplicates); }
      byId('results').append(card);
    }
    byId('status').textContent = entries.length ? 'Updated' : 'No scans yet';
  } catch (error) { byId('status').textContent = error.message; }
}
byId('connect').onclick = byId('history').onclick = () => request('runs');
byId('settings').onclick = () => request('settings');
byId('scan').onclick = () => request('runs', 'POST', {trust_metadata_cache: false});
byId('theme').onclick = () => document.body.classList.toggle('light');
