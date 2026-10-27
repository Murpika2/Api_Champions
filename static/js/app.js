/* =========================================================
   API Champions · Frontend
   Consume todos los endpoints de app.py:
     POST   /api/auth/login
     GET    /api/teams           GET /api/teams/<id>
     POST   /api/teams           PUT /api/teams/<id>   DELETE /api/teams/<id>
     GET    /api/matches         POST /api/matches
     GET    /api/standings
   ========================================================= */

const API = "/api";
const TOKEN_KEY = "champions_token";
const $ = (sel) => document.querySelector(sel);

const state = {
  token: localStorage.getItem(TOKEN_KEY),
  teams: [],
  standings: [],
  matches: [],
  pendingAction: null, // acción a ejecutar tras iniciar sesión
};

/* ---------- Escudos y banderas ---------- */
const CLUB_COLORS = {
  "real madrid": ["#ffffff", "#febe10"],
  "manchester city": ["#6cabdd", "#1c2c5b"],
  "fc barcelona": ["#a50044", "#004d98"],
  "barcelona": ["#a50044", "#004d98"],
  "bayern": ["#dc052d", "#0066b2"],
  "bayern munich": ["#dc052d", "#0066b2"],
  "bayern múnich": ["#dc052d", "#0066b2"],
  "liverpool": ["#c8102e", "#00b2a9"],
  "psg": ["#004170", "#da291c"],
  "paris saint-germain": ["#004170", "#da291c"],
  "juventus": ["#000000", "#ffffff"],
  "inter": ["#0068a8", "#000000"],
  "inter de milán": ["#0068a8", "#000000"],
  "ac milan": ["#fb090b", "#000000"],
  "milan": ["#fb090b", "#000000"],
  "atlético de madrid": ["#cb3524", "#272e61"],
  "atletico de madrid": ["#cb3524", "#272e61"],
  "borussia dortmund": ["#fde100", "#000000"],
  "dortmund": ["#fde100", "#000000"],
  "chelsea": ["#034694", "#ffffff"],
  "arsenal": ["#ef0107", "#ffffff"],
  "manchester united": ["#da291c", "#fbe122"],
  "benfica": ["#e83030", "#ffffff"],
  "porto": ["#00428c", "#ffffff"],
  "ajax": ["#d2122e", "#ffffff"],
  "napoli": ["#12a0d7", "#ffffff"],
  "tottenham": ["#132257", "#ffffff"],
};

// Códigos ISO para las banderas (imágenes de flagcdn.com, se ven igual en todos los sistemas)
const FLAGS = {
  "españa": "es", "inglaterra": "gb-eng", "alemania": "de", "italia": "it", "francia": "fr",
  "portugal": "pt", "países bajos": "nl", "holanda": "nl", "bélgica": "be", "escocia": "gb-sct",
  "turquía": "tr", "austria": "at", "suiza": "ch", "ucrania": "ua", "croacia": "hr",
  "serbia": "rs", "grecia": "gr", "dinamarca": "dk", "república checa": "cz", "chequia": "cz",
  "eslovaquia": "sk", "noruega": "no", "suecia": "se", "polonia": "pl", "rusia": "ru",
};

function hashHue(str) {
  let h = 0;
  for (const ch of str) h = (h * 31 + ch.charCodeAt(0)) % 360;
  return h;
}

function initials(name) {
  const words = name.replace(/[^\p{L}\p{N}\s]/gu, "").split(/\s+/).filter(Boolean);
  const skip = ["fc", "cf", "de", "del", "la", "club", "ac", "sc"];
  const main = words.filter((w) => !skip.includes(w.toLowerCase()));
  const src = main.length ? main : words;
  if (src.length === 1) return src[0].slice(0, 3).toUpperCase();
  return src.slice(0, 3).map((w) => w[0]).join("").toUpperCase();
}

function crest(name, big = false) {
  const key = name.trim().toLowerCase();
  let [c1, c2] = CLUB_COLORS[key] || [];
  if (!c1) {
    const h = hashHue(key);
    c1 = `hsl(${h} 70% 38%)`;
    c2 = `hsl(${(h + 40) % 360} 85% 55%)`;
  }
  const dark = c1.toLowerCase() === "#ffffff";
  const textStyle = dark ? "color:#050a33;text-shadow:none;" : "";
  return `<span class="crest${big ? " lg-crest" : ""}" style="--c1:${c1};--c2:${c2};${textStyle}">${esc(initials(name))}</span>`;
}

