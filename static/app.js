// MandiMitra dashboard: progressive section loading, i18n, passport, advisor, market
const $ = id => document.getElementById(id);
const f = (v, d = 2) => v == null || isNaN(v) ? '–' : (+v).toFixed(d);
const inr = v => v == null ? '–' : '₹' + Math.round(v).toLocaleString('en-IN');
const MN = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const st = { lat: 12.5, lon: 76.85, rad: 100, lang: 'en', data: {}, tab: 'field' };

// ------------------------------------------------------------- i18n (key labels)
const KN = {
 tagline: 'ಉಪಗ್ರಹ-ಆಧಾರಿತ ಕೃಷಿ ಮಾಹಿತಿ · ಪ್ರತಿ ರೈತನಿಗೂ ಉಚಿತ', tabField: '🛰 ಹೊಲ', tabMarket: '💰 ಎಲ್ಲಿ ಮಾರಬೇಕು', tabPassport: '🛡 ಗುಣಮಟ್ಟ ಪಾಸ್‌ಪೋರ್ಟ್', tabAdvisor: '🤖 ಸಲಹೆಗಾರ',
 locLabel: 'ಹೊಲದ ಸ್ಥಳ: ಅಕ್ಷಾಂಶ, ರೇಖಾಂಶ ಅಥವಾ Google Maps ಲಿಂಕ್', radius: 'ತ್ರಿಜ್ಯ (ಮೀ)', crop: 'ಬೆಳೆ', analyze: '🛰 ವಿಶ್ಲೇಷಿಸಿ', demoFarms: 'ಮಾದರಿ ಹೊಲಗಳು:', clickMap: 'ಅಥವಾ ನಕ್ಷೆಯ ಮೇಲೆ ಕ್ಲಿಕ್ ಮಾಡಿ',
 w1: 'ಹೊಲದ ಆರೋಗ್ಯ ಅಂಕ', w1d: 'ಉಪಗ್ರಹ, ಮಣ್ಣಿನ ತೇವಾಂಶ ಮತ್ತು ಹವಾಮಾನ ಅಪಾಯದಿಂದ 0–100 ಅಂಕ, ವಿವರಣೆಯೊಂದಿಗೆ.', w2: 'ಗುಣಮಟ್ಟ ಪಾಸ್‌ಪೋರ್ಟ್ + QR', w2d: 'ಖರೀದಿಗೂ ಮೊದಲು ಖರೀದಿದಾರರಿಗೆ ಉಪಗ್ರಹ ಸಾಕ್ಷ್ಯ ಮತ್ತು ಒಳಸುರಿ ದಾಖಲೆ.',
 w3: 'ನಿವ್ವಳ ಬೆಲೆ ಆಧಾರಿತ ಮಂಡಿ ಶ್ರೇಣಿ', w3d: 'ಸಾಗಣೆ, ಶುಲ್ಕ, ಹಾಳಾಗುವಿಕೆ ಕಳೆದು ಕೈಗೆ ಸಿಗುವ ಹಣದ ಪ್ರಕಾರ.', w4: 'ಕನ್ನಡ ಧ್ವನಿ ಸಲಹೆಗಾರ', w4d: 'ದಿನದ ಕೆಲಸ: ನೀರಾವರಿ, ಸಿಂಪಡಣೆ ಸಮಯ, ಕೀಟ ಅಪಾಯ, ಸಾವಯವ ಗೊಬ್ಬರ.',
 w5: 'ಉಚಿತ ಮತ್ತು ಮುಕ್ತ ದತ್ತಾಂಶ', w5d: 'Sentinel-2, Open-Meteo, Agmarknet, OSM. ಯಾವುದೇ ಚಂದಾ ಇಲ್ಲ.',
 healthScore: '💯 ಹೊಲದ ಆರೋಗ್ಯ ಅಂಕ', todayCard: '🗓 ಇಂದಿನ ಕಾರ್ಯ ಸೂಚಿ', weatherNow: '🌤 ಈಗಿನ ಹವಾಮಾನ', liveSat: '🛰 ನೇರ ಉಪಗ್ರಹ ಚಿತ್ರ', location: '📍 ಸ್ಥಳ',
 indices: '🌿 ಸಸ್ಯ ಸೂಚ್ಯಂಕಗಳು', cropEst: '🌾 ಬೆಳೆ ಅಂದಾಜು', irrigation: '💧 ನೀರಾವರಿ', ndviTrend: '📈 NDVI · 12 ತಿಂಗಳ ಬೆಳೆ ಕ್ಯಾಲೆಂಡರ್', spray: '🧴 ಸಿಂಪಡಣೆ ಸಮಯ ಮತ್ತು ಕೀಟ ಅಪಾಯ',
 forecast: '📅 7 ದಿನಗಳ ಮುನ್ಸೂಚನೆ ಮತ್ತು ಎಚ್ಚರಿಕೆಗಳು', soil: '🪱 ಮಣ್ಣು', climate: '🌡 ಕಳೆದ 30 ದಿನಗಳು', landcover: '🗺 ಭೂ ಹೊದಿಕೆ', revisit: '🛰 ಉಪಗ್ರಹ ಸಂಚಾರ',
 wts: '💰 ಎಲ್ಲಿ ಮಾರಬೇಕು · ಕೈಗೆ ಹೆಚ್ಚು ಹಣ', commodity: 'ಸರಕು', variety: 'ತಳಿ', qty: 'ಪ್ರಮಾಣ (ಕ್ವಿಂ)', vehicle: 'ವಾಹನ', findMandi: '💰 ಉತ್ತಮ ಮಂಡಿ ಹುಡುಕಿ',
 ppTitle: '🛡 ಹೊಲದ ಗುಣಮಟ್ಟ ಪಾಸ್‌ಪೋರ್ಟ್', ppIntro: 'ಪ್ರತಿ ಹೊಲಕ್ಕೆ ಹಂಚಬಹುದಾದ ಪುಟ: ದಿನಾಂಕ ಸಹಿತ ಉಪಗ್ರಹ ಸಾಕ್ಷ್ಯ, ಬೆಳೆ ಆರೋಗ್ಯ ಪ್ರವೃತ್ತಿ, ರೈತರ ಒಳಸುರಿ ದಾಖಲೆ ಮತ್ತು ಸಾವಯವ ಅಂಕ. ಖರೀದಿದಾರರು QR ಸ್ಕ್ಯಾನ್ ಮಾಡುತ್ತಾರೆ.',
 ppSelect: 'ನಿಮ್ಮ ಪಾಸ್‌ಪೋರ್ಟ್‌ಗಳು', ppNew: '➕ ಈ ಸ್ಥಳಕ್ಕೆ ಪಾಸ್‌ಪೋರ್ಟ್ ರಚಿಸಿ', farmer: 'ರೈತರ ಹೆಸರು', village: 'ಗ್ರಾಮ', acres: 'ವಿಸ್ತೀರ್ಣ (ಎಕರೆ)', ppCreate: 'ಪಾಸ್‌ಪೋರ್ಟ್ ರಚಿಸಿ',
 ppLog: '🧾 ಒಳಸುರಿ ದಾಖಲೆ ಸೇರಿಸಿ (ಸ್ವಯಂ ಘೋಷಿತ)', date: 'ದಿನಾಂಕ', itype: 'ಒಳಸುರಿ ವಿಧ', product: 'ಉತ್ಪನ್ನ', quantity: 'ಪ್ರಮಾಣ', notes: 'ಟಿಪ್ಪಣಿ', bill: 'ಬಿಲ್ ಫೋಟೋ (ಐಚ್ಛಿಕ)', ppAdd: 'ಸೇರಿಸಿ',
 ppPreview: '👁 ಖರೀದಿದಾರರು ನೋಡುವುದು', advTitle: '🤖 ದೈನಂದಿನ ಸಲಹೆಗಾರ', schemes: '🏛 ಸರ್ಕಾರಿ ಯೋಜನೆಗಳು · ತ್ವರಿತ ಅರ್ಹತೆ', owner: 'ಸ್ವಂತ ಹೆಸರಿನಲ್ಲಿ ಜಮೀನು?', itax: 'ಆದಾಯ ತೆರಿಗೆ / ಸರ್ಕಾರಿ ನೌಕರಿ?',
 irr: 'ನೀರಾವರಿ', org: 'ಸಾವಯವ ಆಸಕ್ತಿ?', check: 'ಪರಿಶೀಲಿಸಿ', listen: '🔊 ಕೇಳಿ', sellCrop: 'ಈ ಬೆಳೆಗೆ ಉತ್ತಮ ಮಂಡಿ →',
};
const EN = {};
document.querySelectorAll('[data-i]').forEach(e => EN[e.dataset.i] = e.innerHTML);
Object.assign(EN, { listen: '🔊 Listen', sellCrop: 'Best mandi for this crop →' });
const t = k => (st.lang === 'kn' ? KN[k] : EN[k]) || EN[k] || k;
function setLang(l) {
 st.lang = l; $('l-en').classList.toggle('on', l === 'en'); $('l-kn').classList.toggle('on', l === 'kn');
 document.querySelectorAll('[data-i]').forEach(e => { const v = l === 'kn' ? KN[e.dataset.i] : EN[e.dataset.i]; if (v) e.innerHTML = v; });
 if (st.data.summary) { renderScore(st.data.summary); renderCard(st.data.summary); renderAdvisor(st.data.summary); }
}

