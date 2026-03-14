const LICENSE_SERVER = 'https://kuroflow-license-server.onrender.com';

// ── AUTH ──
function doLogin() {
  const key = document.getElementById('login-key').value.trim().toUpperCase();
  if (!key.startsWith('KF-')) { showError('Key must start with KF-'); return; }
  const btn = document.getElementById('login-btn');
  btn.textContent = 'Validating...'; btn.disabled = true;

  fetch(`${LICENSE_SERVER}/validar`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ clave: key, cuenta_mt5: 'MEMBERS_PORTAL' }),
    signal: AbortSignal.timeout(15000)
  })
  .then(r => r.json())
  .then(d => {
    if (d.valido) {
      sessionStorage.setItem('kf_key', key);
      showDashboard(key);
    } else {
      showError(d.mensaje || 'Invalid or expired license key.');
      btn.textContent = 'Access Members Area →'; btn.disabled = false;
    }
  })
  .catch(err => {
    showError(err.name === 'TimeoutError'
      ? 'Server is waking up — please try again in 30 seconds.'
      : 'Connection error. Please try again.');
    btn.textContent = 'Access Members Area →'; btn.disabled = false;
  });
}

function showError(msg) {
  const el = document.getElementById('login-error');
  el.textContent = msg; el.style.display = 'block';
}

function showDashboard(key) {
  document.getElementById('login-screen').style.display = 'none';
  document.getElementById('main-nav').style.display = 'flex';
  document.getElementById('dashboard').style.display = 'block';
  document.getElementById('nav-key-display').textContent = key;
  loadAll();
}

function doLogout() { sessionStorage.clear(); location.reload(); }

document.getElementById('login-key').addEventListener('keydown', e => { if (e.key === 'Enter') doLogin(); });
const savedKey = sessionStorage.getItem('kf_key');
if (savedKey) showDashboard(savedKey);

// ── CLOCK ──
function updateClock() {
  const now = new Date();
  const utc = new Date(now.getTime() + now.getTimezoneOffset() * 60000);
  document.getElementById('utc-clock').textContent = utc.toTimeString().slice(0,8);
  document.getElementById('date-display').textContent = utc.toLocaleDateString('en-GB', { weekday:'short', day:'numeric', month:'short', year:'numeric' });
  const localEl = document.getElementById('local-clock');
  if (localEl) localEl.textContent = now.toTimeString().slice(0,8) + ' local';
}
setInterval(updateClock, 1000); updateClock();

// ── SESSIONS ──
const SESSIONS = [
  { name: 'Sydney',   open: 21, close: 6  },
  { name: 'Tokyo',    open: 0,  close: 9  },
  { name: 'London',   open: 8,  close: 17 },
  { name: 'New York', open: 13, close: 22 },
];
function renderSessions() {
  const now = new Date();
  const day  = now.getUTCDay();   // 0=Sun 6=Sat
  const h    = now.getUTCHours() + now.getUTCMinutes() / 60;
  const marketOpen = isForexMarketOpen();

  let anyActive = false;
  document.getElementById('sessions-list').innerHTML = SESSIONS.map(s => {
    const active = marketOpen && (s.open > s.close
      ? (h >= s.open || h < s.close)
      : (h >= s.open && h < s.close));
    if (active) anyActive = true;
    return `<div class="session-row ${active ? 'active' : ''}">
      <span class="session-name">${s.name}</span>
      <span class="session-hours">${String(s.open).padStart(2,'0')}:00–${String(s.close).padStart(2,'0')}:00 UTC</span>
      <span class="session-badge ${active ? 'on' : 'off'}">${active ? '● Open' : 'Closed'}</span>
    </div>`;
  }).join('');

  const st = document.getElementById('market-status-text');
  if (!marketOpen) {
    st.textContent = 'closed — weekend.';
    st.style.color = 'rgba(245,243,238,0.3)';
  } else if (anyActive) {
    st.textContent = 'open.';
    st.style.color = 'var(--safe-pale)';
  } else {
    st.textContent = 'closed.';
    st.style.color = 'rgba(245,243,238,0.4)';
  }
}
setInterval(renderSessions, 60000);

// ── MARKET HOURS CHECK ──
function isForexMarketOpen() {
  const now  = new Date();
  const day  = now.getUTCDay();
  const hour = now.getUTCHours() + now.getUTCMinutes() / 60;
  if (day === 6) return false;
  if (day === 0 && hour < 22) return false;
  if (day === 5 && hour >= 22) return false;
  return true;
}

// ── USDJPY PRICE — TwelveData ──
const TWELVE_KEY = '386cf5ddc6874140b9b39636e2651be4';
let lastKnownPrice = null;

async function fetchPrice() {
  const marketOpen = isForexMarketOpen();
  try {
    const r = await fetch(
      `https://api.twelvedata.com/price?symbol=USD/JPY&apikey=${TWELVE_KEY}`
    );
    const d = await r.json();
    if (!d.price) throw new Error('no price');
    const p = parseFloat(d.price);
    lastKnownPrice = p;

    document.getElementById('usdjpy-price').textContent = p.toFixed(3);
    document.getElementById('usdjpy-high').textContent  = (p * 1.003).toFixed(3);
    document.getElementById('usdjpy-low').textContent   = (p * 0.997).toFixed(3);

    if (marketOpen) {
      document.getElementById('usdjpy-updated').textContent = new Date().toUTCString().slice(17,22) + ' UTC';
      document.getElementById('usdjpy-change').innerHTML =
        '<span style="color:var(--safe-pale)">▲ ~15 min delay</span>';
    } else {
      document.getElementById('usdjpy-updated').textContent = 'Last close · Fri';
      document.getElementById('usdjpy-change').innerHTML =
        '<span style="color:rgba(245,243,238,0.35)">Market closed</span>';
    }
  } catch {
    if (lastKnownPrice) {
      document.getElementById('usdjpy-price').textContent = lastKnownPrice.toFixed(3);
    }
    document.getElementById('usdjpy-change').innerHTML =
      '<span style="color:rgba(245,243,238,0.3)">Price unavailable</span>';
  }
}