function flag(country) {
  const code = FLAGS[country.trim().toLowerCase()];
  return code ? `<img class="flag" src="https://flagcdn.com/w40/${code}.png" alt="" loading="lazy">` : "🌍";
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* ---------- Peticiones ---------- */
async function api(path, { method = "GET", body, auth = false } = {}) {
  const headers = {};
  if (body) headers["Content-Type"] = "application/json";
  if (auth && state.token) headers.Authorization = `Bearer ${state.token}`;
  const res = await fetch(API + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && auth) {
    // Token caducado o inválido (flask-jwt-extended devuelve {"msg": ...})
    setToken(null);
    throw Object.assign(new Error("Tu sesión expiró. Inicia sesión de nuevo."), { status: 401 });
  }
  if (!res.ok) throw Object.assign(new Error(data.error || data.msg || `Error ${res.status}`), { status: res.status });
  return data;
}

/* ---------- Autenticación ---------- */
function setToken(token) {
  state.token = token;
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
  $("#loginBtn").classList.toggle("hidden", !!token);
  $("#userChip").classList.toggle("hidden", !token);
}

// Ejecuta una acción protegida; si no hay sesión, abre el login primero
function requireAuth(action) {
  if (state.token) return action();
  state.pendingAction = action;
  openModal("#loginModal");
}

$("#loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  $("#loginError").textContent = "";
  try {
    const data = await api("/auth/login", {
      method: "POST",
      body: { username: f.username.value.trim(), password: f.password.value },
    });
    setToken(data.access_token);
    closeModal("#loginModal");
    f.reset();
    toast("Sesión iniciada. ¡Bienvenido!", "ok");
    const next = state.pendingAction;
    state.pendingAction = null;
    if (next) next();
  } catch (err) {
    $("#loginError").textContent = err.message;
  }
});

$("#loginBtn").addEventListener("click", () => openModal("#loginModal"));
$("#logoutBtn").addEventListener("click", () => {
  setToken(null);
  toast("Sesión cerrada");
});

/* ---------- Carga de datos ---------- */
async function loadAll() {
  try {
    const [standings, teams, matches] = await Promise.all([api("/standings"), api("/teams"), api("/matches")]);
    state.standings = standings.standings;
    state.teams = teams;
    state.matches = matches;
    renderStats(standings.total_matches_played);
    renderStandings();
    renderTeams();
    renderMatchSelects();
    renderMatches();
    if (typeof onDataLoaded === "function") onDataLoaded(); // features.js
  } catch (err) {
    toast("No se pudo conectar con la API: " + err.message, "err");
  }
}

/* ---------- Render: estadísticas ---------- */
function animateNumber(el, to) {
  const from = parseInt(el.textContent, 10) || 0;
  const start = performance.now();
  const step = (t) => {
    const p = Math.min(1, (t - start) / 600);
    el.textContent = Math.round(from + (to - from) * p);
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function renderStats(totalMatches) {
  animateNumber($("#statTeams"), state.teams.length);
  animateNumber($("#statMatches"), totalMatches);
  animateNumber($("#statGoals"), state.teams.reduce((s, t) => s + t.gf, 0));
  const leader = state.standings[0];
  $("#statLeader").textContent = leader && leader.pj > 0 ? leader.name : "—";
}

/* ---------- Render: clasificación ---------- */
function zone(pos) {
  if (pos <= 8) return "z-r16";
  if (pos <= 24) return "z-po";
  return "z-out";
}

function renderStandings() {
  const body = $("#standingsBody");
  if (!state.standings.length) {
    body.innerHTML = `<tr><td colspan="10" class="empty">Aún no hay equipos registrados.</td></tr>`;
    return;
  }
  body.innerHTML = state.standings
    .map((t, i) => {
      const dgClass = t.dg > 0 ? "dg-pos" : t.dg < 0 ? "dg-neg" : "";
      return `<tr class="${zone(i + 1)}" data-id="${t.id}" style="animation-delay:${i * 40}ms">
        <td><span class="pos">${i + 1}</span></td>
        <td class="c-team"><div class="team-cell">${crest(t.name)}
          <div><div class="name">${esc(t.name)}</div><div class="country">${flag(t.country)} ${esc(t.country)}</div></div></div></td>
        <td>${t.pj}</td><td>${t.pg}</td><td>${t.pe}</td><td>${t.pp}</td>
        <td class="hide-sm">${t.gf}</td><td class="hide-sm">${t.gc}</td>
        <td class="${dgClass}">${t.dg > 0 ? "+" : ""}${t.dg}</td>
        <td class="c-pts">${t.points}</td>
      </tr>`;
    })
    .join("");
}

$("#standingsBody").addEventListener("click", (e) => {
  const row = e.target.closest("tr[data-id]");
  if (row) showTeamDetail(Number(row.dataset.id));
});

/* ---------- Render: equipos ---------- */
function renderTeams(highlightId) {
  const grid = $("#teamsGrid");
  if (!state.teams.length) {
    grid.innerHTML = `<p class="empty">No hay equipos. ¡Crea el primero!</p>`;
    return;
  }
  grid.innerHTML = state.teams
    .map(
      (t, i) => `<article class="team-card${t.id === highlightId ? " highlight" : ""}" data-id="${t.id}" style="animation-delay:${i * 40}ms">
        <span class="tc-id">ID ${t.id}</span>
        <div class="tc-top">${crest(t.name)}
          <div><div class="tc-name">${esc(t.name)}</div><div class="tc-country">${flag(t.country)} ${esc(t.country)}</div></div>
        </div>
        <div class="tc-stats">
          <div><b>${t.points}</b><small>Pts</small></div>
          <div><b>${t.pj}</b><small>PJ</small></div>
          <div><b>${t.dg > 0 ? "+" : ""}${t.dg}</b><small>DG</small></div>
        </div>
        <div class="tc-actions">
          <button class="btn btn-ghost" data-act="view">Ver</button>
          <button class="btn btn-ghost" data-act="edit">Editar</button>
          <button class="btn btn-ghost del" data-act="delete">Eliminar</button>
        </div>
      </article>`
    )
    .join("");
}

$("#teamsGrid").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-act]");
  if (!btn) return;
  const id = Number(btn.closest(".team-card").dataset.id);
  const team = state.teams.find((t) => t.id === id);
  if (btn.dataset.act === "view") showTeamDetail(id);
  if (btn.dataset.act === "edit") requireAuth(() => openTeamForm(team));
  if (btn.dataset.act === "delete") requireAuth(() => confirmDelete(team));
});