// ------------------------------------------------------------- tabs, map, location
function tab(n) {
 st.tab = n;
 ['field', 'market', 'passport', 'advisor'].forEach(x => { $('v-' + x).classList.toggle('hidden', x !== n); $('t-' + x).classList.toggle('on', x === n); });
 if (n === 'field' && map) setTimeout(() => map.invalidateSize(), 50);
 if (n === 'passport') initPassport();
 if (n === 'advisor' && st.data.summary) renderAdvisor(st.data.summary);
 if (n === 'advisor' && !$('s-out').innerHTML) runSchemes();
 if (n === 'market' && !st.data.market && !st.mLoading) runMarket();
}
const map = L.map('map', { zoomControl: true }).setView([12.5, 76.85], 14);
L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 19, attribution: 'Esri World Imagery' }).addTo(map);
let marker = null, circle = null;
function place() {
 if (marker) { map.removeLayer(marker); map.removeLayer(circle); }
 marker = L.marker([st.lat, st.lon]).addTo(map);
 circle = L.circle([st.lat, st.lon], { radius: st.rad, color: '#facc15', weight: 2, fillOpacity: .1 }).addTo(map);
 map.setView([st.lat, st.lon], 15);
 $('coordtxt').textContent = `${st.lat.toFixed(5)}, ${st.lon.toFixed(5)} · ${st.rad} m buffer (${(Math.PI * st.rad * st.rad / 4046.86).toFixed(2)} acres)`;
}
map.on('click', e => { $('q').value = `${e.latlng.lat.toFixed(5)}, ${e.latlng.lng.toFixed(5)}`; go(); });
function preset(la, lo) { $('q').value = `${la}, ${lo}`; go(); }
function localParse(s) {
 const P = [/@(-?\d+\.\d+),(-?\d+\.\d+)/, /!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)/, /[?&](?:q|ll|query|destination|center)=(-?\d+\.\d+)(?:,|%2C)\s*(-?\d+\.\d+)/, /^\s*(-?\d{1,2}(?:\.\d+)?)\s*[, ]\s*(-?\d{1,3}(?:\.\d+)?)\s*$/];
 for (const p of P) { const m = s.match(p); if (m) return [+m[1], +m[2]]; } return null;
}
async function resolveQ() {
 const s = $('q').value.trim(); let c = localParse(s);
 if (!c) { const r = await fetch('/resolve?q=' + encodeURIComponent(s)); if (!r.ok) throw new Error((await r.json()).detail || 'Could not read location'); const j = await r.json(); c = [j.lat, j.lon]; }
 if (Math.abs(c[0]) > 90 || Math.abs(c[1]) > 180) throw new Error('Coordinates out of range');
 st.lat = c[0]; st.lon = c[1]; st.rad = +$('rad').value || 100;
}