function schedulePriceFetch() {
  fetchPrice();
  const interval = isForexMarketOpen() ? 30000 : 300000;
  setTimeout(schedulePriceFetch, interval);
}

// ── CALENDAR ──
async function fetchCalendar() {
  const el = document.getElementById('calendar-list');
  try {
    const r = await fetch('https://nfs.faireconomy.media/ff_calendar_thisweek.json');
    const events = await r.json();
    const days = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const filtered = events.filter(e => ['USD','JPY'].includes(e.country) && e.impact === 'High').slice(0, 8);
    if (!filtered.length) throw new Error('none');
    el.innerHTML = filtered.map(e => {
      const dt = new Date(e.date);
      const dateStr = `${days[dt.getDay()]} ${dt.getDate()} ${months[dt.getMonth()]}`;
      const timeStr = dt.toUTCString().slice(17,22);
      return `<div class="cal-event">
        <span class="cal-time">${timeStr}<br><span style="font-size:0.58rem;opacity:0.6">${dateStr}</span></span>
        <span class="cal-dot high"></span>
        <span class="cal-name">${e.title}</span>
        <span class="cal-country">${e.country}</span>
      </div>`;
    }).join('');
  } catch {
    el.innerHTML = `<div class="cal-empty">No high-impact events found this week.<br><span style="font-size:0.6rem;opacity:0.6">Check <a href="https://www.forexfactory.com/calendar" target="_blank" style="color:var(--gold)">Forex Factory</a> for full calendar.</span></div>`;
  }
}

// ── WEEKLY ANALYSIS (via server — two sections) ──
async function fetchAnalysis() {
  const bodyUsdjpy   = document.getElementById('analysis-body-usdjpy');
  const bodyGlobal   = document.getElementById('analysis-body-global');
  const weekEl       = document.getElementById('analysis-week');
  const weekElGlobal = document.getElementById('analysis-week-global');
  if (!bodyUsdjpy || !bodyGlobal) return;

  const now = new Date();
  const wn  = getWeekNumber(now);
  const weekLabel = `Week ${wn} · ${now.getFullYear()}`;
  if (weekEl)       weekEl.textContent       = weekLabel;
  if (weekElGlobal) weekElGlobal.textContent = weekLabel;

  const cacheKey = `kf_analysis2_${wn}_${now.getFullYear()}`;
  const cached   = sessionStorage.getItem(cacheKey);
  if (cached) {
    try {
      const d = JSON.parse(cached);
      if (d.usdjpy) bodyUsdjpy.innerHTML = d.usdjpy;
      if (d.global)  bodyGlobal.innerHTML  = d.global;
      return;
    } catch(e) {}
  }

  const errMsg = `<p style="color:rgba(245,243,238,0.3);font-family:'DM Mono',monospace;font-size:0.75rem">Analysis temporarily unavailable. Check back shortly.</p>`;

  try {
    const r = await fetch(`${LICENSE_SERVER}/analysis`, { signal: AbortSignal.timeout(90000) });
    const d = await r.json();
    if (d.usdjpy && d.global) {
      bodyUsdjpy.innerHTML = d.usdjpy;
      bodyGlobal.innerHTML  = d.global;
      sessionStorage.setItem(cacheKey, JSON.stringify({ usdjpy: d.usdjpy, global: d.global }));
    } else {
      bodyUsdjpy.innerHTML = errMsg;
      bodyGlobal.innerHTML  = errMsg;
    }
  } catch {
    bodyUsdjpy.innerHTML = errMsg;
    bodyGlobal.innerHTML  = errMsg;
  }
}

function getWeekNumber(d) {
  const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  date.setUTCDate(date.getUTCDate() + 4 - (date.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  return Math.ceil((((date - yearStart) / 86400000) + 1) / 7);
}

function loadAll() {
  renderSessions();
  schedulePriceFetch();
  fetchCalendar();
  fetchAnalysis();
}

  // Login button
  var loginBtn = document.getElementById('login-btn');
  if (loginBtn) loginBtn.addEventListener('click', doLogin);

  // Support email
  var supportLink = document.getElementById('support-link');
  if (supportLink) {
    supportLink.addEventListener('click', function(e) {
      e.preventDefault();
      window.location.href = 'mailto:support@kuro-flow.com';
    });
  }


// Attach event listeners directly
document.addEventListener('DOMContentLoaded', function() {
  var loginBtn = document.getElementById('login-btn');
  if (loginBtn) loginBtn.addEventListener('click', doLogin);

  var loginKey = document.getElementById('login-key');
  if (loginKey) loginKey.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') doLogin();
  });

  var supportLink = document.getElementById('support-link');
  if (supportLink) {
    supportLink.addEventListener('click', function(e) {
      e.preventDefault();
      window.location.href = 'mailto:support@kuro-flow.com';
    });
  }
});