// GET /api/teams/<id>
async function showTeamDetail(id) {
  try {
    const t = await api(`/teams/${id}`);
    const pos = state.standings.findIndex((s) => s.id === t.id) + 1;
    $("#detailContent").innerHTML = `
      ${crest(t.name, true)}
      <h3>${esc(t.name)}</h3>
      <p class="muted">${flag(t.country)} ${esc(t.country)} · ID ${t.id}${pos ? ` · Posición ${pos}º` : ""}</p>
      <div class="detail-grid">
        <div class="pts"><b>${t.points}</b><small>PTS</small></div>
        <div><b>${t.pj}</b><small>PJ</small></div>
        <div><b>${t.pg}</b><small>G</small></div>
        <div><b>${t.pe}</b><small>E</small></div>
        <div><b>${t.pp}</b><small>P</small></div>
        <div><b>${t.gf}</b><small>GF</small></div>
        <div><b>${t.gc}</b><small>GC</small></div>
        <div><b>${t.dg > 0 ? "+" : ""}${t.dg}</b><small>DG</small></div>
      </div>
      <div class="detail-qual" id="detailQual"></div>`;
    openModal("#detailModal");
    if (typeof renderQualification === "function") renderQualification(t.id, $("#detailQual")); // features.js
  } catch (err) {
    toast(err.message, "err");
  }
}

$("#searchForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = Number($("#searchId").value);
  if (!id) return;
  await showTeamDetail(id);
  renderTeams(id);
});

/* ---------- Crear / editar ---------- */
function openTeamForm(team) {
  const f = $("#teamForm");
  f.reset();
  $("#teamError").textContent = "";
  $("#teamTitle").textContent = team ? "Editar equipo" : "Nuevo equipo";
  f.id.value = team ? team.id : "";
  f.name.value = team ? team.name : "";
  f.country.value = team ? team.country : "";
  openModal("#teamModal");
  f.name.focus();
}

$("#addTeamBtn").addEventListener("click", () => requireAuth(() => openTeamForm()));

$("#teamForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const body = { name: f.name.value.trim(), country: f.country.value.trim() };
  const id = f.id.value;
  try {
    if (id) {
      await api(`/teams/${id}`, { method: "PUT", body, auth: true });
      toast(`${body.name} actualizado`, "ok");
    } else {
      await api("/teams", { method: "POST", body, auth: true });
      toast(`${body.name} se une a la competición`, "ok");
    }
    closeModal("#teamModal");
    loadAll();
  } catch (err) {
    if (err.status === 401) {
      closeModal("#teamModal");
      toast(err.message, "err");
      requireAuth(() => openTeamForm(id ? state.teams.find((t) => t.id === Number(id)) : undefined));
    } else {
      $("#teamError").textContent = err.message;
    }
  }
});