// ------------------------------------------------------------- progressive loader
const SECTIONS = ['c-score', 'c-card', 'c-wx', 'c-live', 'c-idx', 'c-crop', 'c-irr', 'c-spray', 'c-fc', 'c-soil', 'c-clim', 'c-lc', 'c-rev'];
function skel(id, n = 3) { const b = $(id).querySelector('.body'); b.innerHTML = Array.from({ length: n }, (_, i) => `<div class="sk" style="height:${i ? 14 : 34}px;width:${90 - i * 12}%"></div>`).join(''); }
function timing(id, secs, meta) { const h = $(id).querySelector('h3'); let s = h.querySelector('.t'); if (!s) { s = document.createElement('span'); s.className = 't'; h.appendChild(s); } s.textContent = `${secs.toFixed(1)} s${meta && meta.cached ? ' · cached' : ''}`; }
async function J(url) { const t0 = performance.now(); const r = await fetch(url); const d = await r.json(); d._client = (performance.now() - t0) / 1000; return d; }
let runId = 0, chart = null, mchart = null;
async function go() {
 try { await resolveQ(); } catch (e) { $('status').textContent = '⚠ ' + e.message; return; }
 const my = ++runId; st.data = {}; place();
 SECTIONS.forEach(id => skel(id, id === 'c-live' ? 6 : 3));
 const q = `lat=${st.lat}&lon=${st.lon}&radius=${st.rad}`, T0 = performance.now(); let first = null; const done = {};
 $('go').disabled = true; $('status').innerHTML = `⏳ Loading live data for <b>${st.lat.toFixed(4)}, ${st.lon.toFixed(4)}</b>…`;
 const mark = (k) => { const s = (performance.now() - T0) / 1000; done[k] = s; if (first == null) first = s; upd(); };
 const upd = () => { const n = Object.keys(done).length; $('status').innerHTML = `${n < 7 ? '⏳' : '✅'} First data in <b>${first.toFixed(1)} s</b> · ${n}/7 sections loaded${n === 7 ? ` · full dashboard in <b>${Math.max(...Object.values(done)).toFixed(1)} s</b>` : ''} <span class="mut">(${Object.entries(done).map(([k, v]) => k + ' ' + v.toFixed(1) + 's').join(' · ')})</span>`; };
 const guard = fn => d => { if (my === runId) fn(d); };
 const pW = J('/api/weather?' + q).then(guard(d => { st.data.wx = d; renderWx(d); timing('c-wx', d._client, d._meta); mark('weather'); }));
 const pL = J('/api/sat/latest?' + q).then(guard(d => { st.data.latest = d; renderLatest(d); ['c-live', 'c-idx', 'c-lc'].forEach(i => timing(i, d._client, d._meta)); mark('satellite'); }));
 J('/api/sat/series?' + q).then(guard(d => { st.data.series = d; renderSeries(d); timing('c-ndvi', d._client, d._meta); timing('c-crop', d._client, d._meta); mark('ndvi-series'); }));
 J('/api/climate?' + q).then(guard(d => { renderClimate(d); timing('c-clim', d._client, d._meta); mark('climate'); }));
 J('/api/soil?' + q).then(guard(d => { st.data.soil = d; renderSoil(d); timing('c-soil', d._client, d._meta); mark('soil'); }));
 J('/api/revisit?' + q).then(guard(d => { renderRevisit(d); timing('c-rev', d._client); mark('revisit'); }));
 Promise.all([pW, pL]).then(() => J(`/api/summary?${q}&crop=${$('crop').value}`)).then(guard(d => {
  st.data.summary = d; renderScore(d); renderCard(d); renderIrr(d); renderSpray(d, 'c-spray'); renderAdvisor(d);
  ['c-score', 'c-card', 'c-irr', 'c-spray'].forEach(i => timing(i, (performance.now() - T0) / 1000)); mark('advisor');
  if (st.data.wx) renderForecast(st.data.wx, d);
 })).catch(e => { $('status').textContent = 'Error: ' + e.message; });
 Promise.allSettled([pW, pL]).then(() => { $('go').disabled = false; });
 if (st.tab === 'market') runMarket();
}

// ------------------------------------------------------------- renderers: field
const B = id => $(id).querySelector('.body');
function ring(score, grade) {
 const c = score >= 80 ? '#16a34a' : score >= 65 ? '#65a30d' : score >= 50 ? '#d97706' : '#dc2626', R = 46, L = 2 * Math.PI * R;
 return `<svg width="120" height="120" viewBox="0 0 120 120"><circle cx="60" cy="60" r="${R}" fill="none" stroke="#eef2f0" stroke-width="12"/>
 <circle cx="60" cy="60" r="${R}" fill="none" stroke="${c}" stroke-width="12" stroke-linecap="round" stroke-dasharray="${L * score / 100} ${L}" transform="rotate(-90 60 60)"/>
 <text x="60" y="62" text-anchor="middle" font-size="32" font-weight="800" fill="#0f172a">${score}</text><text x="60" y="82" text-anchor="middle" font-size="11" fill="#64748b">${grade}</text></svg>`;
}
function renderScore(d) {
 const s = d.score; if (!s || s.score == null) { B('c-score').innerHTML = '<div class="mut">Not enough data</div>'; return; }
 const kn = st.lang === 'kn';
 B('c-score').innerHTML = `<div class="ring">${ring(s.score, kn ? s.grade_kn : s.grade)}<div class="parts">${s.parts.map(p => `<div class="prow"><span>${kn ? p.kn : p.name}</span><b>${p.points}/${p.max}</b><div class="pbar" style="grid-column:span 2"><i style="width:${100 * p.points / p.max}%;background:${p.points / p.max >= .7 ? '#16a34a' : p.points / p.max >= .45 ? '#d97706' : '#dc2626'}"></i></div></div>`).join('')}</div></div>
 <div style="font-size:13px;margin-top:8px">${kn ? s.explanation_kn : s.explanation}</div><div class="disc">${s.method}</div>`;
}
function speak(text, lang) {
 if (!('speechSynthesis' in window)) { alert('Text-to-speech not supported in this browser'); return; }
 speechSynthesis.cancel(); const u = new SpeechSynthesisUtterance(text); const vs = speechSynthesis.getVoices();
 let v = vs.find(x => x.lang === (lang === 'kn' ? 'kn-IN' : 'en-IN')) || (lang === 'kn' ? null : vs.find(x => x.lang.startsWith('en')));
 if (lang === 'kn' && !v) { v = vs.find(x => x.lang === 'en-IN'); u.text = st.data.summary ? st.data.summary.card.headline_en + ' ' + st.data.summary.card.items.map(i => i.en).join(' ') : text; $('status').innerHTML += ' · <span class="mut">No Kannada voice on this device, reading English (en-IN).</span>'; }
 if (v) { u.voice = v; u.lang = v.lang; } else u.lang = lang === 'kn' ? 'kn-IN' : 'en-IN'; u.rate = .95; speechSynthesis.speak(u);
}
function cardText(c, lang) { return (lang === 'kn' ? c.headline_kn : c.headline_en) + ' ' + c.items.map(i => lang === 'kn' ? i.kn : i.en).join(' '); }
function cardHTML(c, both) {
 const kn = st.lang === 'kn';
 return `<div style="font-weight:700;margin-bottom:4px">${kn ? c.headline_kn : c.headline_en}</div>` + c.items.map(i => `<div class="act"><div class="ic">${i.icon}</div><div>${kn ? i.kn : i.en}${both ? `<div class="kn">${kn ? i.en : i.kn}</div>` : ''}</div></div>`).join('');
}
function renderCard(d) {
 const c = d.card;
 B('c-card').innerHTML = cardHTML({ ...c, items: c.items.slice(0, 4) }, false) +
  `<div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap"><button class="listen" onclick="speak(cardText(st.data.summary.card,'kn'),'kn')">🔊 ಕನ್ನಡ</button><button class="listen" onclick="speak(cardText(st.data.summary.card,'en'),'en')">🔊 English</button><button class="btn sec sm" onclick="tab('advisor')">${st.lang === 'kn' ? 'ಪೂರ್ಣ ಸಲಹೆ →' : 'Full advisor →'}</button></div>`;
}
function renderWx(d) {
 const c = d.current;
 B('c-wx').innerHTML = `<div class="big">${f(c.temperature_2m, 1)}°C</div><div class="mut" style="margin-bottom:8px">${c.weather} · feels ${f(c.apparent_temperature, 0)}°C</div>
 <div class="kv"><span>💧 Humidity</span><b>${c.relative_humidity_2m}%</b><span>🌬 Wind</span><b>${c.wind_speed_10m} km/h</b><span>🌧 Rain now</span><b>${c.rain} mm</b><span>☁ Cloud</span><b>${c.cloud_cover}%</b>
 <span>🌱 Soil 0–7 cm</span><b>${f(d.soil.moisture_0_7cm_m3m3, 2)} m³/m³</b></div><div class="disc">Open-Meteo · ${c.time.replace('T', ' ')} local</div>`;
 renderForecast(d, st.data.summary);
}
function renderForecast(w, s) {
 const fc = w.daily.filter(x => !x.past), al = w.alerts || [];
 B('c-fc').innerHTML = `<table><tr><th>Date</th><th>Sky</th><th>Max/Min</th><th>Rain (prob)</th><th>RH</th><th>ET0</th><th>Wind</th></tr>
 ${fc.map(x => `<tr><td>${x.date.slice(8)} ${MN[+x.date.slice(5, 7) - 1]}</td><td>${x.weather}</td><td><b>${f(x.tmax, 0)}°</b> / ${f(x.tmin, 0)}°</td><td>${x.rain_mm} mm (${x.rain_prob ?? '–'}%)</td><td>${x.rh_min}–${x.rh_max}%</td><td>${x.et0_mm}</td><td>${x.wind_max_kmh}</td></tr>`).join('')}</table>
 ${al.length ? al.map(a => `<div class="alert ${a.level}"><b>${a.date} · ${a.type}</b> ${a.msg}</div>`).join('') : '<div style="margin-top:8px"><span class="pill">✓ No heat, heavy-rain, frost, wind or fungal-weather alerts this week</span></div>'}
 <div class="disc">Open-Meteo forecast. Alert rules: heat >38 °C, rain >50 mm/day, frost <4 °C, wind >40 km/h, fungal weather (RH ≥90% & min ≥60% at 15–32 °C).</div>`;
}
function renderLatest(d) {
 const th = d.thumbnails, sm = (th && th.scene) || {}, ls = d.latest_scene || {}, I = ls.indices || {};
 if (!th || th.error) { B('c-live').innerHTML = `<div class="mut">No cloud-free Sentinel-2 image in the last months (${th && th.error || 'cloudy'}).</div>`; }
 else {
  const cap = k => `<div class="cap"><b>${k}</b> · ${sm.datetime_ist} · <b>${sm.satellite}</b> · ${sm.days_ago} day${sm.days_ago == 1 ? '' : 's'} ago · cloud ${sm.tile_cloud_pct}% · field ${Math.round(sm.field_clear_fraction * 100)}% clear</div>`;
  B('c-live').innerHTML = `<div class="live"><figure style="margin:0"><img src="${th.true_color}" alt="true colour">${cap('True colour (B4·B3·B2)')}</figure><figure style="margin:0"><img src="${th.ndvi}" alt="NDVI">${cap('NDVI crop-health map')}</figure></div>
  <div class="strip">${(d.recent_clear_scenes || []).map(g => `<figure><a href="${g.scene_preview_url}" target="_blank"><img src="${g.true_color}" alt=""></a><figcaption>${g.date.slice(8)} ${MN[+g.date.slice(5, 7) - 1]} · ${g.satellite_short}</figcaption></figure>`).join('')}</div>
  <div class="disc">Sentinel-2 L2A, fetched live from Microsoft Planetary Computer. Scene <code>${sm.item_id}</code> · <a href="${sm.stac_item_url}" target="_blank">STAC item</a> · <a href="${sm.scene_preview_url}" target="_blank">full scene</a> · <a href="${sm.explorer_url}" target="_blank">Explorer</a>. The strip shows the last ${(d.recent_clear_scenes || []).length} cloud-free passes. White circle = your field.</div>`;
 }
 const row = (k, n) => `<span>${k} <span class="mut">${n}</span></span><b>${f(I[k] && I[k].mean)}</b>`;
 const z = ls.ndvi_zones || {}, zc = ['#dc2626', '#f59e0b', '#a3e635', '#16a34a'];
 B('c-idx').innerHTML = I.NDVI ? `<div class="big">${f(I.NDVI.mean)}</div><div class="mut">NDVI field mean · ${ls.date}</div>
 <div style="display:flex;height:10px;border-radius:5px;overflow:hidden;margin:8px 0">${Object.values(z).map((v, i) => `<div style="width:${v * 100}%;background:${zc[i]}"></div>`).join('')}</div>
 <div class="mut" style="margin-bottom:8px">${Object.entries(z).map(([k, v]) => `${k.split(' ')[0]} ${(v * 100).toFixed(0)}%`).join(' · ')}</div>
 <div class="kv">${row('NDRE', 'chlorophyll/N')}${row('NDMI', 'canopy water')}${row('NDWI', 'surface water')}</div>` : '<div class="mut">No clear scene</div>';
 const lc = d.worldcover || {};
 B('c-lc').innerHTML = `<div class="mid">${lc.point_class || '–'}</div><div class="kv" style="margin-top:6px">${Object.entries(lc.buffer_distribution || {}).map(([k, v]) => `<span>${k}</span><b>${(v * 100).toFixed(0)}%</b>`).join('')}</div><div class="disc">ESA WorldCover 10 m (2021) · share of field buffer</div>`;
}
const CROP2COM = { paddy: 'paddy', ragi: 'ragi', maize: 'maize', tomato: 'tomato', sugarcane: 'jaggery', coconut: 'coconut', arecanut: 'arecanut', cotton: 'cotton', groundnut: 'groundnut', onion: 'onion', potato: 'potato', tur: 'tur', banana: 'banana' };
function renderSeries(d) {
 const ce = d.crop_estimate || {};
 const guess = Object.keys(CROP2COM).find(k => (ce.candidates || '').toLowerCase().split(';')[0].includes(k) || (ce.label || '').toLowerCase().includes(k)) || 'paddy';
 B('c-crop').innerHTML = `<div class="mid">${ce.label || '–'}</div><div style="margin:4px 0"><span class="pill ${ce.confidence_level === 'low' ? 'warn' : ''}">${ce.confidence_level || ''} confidence ${f(ce.confidence)}</span></div>
 <div style="font-size:12.5px">${ce.reasoning || ''}</div>${ce.candidates ? `<div style="font-size:12.5px;margin-top:4px"><b>Likely:</b> ${ce.candidates}</div>` : ''}
 <button class="btn sm" style="margin-top:8px" onclick="sellCrop('${guess}')">💰 ${t('sellCrop')} (${guess})</button>
 <div class="disc">⚠ Heuristic estimate from the NDVI season pattern, not a trained classifier.</div>`;
 const m = d.ndvi_monthly, sc = d.ndvi_scenes, m0 = m[0].month, y0 = +m0.slice(0, 4), mo0 = +m0.slice(5, 7);
 const X = s => (+s.slice(0, 4) - y0) * 12 + (+s.slice(5, 7) - mo0) + (+s.slice(8, 10) - 1) / 30.5;
 if (chart) chart.destroy();
 chart = new Chart($('ch'), { data: { datasets: [
  { type: 'line', label: 'Monthly median NDVI', data: m.map(x => ({ x: X(x.month + '-15'), y: x.ndvi })), borderColor: '#15803d', backgroundColor: 'rgba(21,128,61,.12)', fill: true, spanGaps: true, tension: .35, pointRadius: 4 },
  { type: 'scatter', label: 'Cloud-free scenes', data: sc.map(x => ({ x: X(x.date), y: x.ndvi })), backgroundColor: 'rgba(245,158,11,.8)', pointRadius: 3 }] },
  options: { animation: false, maintainAspectRatio: true, scales: { x: { type: 'linear', min: 0, max: m.length, ticks: { stepSize: 1, callback: v => { const k = mo0 - 1 + v; return MN[((k % 12) + 12) % 12] + (k % 12 == 0 || v == 0 ? " '" + String(y0 + Math.floor(k / 12)).slice(2) : ''); } } }, y: { min: 0, max: 1, title: { display: true, text: 'NDVI' } } }, plugins: { legend: { position: 'bottom' } } } });
}
function sellCrop(c) { $('mcom').value = CROP2COM[c] || 'paddy'; $('mvar').innerHTML = '<option value="all">All varieties (median per mandi)</option>'; st.data.market = null; tab('market'); runMarket(); }
function renderIrr(d) {
 const ir = d.irrigation;
 B('c-irr').innerHTML = `<div><span class="pill ${ir.action === 'IRRIGATE' ? 'bad' : ir.action === 'WAIT' || ir.action === 'N/A' ? 'warn' : ''}" style="font-size:14px">${ir.action}</span></div>
 <div style="margin:8px 0;font-size:13.5px">${ir.advice}</div><div class="kv"><span>Crop coefficient Kc (from NDVI)</span><b>${ir.kc}</b><span>Last 7 d crop water use / rain</span><b>${ir.last7.etc_mm} / ${ir.last7.effective_rain_mm} mm</b><span>Next 3 d</span><b>${ir.next3.etc_mm} / ${ir.next3.rain_mm} mm</b><span>Root-zone depletion</span><b>${f(ir.root_zone_depletion * 100, 0)}%</b></div>
 <div class="disc">FAO-56 water balance (ETc = Kc × ET0 − effective rain). Model soil moisture (~10 km). Generic loam assumed.</div>`;
}
function renderSpray(d, id) {
 const s = d.spray, p = d.pests, lv = l => `<span class="pill ${l === 'high' ? 'bad' : l === 'medium' ? 'warn' : ''}">${l}</span>`;
 B(id).innerHTML = `<div style="font-weight:700;font-size:13px;margin-bottom:6px">${st.lang === 'kn' ? 'ಸಿಂಪಡಣೆಗೆ ಸುರಕ್ಷಿತ ಸಮಯ (48 ಗಂ)' : 'Safe spray windows (next 48 h)'}</div>
 <div class="win">${s.windows.length ? s.windows.map(w => `<span>✅ ${w.start.slice(8, 10)} ${MN[+w.start.slice(5, 7) - 1]} ${w.start.slice(11, 16)}–${w.end.slice(11, 16)} <span class="mut">wind ≤${f(w.max_wind, 0)} km/h</span></span>`).join('') : '<span style="background:#fef2f2;border-color:#fecaca">⛔ No safe window: ' + (s.constraints_seen.join(', ') || 'wind/rain') + '</span>'}</div>
 <div class="disc" style="margin-bottom:8px">${s.rules}</div>
 <div style="font-weight:700;font-size:13px;margin:6px 0">${st.lang === 'kn' ? 'ಕೀಟ / ರೋಗ ಅಪಾಯ' : 'Pest / disease risk'} · ${d.crop_label}</div>
 ${p.risks.map(r => `<div class="risk"><div><b>${r.risk}</b><div class="mut">${r.driver}</div><div style="font-size:12px">🌿 ${r.organic_action}</div></div><div>${lv(r.level)}</div></div>`).join('')}
 <div class="disc">${p.note}</div>`;
}
function renderSoil(d) {
 const w = st.data.wx, s = w ? w.soil : null, sg = d && d.properties;
 const r = (k, l, dp = '0-5cm') => sg && sg[k] ? `<span>${l}</span><b>${sg[k][dp] ?? '–'} ${sg[k].unit === '-' ? '' : sg[k].unit}</b>` : '';
 B('c-soil').innerHTML = `<div class="kv">${s ? `<span>Moisture 0–7 / 7–28 cm</span><b>${f(s.moisture_0_7cm_m3m3)} / ${f(s.moisture_7_28cm_m3m3)}</b><span>Soil temp 0–7 cm</span><b>${f(s.temperature_0_7cm_c, 1)}°C</b>` : ''}
 ${r('phh2o', 'pH')}${r('soc', 'Organic carbon')}${r('nitrogen', 'Total nitrogen')}${r('clay', 'Clay')}${r('sand', 'Sand')}${r('cec', 'CEC')}</div>
 <div class="disc">${sg ? 'Texture and chemistry: ISRIC SoilGrids 250 m model (0–5 cm), not a lab test.' : 'SoilGrids is slow or unavailable right now. Use your Soil Health Card values.'} Moisture: Open-Meteo model.</div>`;
}
function renderClimate(c) {
 B('c-clim').innerHTML = c.error ? `<div class="mut">${c.error}</div>` : `<div class="big">${c.total_rain_mm} mm</div><div class="mut" style="margin-bottom:8px">rain in ${c.days_with_data} days · ${c.rainy_days_gt2_5mm} rainy days</div>
 <div class="kv"><span>Mean max / min</span><b>${c.mean_tmax_c} / ${c.mean_tmin_c}°C</b><span>Extremes</span><b>${f(c.abs_max_c, 1)} / ${f(c.abs_min_c, 1)}°C</b><span>Humidity</span><b>${c.mean_rh_pct}%</b><span>Growing degree days</span><b>${c.growing_degree_days_base10}</b></div><div class="disc">${c.period} · ${c.source}</div>`;
}
function renderRevisit(r) {
 const s2 = r.sentinel2 || {}, ls = r.landsat || {}, s1 = r.sentinel1 || {}, d5 = a => Array.isArray(a) ? a.slice(0, 3).map(x => x.date.slice(5)).join(', ') : '–';
 B('c-rev').innerHTML = `<table><tr><th>Mission</th><th>Last passes</th><th>Next (est.)</th></tr>
 <tr><td>Sentinel-2 <span class="mut">10 m</span></td><td>${(s2.last_acquisitions || []).slice(0, 3).map(a => a.date.slice(5)).join(', ')}</td><td><b>${(s2.estimated_next || []).slice(0, 2).map(x => x.date.slice(5)).join(', ')}</b></td></tr>
 <tr><td>Landsat 8/9 <span class="mut">30 m</span></td><td>${d5(ls.last_acquisitions)}</td><td>${(ls.estimated_next || '–').slice(5)}</td></tr>
 <tr><td>Sentinel-1 SAR</td><td>${d5(s1.last_acquisitions)}</td><td>${(s1.estimated_next || '–').slice(5)}</td></tr>
 <tr><td>LISS-IV <span class="mut">5.8 m</span></td><td colspan="2" class="mut">5 d steerable / 24 d nadir · via Bhuvan/NRSC</td></tr></table>
 <div class="disc">Actual acquisition dates from STAC. Sentinel-2 observed gap: ${s2.observed_median_gap_days ?? '–'} days.</div>`;
}