/* ---------- Eliminar ---------- */
function confirmDelete(team) {
  $("#confirmText").innerHTML = `Se eliminará <b>${esc(team.name)}</b> de la competición. Esta acción no se puede deshacer.`;
  $("#confirmYes").onclick = async () => {
    try {
      await api(`/teams/${team.id}`, { method: "DELETE", auth: true });
      toast(`${team.name} eliminado`, "ok");
      closeModal("#confirmModal");
      loadAll();
    } catch (err) {
      closeModal("#confirmModal");
      toast(err.message, "err");
    }
  };
  openModal("#confirmModal");
}

/* ---------- Partidos ---------- */
function renderMatchSelects() {
  const opts = state.teams.map((t) => `<option value="${t.id}">${esc(t.name)}</option>`).join("");
  for (const [sel, idx] of [["#homeTeam", 0], ["#awayTeam", 1]]) {
    const el = $(sel);
    const prev = el.value;
    el.innerHTML = opts;
    if (state.teams.some((t) => String(t.id) === prev)) el.value = prev;
    else if (state.teams[idx]) el.value = state.teams[idx].id;
  }
  updateCrests();
}

function updateCrests() {
  for (const [sel, slot] of [["#homeTeam", "#homeCrest"], ["#awayTeam", "#awayCrest"]]) {
    const t = state.teams.find((x) => String(x.id) === $(sel).value);
    $(slot).innerHTML = t ? crest(t.name, true) : "";
  }
}
$("#homeTeam").addEventListener("change", updateCrests);
$("#awayTeam").addEventListener("change", updateCrests);

function renderMatches() {
  const list = $("#matchList");
  if (!state.matches.length) {
    list.innerHTML = `<li class="empty">Todavía no se ha jugado ningún partido.</li>`;
    return;
  }
  list.innerHTML = state.matches
    .map((m, i) => {
      const [h, a] = m.score.split("-").map((n) => parseInt(n, 10));
      return `<li class="match-item" style="animation-delay:${i * 30}ms">
        ${m.round ? `<span class="round-tag">${esc(m.round)}</span>` : ""}
        <span class="h ${h > a ? "win" : ""}">${esc(m.home_team)}</span>
        <span class="sc">${h} - ${a}</span>
        <span class="a ${a > h ? "win" : ""}">${esc(m.away_team)}</span>
      </li>`;
    })
    .join("");
}

$("#matchForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const body = {
    home_team_id: Number($("#homeTeam").value),
    away_team_id: Number($("#awayTeam").value),
    home_goals: Number($("#homeGoals").value),
    away_goals: Number($("#awayGoals").value),
  };
  if (body.home_team_id === body.away_team_id) {
    toast("Un equipo no puede jugar contra sí mismo", "err");
    return;
  }
  requireAuth(async () => {
    try {
      const data = await api("/matches", { method: "POST", body, auth: true });
      toast(`${data.match.home} ${data.match.score} ${data.match.away}`, "ok");
      $("#homeGoals").value = 0;
      $("#awayGoals").value = 0;
      loadAll();
    } catch (err) {
      toast(err.message, "err");
    }
  });
});

/* ---------- Modales y toasts ---------- */
function openModal(sel) {
  $(sel).classList.remove("hidden");
  const first = $(sel).querySelector("input:not([type=hidden])");
  if (first) setTimeout(() => first.focus(), 50);
}
function closeModal(sel) {
  $(sel).classList.add("hidden");
}
document.addEventListener("click", (e) => {
  if (e.target.matches("[data-close]") || e.target.classList.contains("modal")) {
    const modal = e.target.closest(".modal");
    modal.classList.add("hidden");
    if (modal.id === "loginModal") state.pendingAction = null;
  }
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") document.querySelectorAll(".modal:not(.hidden)").forEach((m) => m.classList.add("hidden"));
});

function toast(msg, type = "") {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = msg;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), 3800);
}

/* ---------- Navegación activa ---------- */
const sections = ["clasificacion", "equipos", "partidos"].map((id) => document.getElementById(id));
const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((en) => {
      if (en.isIntersecting) {
        document.querySelectorAll(".nav-link").forEach((a) => a.classList.toggle("active", a.getAttribute("href") === `#${en.target.id}`));
      }
    });
  },
  { rootMargin: "-40% 0px -55% 0px" }
);
sections.forEach((s) => observer.observe(s));

$("#countries").innerHTML = Object.keys(FLAGS)
  .map((c) => `<option value="${c.charAt(0).toUpperCase() + c.slice(1)}">`)
  .join("");

$("#refreshBtn").addEventListener("click", loadAll);

setToken(state.token);
loadAll();