// ------------------------------------------------------------- advisor tab
function renderAdvisor(d) {
 if (!d) return;
 const c = d.card;
 B('a-card').innerHTML = `<div style="display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap"><button class="listen" onclick="speak(cardText(st.data.summary.card,'kn'),'kn')">🔊 ಕನ್ನಡದಲ್ಲಿ ಕೇಳಿ</button><button class="listen" onclick="speak(cardText(st.data.summary.card,'en'),'en')">🔊 Listen in English</button><button class="btn sec sm" onclick="speechSynthesis.cancel()">⏹</button></div>` +
  cardHTML(c, true) + (d.llm && d.llm.text ? `<div class="card" style="background:#f8fafc;margin-top:10px"><b>${d.llm.engine}</b><div style="white-space:pre-wrap;font-size:13px">${d.llm.text}</div></div>` : '') +
  `<div class="disc">Engine: ${d.llm ? d.llm.engine : 'rule-based templates (set GROQ_API_KEY or GEMINI_API_KEY on the server for an optional LLM summary)'}. Based on: satellite scene ${d.scene_date}, Open-Meteo forecast ${d.weather_time}. ${c.kn_note}</div>`;
 $('a-engine').textContent = d.llm ? d.llm.engine : 'rule-based';
 renderSpray(d, 'a-risk');
}
async function runSchemes() {
 const irr = $('s-irr').value, q = new URLSearchParams({ land_acres: $('s-ac').value, owner: $('s-own').value, income_tax: $('s-tax').value, govt_employee: $('s-tax').value, irrigation: irr === 'offgrid' ? 'borewell' : irr, grid_pump: irr !== 'offgrid', organic_interest: $('s-org').value, crop: $('crop').value });
 const d = await J('/api/schemes?' + q);
 $('s-out').innerHTML = `<div class="sch">${d.schemes.map(s => `<div class="s ${s.status === 'likely' ? 'likely' : s.status === 'not eligible' ? 'notel' : ''}"><div style="display:flex;justify-content:space-between;gap:6px"><b>${s.name}</b><span class="pill ${s.status === 'likely' ? '' : s.status === 'not eligible' ? 'bad' : 'warn'}">${s.status}</span></div>
 <div class="mut">${s.kn}</div><div style="font-size:12.5px;margin:4px 0">${s.benefit}</div><div style="font-size:12px">${s.why}</div><a href="${s.url}" target="_blank" style="font-size:12px">Official site ↗</a></div>`).join('')}</div>
 <div class="disc">⚠ ${d.note} <a href="${d.fruits_url}" target="_blank">FRUITS portal ↗</a></div>`;
}

// ------------------------------------------------------------- passport tab
let ppInit = false;
async function initPassport(sel) {
 const d = await J('/api/farms');
 $('pfarm').innerHTML = d.farms.map(x => `<option value="${x.id}">${x.farmer} · ${x.village || ''} · ${x.crop}${x.demo ? ' (demo)' : ''}</option>`).join('');
 $('ptypes').innerHTML = d.input_types.map(x => `<option>${x}</option>`).join('');
 if (!document.querySelector('#logf [name=date]').value) document.querySelector('#logf [name=date]').value = new Date().toISOString().slice(0, 10);
 const id = sel || $('pfarm').value; if (id) { $('pfarm').value = id; loadPassport(id); }
}
async function loadPassport(id) {
 $('pcard').innerHTML = '<div class="sk" style="height:120px"></div>';
 const d = await J('/api/passport/' + id); st.data.passport = d; const o = d.organic, h = d.health;
 const url = location.origin + '/passport/' + id;
 $('pcard').innerHTML = `<div style="display:flex;gap:14px;align-items:center"><img src="${d.qr}" width="132" height="132" style="border:1px solid #e2e8f0;border-radius:10px">
 <div><div class="mid">${d.farm.farmer}</div><div class="mut">${d.farm.village} · ${d.farm.crop} · ${d.farm.area_acres || '–'} acres</div>
 <div style="margin:6px 0"><span class="pill">💯 Health ${h.score}/100</span> <span class="pill ${o.level === 'organic' ? '' : o.level === 'conventional' ? 'bad' : 'warn'}">🌿 Organic ${o.score}/100</span></div>
 <div class="mut">🛰 Satellite-verified ${d.satellite.scene ? d.satellite.scene.date : '–'} · 🧾 ${o.entries} self-declared entries</div>
 <div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap"><a class="btn sm" href="/passport/${id}" target="_blank">Open passport ↗</a><button class="btn sec sm" onclick="navigator.clipboard&&navigator.clipboard.writeText('${url}');this.textContent='Copied ✓'">Copy link</button></div></div></div>
 <div class="disc">QR encodes ${url}. Set PUBLIC_BASE_URL on the server when it is hosted publicly so phones can open it.</div>`;
 $('plogs').innerHTML = `<table><tr><th>Date</th><th>Type</th><th>Product</th><th>Qty</th><th>Bill</th></tr>${d.logs.map(l => `<tr><td>${l.date}</td><td>${l.input_type}</td><td>${l.product}${l.demo ? ' <span class="pill grey">DEMO</span>' : ''}</td><td>${l.quantity || ''}</td><td>${l.bill_file ? `<a href="/uploads/${l.bill_file}" target="_blank">📎</a>` : '–'}</td></tr>`).join('')}</table>`;
 $('pframe').src = '/passport/' + id;
}
async function createPassport() {
 const r = await fetch('/api/farms', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ farmer: $('pf-name').value || 'Farmer', village: $('pf-vil').value, crop: $('pf-crop').value, lat: st.lat, lon: st.lon, radius: st.rad, area_acres: +$('pf-ac').value }) });
 const j = await r.json(); $('pf-msg').textContent = r.ok ? `Created ✓ ${j.url}` : 'Error'; if (r.ok) initPassport(j.id);
}
async function addLog(e) {
 e.preventDefault(); const id = $('pfarm').value; if (!id) return;
 const r = await fetch(`/api/farms/${id}/logs`, { method: 'POST', body: new FormData($('logf')) });
 $('log-msg').textContent = r.ok ? 'Entry added ✓ (self-declared)' : 'Error: ' + (await r.text()); if (r.ok) { $('logf').reset(); loadPassport(id); }
}

// ------------------------------------------------------------- market tab
let mmap = null;
fetch('/commodities').then(r => r.json()).then(j => {
 $('mcom').innerHTML = j.commodities.map(c => `<option value="${c.key}">${c.label}${c.class === 'perishable' ? ' 🥬' : ''}</option>`).join('');
 $('mveh').innerHTML = j.vehicles.map(v => `<option value="${v.key}">${v.label} · ₹${v.rate_per_km}/km</option>`).join('');
 $('mcom').value = Q.get('commodity') || 'tomato'; $('mveh').value = 'tractor';
 $('mcom').onchange = () => { $('mvar').innerHTML = '<option value="all">All varieties (median per mandi)</option>'; };
});
async function runMarket() {
 if (!$('mcom').value) return setTimeout(runMarket, 300);
 st.mLoading = true; $('mgo').disabled = true; $('mstatus').textContent = 'Fetching Agmarknet prices, road distances…'; const t0 = performance.now();
 try {
  const r = await fetch(`/market?lat=${st.lat}&lon=${st.lon}&commodity=${$('mcom').value}&qty=${$('mqty').value}&vehicle=${$('mveh').value}&variety=${encodeURIComponent($('mvar').value)}`);
  if (!r.ok) throw new Error(await r.text()); const d = await r.json(); st.data.market = d; renderMarket(d);
  $('mstatus').textContent = `✅ Done in ${((performance.now() - t0) / 1000).toFixed(1)} s · farm ${st.lat.toFixed(4)}, ${st.lon.toFixed(4)}`;
 } catch (e) { $('mstatus').textContent = 'Error: ' + e.message; }
 $('mgo').disabled = false; st.mLoading = false;
}
function renderMarket(d) {
 const pi = d.price_info || {}, b = d.best, n = d.nearest, tr = d.trend || {}, h = tr.hint || {}, A = d.assumptions || {}, s = pi.status || 'unavailable';
 const lab = { live: 'LIVE DATA', cached: 'CACHED (today)', fallback: 'FALLBACK SNAPSHOT – not today', unavailable: 'NO DATA' }[s];
 const cur = d.variety_selected || 'all';
 $('mvar').innerHTML = '<option value="all">All varieties (median per mandi)</option>' + (d.varieties || []).map(v => `<option value="${v.variety}">${v.variety} · ${v.markets}</option>`).join(''); $('mvar').value = cur;
 if (!d.mandis || !d.mandis.length) { $('mout').innerHTML = `<div class="card" style="margin-top:14px">${d.error || 'No mandis found'}</div>`; return; }
 $('mout').innerHTML = `<div class="card" style="margin-top:14px;display:flex;gap:10px;align-items:center;flex-wrap:wrap"><span class="pill status-${s}">● ${lab}</span><b>Price date ${pi.data_date}</b><span>${pi.markets_reporting} Karnataka mandis reported ${d.commodity} · ₹/quintal</span><span class="mut" style="flex-basis:100%">Source: ${pi.source || '–'}${pi.note ? ' · ' + pi.note : ''}</span></div>
 <div class="hero4" style="margin-top:14px">
  <div class="card"><h3>Best mandi</h3><div class="mid">${b.market.replace(' APMC', '')}</div><div class="mut">${b.district} · ${b.road_km} km</div></div>
  <div class="card"><h3>Net price there</h3><div class="big">${inr(b.net_per_q)}</div><div class="mut">per quintal · modal ${inr(b.modal)}</div></div>
  <div class="card"><h3>You take home</h3><div class="big">${inr(b.net_total)}</div><div class="mut">${d.quantity_q} q · ${d.vehicle.label}</div></div>
  <div class="card"><h3>Extra vs nearest</h3><div class="big" style="color:${d.extra_gain_best_vs_nearest > 0 ? '#15803d' : '#334155'}">+${inr(d.extra_gain_best_vs_nearest)}</div><div class="mut">nearest: ${n.market.replace(' APMC', '')} ${n.road_km} km</div></div></div>
 <div class="grid" style="margin-top:14px"><div class="card c7"><h3>Mandis & road routes</h3><div id="mmap"></div><div class="disc">🔴 farm · 🟢 rank by net price · 🔵 nearest. ${A.distance_source}. Town-level mandi geocodes (OSM Nominatim).</div></div>
 <div class="card c5"><h3>Sell now or wait? <span class="pill warn">rule-based</span></h3><div class="mid">${h.action || '–'}</div><div style="font-size:13px;margin:6px 0">${h.why || ''}</div>
 <div class="kv"><span>Karnataka avg modal (all varieties)</span><b>${inr(d.state_avg_modal)}</b><span>7-day change</span><b>${tr.change_7d_pct == null ? 'n/a' : tr.change_7d_pct + '%'}</b><span>30-day change</span><b>${tr.change_30d_pct == null ? 'n/a' : tr.change_30d_pct + '%'}</b></div><canvas id="mch" height="140" style="margin-top:8px"></canvas><div class="disc">History: ${(tr.sources || []).join(' + ')}</div></div></div>
 <div class="card" style="margin-top:14px"><h3>Ranked mandis · ${d.quantity_q} q ${d.commodity}</h3><div style="overflow-x:auto"><table class="mt"><tr><th>#</th><th>Mandi</th><th>Varieties (modal)</th><th>Modal</th><th>Road</th><th>Transport/q</th><th>Fees/q</th><th>Spoilage/q</th><th>Net/q</th><th>Total</th><th>vs nearest</th></tr>
 ${d.mandis.map(m => `<tr class="${m.rank == 1 ? 'best' : m.is_nearest ? 'near' : ''}"><td><span class="num" style="background:${m.is_nearest ? '#2563eb' : '#15803d'}">${m.rank}</span></td><td>${m.market} <span class="mut">${m.district}</span></td><td style="font-size:11px">${(m.variety_prices || []).map(v => `${v.variety} ${inr(v.modal)}`).join('<br>')}</td><td>${inr(m.modal)}</td><td>${m.road_km} km</td><td>${inr(m.transport_per_q)}</td><td>${inr(m.charges_per_q)}</td><td>${m.spoilage_pct ? inr(m.spoilage_per_q) : '–'}</td><td><b>${inr(m.net_per_q)}</b></td><td>${inr(m.net_total)}</td><td style="color:${m.gain_vs_nearest_total > 0 ? '#15803d' : m.gain_vs_nearest_total < 0 ? '#b91c1c' : '#666'}">${m.gain_vs_nearest_total > 0 ? '+' : ''}${inr(m.gain_vs_nearest_total)}</td></tr>`).join('')}</table></div>
 <div class="disc">Net/q = modal × (1 − spoilage) − APMC fee ${A.market_fee_pct}% − commission ${A.commission_pct}% − hamali ₹${A.hamali_per_q} − transport. Assumptions in data/market_config.json (estimates). Prices vary by variety; pick yours above.</div></div>`;
 if (mmap) mmap.remove(); mmap = L.map('mmap'); L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18, attribution: '© OpenStreetMap' }).addTo(mmap);
 const ic = (x, c) => L.divIcon({ className: '', html: `<div class="mk-icon ${c}" style="width:24px;height:24px">${x}</div>`, iconSize: [24, 24], iconAnchor: [12, 12] });
 const pts = [[d.farm.lat, d.farm.lon]]; L.marker(pts[0], { icon: ic('F', 'farm'), zIndexOffset: 1000 }).addTo(mmap);
 [...d.mandis].reverse().forEach(m => { if (m.route) L.polyline(m.route, { color: m.rank == 1 ? '#16a34a' : m.is_nearest ? '#2563eb' : '#94a3b8', weight: m.rank == 1 ? 5 : 3, opacity: .85 }).addTo(mmap); L.marker([m.lat, m.lon], { icon: ic(m.rank, m.is_nearest ? 'near' : '') }).addTo(mmap).bindPopup(`<b>#${m.rank} ${m.market}</b><br>Net ${inr(m.net_per_q)}/q`); pts.push([m.lat, m.lon]); });
 mmap.fitBounds(pts, { padding: [25, 25] });
 const tp = (tr.points || []).slice(-60); if (mchart) mchart.destroy();
 mchart = new Chart($('mch'), { type: 'line', data: { labels: tp.map(p => p.date.slice(5)), datasets: [{ data: tp.map(p => p.modal), borderColor: '#b45309', pointRadius: 2, tension: .25 }] }, options: { animation: false, plugins: { legend: { display: false } }, scales: { x: { ticks: { maxTicksLimit: 8 } } } } });
}

// ------------------------------------------------------------- boot
const Q = new URLSearchParams(location.search);
if (Q.get('q')) $('q').value = Q.get('q'); if (Q.get('lat')) $('q').value = `${Q.get('lat')}, ${Q.get('lon')}`;
if (Q.get('rad')) $('rad').value = Q.get('rad'); if (Q.get('lang') === 'kn') setLang('kn');
if (Q.get('tab')) st.tab = Q.get('tab');
if (typeof speechSynthesis !== 'undefined') speechSynthesis.getVoices();
go().then(() => { if (st.tab !== 'field') tab(st.tab); });
