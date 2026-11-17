/* =========================================================
   API Champions · Frontend (HTML + CSS + JavaScript puro)
   Consume la API real. La dirección base llega desde el servidor
   (variable FRONTEND_API_BASE), no está escrita en el código.
   ========================================================= */

const API = (window.APP_CONFIG && window.APP_CONFIG.apiBase) || "/api";
const TOKEN_KEY = "champions_token";
const USER_KEY = "champions_user";
const $ = (sel) => document.querySelector(sel);

const state = {
  token: null,
  user: null,
  teams: [], // equipos activos (para listas desplegables)
  standings: [],
  matches: [],
  spots: 0,
  pendingAction: null, // acción a ejecutar después de iniciar sesión
};

/* ---------- Almacenamiento seguro (puede fallar en modo privado) ---------- */
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* sin almacenamiento */ } },
  del(k) { try { localStorage.removeItem(k); } catch { /* sin almacenamiento */ } },
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

const FLAGS = {
  "españa": "es", "inglaterra": "gb-eng", "alemania": "de", "italia": "it", "francia": "fr",
  "portugal": "pt", "países bajos": "nl", "holanda": "nl", "bélgica": "be", "escocia": "gb-sct",
  "turquía": "tr", "austria": "at", "suiza": "ch", "ucrania": "ua", "croacia": "hr",
  "serbia": "rs", "grecia": "gr", "dinamarca": "dk", "república checa": "cz", "chequia": "cz",
  "eslovaquia": "sk", "noruega": "no", "suecia": "se", "polonia": "pl", "colombia": "co",
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
  const light = c1.toLowerCase() === "#ffffff";
  const textStyle = light ? "color:#050a33;text-shadow:none;" : "";
  return `<span class="crest${big ? " lg-crest" : ""}" style="--c1:${c1};--c2:${c2};${textStyle}" aria-hidden="true">${esc(initials(name))}</span>`;
}

function flag(country) {
  const code = FLAGS[country.trim().toLowerCase()];
  return code ? `<img class="flag" src="https://flagcdn.com/w40/${code}.png" alt="" loading="lazy">` : "🌍";
}

// Escapa el texto que viene de la API antes de insertarlo en el HTML (evita XSS)
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const signed = (n) => (n > 0 ? `+${n}` : `${n}`);

/* ---------- Indicador de carga ---------- */
let loadingCount = 0;
function loading(on) {
  loadingCount = Math.max(0, loadingCount + (on ? 1 : -1));
  $("#loadingBar").classList.toggle("hidden", loadingCount === 0);
  document.body.setAttribute("aria-busy", loadingCount > 0 ? "true" : "false");
}

// Deshabilita un botón mientras se ejecuta una acción asíncrona
async function busy(btn, fn) {
  if (!btn) return fn();
  const label = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner" aria-hidden="true"></span> Procesando…`;
  try {
    return await fn();
  } finally {
    btn.disabled = false;
    btn.innerHTML = label;
  }
}

/* ---------- Peticiones a la API ---------- */
class ApiError extends Error {
  constructor(message, status, details) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

async function api(path, { method = "GET", body, auth = false } = {}) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth && state.token) headers.Authorization = `Bearer ${state.token}`;

  loading(true);
  let res;
  try {
    res = await fetch(API + path, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined });
  } catch {
    throw new ApiError("No se pudo conectar con la API. Revisa tu conexión e intenta de nuevo.", 0);
  } finally {
    loading(false);
  }

  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const message = (data && (data.error || data.msg)) || `Error ${res.status}`;
    const err = new ApiError(message, res.status, data && data.details);
    if (res.status === 401 && auth) sessionRejected(message);
    throw err;
  }
  return data || {};
}

function errorText(err) {
  const msgs = err.details ? Object.values(err.details).filter((v) => typeof v === "string") : [];
  if (msgs.length) return `${err.message}: ${msgs.join(" · ")}`;
  return err.message;
}

/* ---------- Sesión (UI01) ---------- */
function setSession(token, user) {
  state.token = token;
  state.user = user;
  if (token) {
    store.set(TOKEN_KEY, token);
    store.set(USER_KEY, JSON.stringify(user));
  } else {
    store.del(TOKEN_KEY);
    store.del(USER_KEY);
  }
  $("#loginBtn").classList.toggle("hidden", !!token);
  $("#userChip").classList.toggle("hidden", !token);
  if (user) {
    $("#userName").textContent = user.username;
    $("#userRole").textContent = user.role === "admin" ? "admin" : "solo lectura";
    $("#userRole").classList.toggle("viewer", user.role !== "admin");
  }
}

// La API rechazó el token: se cierra la sesión y se ofrece volver a entrar
function sessionRejected(message) {
  if (!state.token) return;
  setSession(null, null);
  toast(message, "err");
  $("#loginMsg").textContent = message;
  openModal("#loginModal");
}

function requireAuth(action) {
  if (!state.token) {
    state.pendingAction = action;
    $("#loginMsg").textContent = "Inicia sesión para continuar con esta acción.";
    openModal("#loginModal");
    return;
  }
  // Los permisos los decide el servidor: si el rol no alcanza, la API responde 403
  // y la interfaz muestra ese rechazo.
  return action();
}

$("#loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  $("#loginError").textContent = "";
  await busy(f.querySelector("[type=submit]"), async () => {
    try {
      const res = await api("/auth/login", {
        method: "POST",
        body: { username: f.username.value.trim(), password: f.password.value },
      });
      setSession(res.data.access_token, res.data.user);
      const next = state.pendingAction;
      closeModal("#loginModal");
      f.reset();
      toast(`Bienvenido, ${res.data.user.username}`, "ok");
      if (next) next();
    } catch (err) {
      $("#loginError").textContent = errorText(err);
    }
  });
});

$("#loginBtn").addEventListener("click", () => {
  $("#loginMsg").textContent = "Inicia sesión para crear, editar y desactivar equipos o registrar partidos.";
  openModal("#loginModal");
});
$("#logoutBtn").addEventListener("click", () => {
  setSession(null, null);
  toast("Sesión cerrada");
});

// Al cargar la página se comprueba con la API que el token guardado siga siendo válido
async function restoreSession() {
  const token = store.get(TOKEN_KEY);
  if (!token) return setSession(null, null);
  let user = null;
  try { user = JSON.parse(store.get(USER_KEY)); } catch { /* ignorado */ }
  state.token = token;
  try {
    const res = await api("/auth/me", { auth: true });
    setSession(token, res.data);
  } catch (err) {
    if (err.status !== 401) setSession(token, user); // sin conexión: se mantiene hasta comprobarla
  }
}

/* ---------- Carga de datos ---------- */
async function loadAll() {
  try {
    const [st, teams, matches] = await Promise.all([api("/standings"), api("/teams"), api("/matches")]);
    state.standings = st.data;
    state.spots = st.qualification_spots;
    state.teams = teams.data;
    state.matches = matches.data;
    renderStats(st.total_matches_played);
    renderStandings();
    renderSelects();
    renderMatches();
  } catch (err) {
    toast(errorText(err), "err");
    $("#standingsBody").innerHTML = `<tr><td colspan="11" class="empty">No se pudo cargar la clasificación. ${esc(err.message)}</td></tr>`;
  }
  loadTeamsGrid();
  loadScorers();
}

/* ---------- Estadísticas ---------- */
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
  animateNumber($("#statGoals"), state.matches.reduce((s, m) => s + m.home_goals + m.away_goals, 0));
  const leader = state.standings[0];
  $("#statLeader").textContent = leader && leader.pj > 0 ? leader.name : "—";
}

/* ---------- Clasificación ---------- */
const STATUS = {
  clasificado: ["b-ok", "✓", "Clasificado"],
  eliminado: ["b-out", "✕", "Eliminado"],
  en_disputa: ["b-mid", "…", "En disputa"],
};

function renderStandings() {
  const body = $("#standingsBody");
  $("#legendSpots").textContent = state.spots ? `1–${state.spots} · Zona de clasificación` : "Zona de clasificación";
  if (!state.standings.length) {
    body.innerHTML = `<tr><td colspan="11" class="empty">Aún no hay equipos activos.</td></tr>`;
    return;
  }
  body.innerHTML = state.standings
    .map((t, i) => {
      const dgClass = t.dg > 0 ? "dg-pos" : t.dg < 0 ? "dg-neg" : "";
      const [cls, icon, label] = STATUS[t.qualification_status] || ["", "", ""];
      return `<tr class="${t.zone === "clasifica" ? "z-r16" : "z-out"}" data-id="${t.id}" tabindex="0" style="animation-delay:${i * 40}ms" aria-label="${esc(t.name)}, posición ${t.position}, ${t.points} puntos">
        <td><span class="pos">${t.position}</span></td>
        <td class="c-team"><div class="team-cell">${crest(t.name)}
          <div><div class="name">${esc(t.name)}</div><div class="country">${flag(t.country)} ${esc(t.country)}</div></div></div></td>
        <td>${t.pj}</td><td>${t.pg}</td><td>${t.pe}</td><td>${t.pp}</td>
        <td class="hide-sm">${t.gf}</td><td class="hide-sm">${t.gc}</td>
        <td class="${dgClass}">${signed(t.dg)}</td>
        <td class="c-pts">${t.points}</td>
        <td class="hide-sm">${label ? `<span class="badge ${cls}" title="${label}">${icon}</span>` : ""}</td>
      </tr>`;
    })
    .join("");
}

$("#standingsBody").addEventListener("click", (e) => {
  const row = e.target.closest("tr[data-id]");
  if (row) showTeamDetail(Number(row.dataset.id));
});
$("#standingsBody").addEventListener("keydown", (e) => {
  const row = e.target.closest("tr[data-id]");
  if (row && (e.key === "Enter" || e.key === " ")) {
    e.preventDefault();
    showTeamDetail(Number(row.dataset.id));
  }
});

/* ---------- Equipos: listado y búsqueda (RF02 / UI02) ---------- */
function currentFilters() {
  return {
    name: $("#searchName").value.trim(),
    country: $("#searchCountry").value.trim(),
    inactive: $("#searchInactive").checked,
  };
}

async function loadTeamsGrid(highlightId) {
  const f = currentFilters();
  const qs = new URLSearchParams();
  if (f.name) qs.set("name", f.name);
  if (f.country) qs.set("country", f.country);
  if (f.inactive) qs.set("include_inactive", "true");
  const grid = $("#teamsGrid");
  try {
    const res = await api(`/teams${qs.toString() ? "?" + qs : ""}`);
    const filtering = f.name || f.country;
    $("#teamsInfo").textContent = filtering ? `${res.count} equipo(s) encontrado(s)` : "";
    if (!res.data.length) {
      grid.innerHTML = `<p class="empty">${esc(res.message || "No hay equipos. ¡Crea el primero!")}</p>`;
      return;
    }
    grid.innerHTML = res.data.map((t, i) => teamCard(t, i, highlightId)).join("");
  } catch (err) {
    grid.innerHTML = `<p class="empty">No se pudieron cargar los equipos. ${esc(errorText(err))}</p>`;
  }
}

function teamCard(t, i, highlightId) {
  const actions = t.active
    ? `<button class="btn btn-ghost" data-act="view" type="button">Ver</button>
       <button class="btn btn-ghost" data-act="edit" type="button">Editar</button>
       <button class="btn btn-ghost del" data-act="deactivate" type="button">Desactivar</button>`
    : `<button class="btn btn-ghost" data-act="view" type="button">Ver</button>
       <button class="btn btn-ghost" data-act="activate" type="button">Reactivar</button>`;
  return `<article class="team-card${t.id === highlightId ? " highlight" : ""}${t.active ? "" : " inactive"}" data-id="${t.id}" style="animation-delay:${i * 40}ms">
    <span class="tc-id">ID ${t.id}${t.active ? "" : " · DESACTIVADO"}</span>
    <div class="tc-top">${crest(t.name)}
      <div><h3 class="tc-name">${esc(t.name)}</h3><div class="tc-country">${flag(t.country)} ${esc(t.country)}</div></div>
    </div>
    <div class="tc-stats">
      <div><b>${t.points}</b><small>Pts</small></div>
      <div><b>${t.pj}</b><small>PJ</small></div>
      <div><b>${signed(t.dg)}</b><small>DG</small></div>
    </div>
    <div class="tc-actions">${actions}</div>
  </article>`;
}

$("#teamsGrid").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-act]");
  if (!btn) return;
  const id = Number(btn.closest(".team-card").dataset.id);
  const name = btn.closest(".team-card").querySelector(".tc-name").textContent;
  const act = btn.dataset.act;
  if (act === "view") showTeamDetail(id);
  if (act === "edit") requireAuth(() => openTeamForm(id));
  if (act === "deactivate") requireAuth(() => confirmDeactivate(id, name));
  if (act === "activate") {
    requireAuth(() =>
      busy(btn, async () => {
        try {
          const res = await api(`/teams/${id}/activate`, { method: "PATCH", auth: true });
          toast(res.message, "ok");
          loadAll();
        } catch (err) {
          toast(errorText(err), "err");
        }
      })
    );
  }
});

$("#searchForm").addEventListener("submit", (e) => {
  e.preventDefault();
  loadTeamsGrid();
});
$("#clearSearch").addEventListener("click", () => {
  $("#searchForm").reset();
  loadTeamsGrid();
});
$("#searchInactive").addEventListener("change", () => loadTeamsGrid());

// Ficha del equipo: GET /api/teams/<id>
async function showTeamDetail(id) {
  try {
    const { data: t } = await api(`/teams/${id}`);
    const row = state.standings.find((s) => s.id === t.id);
    const players = t.players.length
      ? `<ul class="mini-list">${t.players.map((p) => `<li><span>${esc(p.name)}</span><b>${p.goals} ⚽</b></li>`).join("")}</ul>`
      : `<p class="muted">Sin jugadores registrados.</p>`;
    $("#detailContent").innerHTML = `
      ${crest(t.name, true)}
      <h3>${esc(t.name)}</h3>
      <p class="muted">${flag(t.country)} ${esc(t.country)} · ID ${t.id}${row ? ` · Posición ${row.position}º` : ""}${t.active ? "" : " · <b>Desactivado</b>"}</p>
      <div class="detail-grid">
        <div class="pts"><b>${t.points}</b><small>PTS</small></div>
        <div><b>${t.pj}</b><small>PJ</small></div>
        <div><b>${t.pg}</b><small>G</small></div>
        <div><b>${t.pe}</b><small>E</small></div>
        <div><b>${t.pp}</b><small>P</small></div>
        <div><b>${t.gf}</b><small>GF</small></div>
        <div><b>${t.gc}</b><small>GC</small></div>
        <div><b>${signed(t.dg)}</b><small>DG</small></div>
      </div>
      <p class="form-title" style="margin:8px 0 0">Jugadores</p>
      ${players}`;
    openModal("#detailModal");
  } catch (err) {
    toast(errorText(err), "err");
  }
}

/* ---------- Crear / editar ---------- */
async function openTeamForm(id) {
  const f = $("#teamForm");
  f.reset();
  $("#teamError").textContent = "";
  let team = null;
  if (id) {
    try {
      team = (await api(`/teams/${id}`)).data;
    } catch (err) {
      return toast(errorText(err), "err");
    }
  }
  $("#teamTitle").textContent = team ? "Editar equipo" : "Nuevo equipo";
  f.id.value = team ? team.id : "";
  f.name.value = team ? team.name : "";
  f.country.value = team ? team.country : "";
  openModal("#teamModal");
}

$("#addTeamBtn").addEventListener("click", () => requireAuth(() => openTeamForm()));

$("#teamForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const body = { name: f.name.value.trim(), country: f.country.value.trim() };
  const id = f.id.value;
  $("#teamError").textContent = "";
  if (!body.name || !body.country) {
    $("#teamError").textContent = "Completa el nombre y el país.";
    return;
  }
  await busy(f.querySelector("[type=submit]"), async () => {
    try {
      const res = id
        ? await api(`/teams/${id}`, { method: "PUT", body, auth: true })
        : await api("/teams", { method: "POST", body, auth: true });
      toast(res.message, "ok");
      closeModal("#teamModal");
      await loadAll();
      loadTeamsGrid(res.data.id);
    } catch (err) {
      if (err.status === 401) closeModal("#teamModal");
      else $("#teamError").textContent = errorText(err);
    }
  });
});

/* ---------- Confirmaciones de acciones destructivas ---------- */
function confirmAction({ title, html, yes, onYes }) {
  $("#confirmTitle").textContent = title;
  $("#confirmText").innerHTML = html;
  const btn = $("#confirmYes");
  btn.textContent = yes;
  btn.onclick = () =>
    busy(btn, async () => {
      try {
        await onYes();
        closeModal("#confirmModal");
      } catch (err) {
        closeModal("#confirmModal");
        if (err.status !== 401) toast(errorText(err), "err");
      }
    });
  openModal("#confirmModal");
}

function confirmDeactivate(id, name) {
  confirmAction({
    title: "¿Desactivar equipo?",
    html: `<b>${esc(name)}</b> dejará de aparecer en la tabla y no podrá jugar más partidos. Sus resultados anteriores se conservan y podrás reactivarlo después.`,
    yes: "Desactivar",
    onYes: async () => {
      const res = await api(`/teams/${id}`, { method: "DELETE", auth: true });
      toast(res.message, "ok");
      loadAll();
    },
  });
}

/* ---------- Listas desplegables ---------- */
function fillSelect(sel, keep, fallbackIndex = 0) {
  const el = $(sel);
  const prev = el.value;
  el.innerHTML = state.teams.map((t) => `<option value="${t.id}">${esc(t.name)}</option>`).join("");
  if (state.teams.some((t) => String(t.id) === prev) && keep) el.value = prev;
  else if (state.teams[fallbackIndex]) el.value = state.teams[fallbackIndex].id;
}

function renderSelects() {
  const sorted = [...state.teams].sort((a, b) => a.name.localeCompare(b.name));
  state.teams = sorted;
  fillSelect("#homeTeam", true, 0);
  fillSelect("#awayTeam", true, 1);
  fillSelect("#calcTeam", true, 0);
  fillSelect("#playerTeam", true, 0);
  fillSelect("#koTeam1", true, 0);
  fillSelect("#koTeam2", true, 1);
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

/* ---------- Partidos ---------- */
function renderMatches() {
  const list = $("#matchList");
  if (!state.matches.length) {
    list.innerHTML = `<li class="empty">Todavía no se ha jugado ningún partido.</li>`;
    return;
  }
  list.innerHTML = state.matches
    .map((m, i) => {
      const h = m.home_goals, a = m.away_goals;
      return `<li class="match-item" style="animation-delay:${i * 30}ms">
        <span class="h ${h > a ? "win" : ""}">${esc(m.home_team)}</span>
        <span class="sc">${h} - ${a}</span>
        <span class="a ${a > h ? "win" : ""}">${esc(m.away_team)}</span>
        <button class="btn-icon" type="button" data-match="${m.id}" title="Anular partido" aria-label="Anular ${esc(m.home_team)} ${h} - ${a} ${esc(m.away_team)}">✕</button>
      </li>`;
    })
    .join("");
}

$("#matchList").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-match]");
  if (!btn) return;
  const m = state.matches.find((x) => x.id === Number(btn.dataset.match));
  requireAuth(() =>
    confirmAction({
      title: "¿Anular partido?",
      html: `Se eliminará <b>${esc(m.home_team)} ${m.score} ${esc(m.away_team)}</b> y la tabla se recalculará.`,
      yes: "Anular",
      onYes: async () => {
        const res = await api(`/matches/${m.id}`, { method: "DELETE", auth: true });
        toast(res.message, "ok");
        loadAll();
      },
    })
  );
});

$("#matchForm").addEventListener("submit", (e) => {
  e.preventDefault();
  $("#matchError").textContent = "";
  const body = {
    home_team_id: Number($("#homeTeam").value),
    away_team_id: Number($("#awayTeam").value),
    home_goals: Number($("#homeGoals").value),
    away_goals: Number($("#awayGoals").value),
  };
  if (body.home_team_id === body.away_team_id) {
    $("#matchError").textContent = "Un equipo no puede jugar contra sí mismo.";
    return;
  }
  if (![body.home_goals, body.away_goals].every((g) => Number.isInteger(g) && g >= 0 && g <= 99)) {
    $("#matchError").textContent = "Los goles deben ser números enteros entre 0 y 99.";
    return;
  }
  requireAuth(() =>
    busy(e.target.querySelector("[type=submit]"), async () => {
      try {
        const res = await api("/matches", { method: "POST", body, auth: true });
        const m = res.data.match;
        toast(`${m.home_team} ${m.score} ${m.away_team}`, "ok");
        $("#homeGoals").value = 0;
        $("#awayGoals").value = 0;
        showEffects(res.data.effects);
        loadAll();
      } catch (err) {
        if (err.status !== 401) $("#matchError").textContent = errorText(err);
      }
    })
  );
});

function showEffects(effects) {
  const box = $("#matchEffects");
  box.innerHTML = `<p class="form-title">Efecto en la tabla</p>` +
    effects
      .map((ef) => {
        const diff = ef.position_before - ef.position_after;
        const arrow = diff > 0 ? `<span class="up">▲ ${diff}</span>` : diff < 0 ? `<span class="down">▼ ${-diff}</span>` : `<span>＝</span>`;
        return `<div class="effect-row"><span>${esc(ef.team)}</span><span>${ef.position_before}º → <b>${ef.position_after}º</b> ${arrow}</span><b>${ef.points} pts</b></div>`;
      })
      .join("");
  box.classList.remove("hidden");
}

/* ---------- Funciones especiales: pestañas ---------- */
const tabs = [...document.querySelectorAll(".tab")];
function selectTab(tab) {
  tabs.forEach((t) => {
    const on = t === tab;
    t.classList.toggle("active", on);
    t.setAttribute("aria-selected", on);
    t.tabIndex = on ? 0 : -1;
    $("#" + t.getAttribute("aria-controls")).classList.toggle("hidden", !on);
  });
}
tabs.forEach((t, i) => {
  t.addEventListener("click", () => selectTab(t));
  t.addEventListener("keydown", (e) => {
    const dir = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!dir) return;
    const next = tabs[(i + dir + tabs.length) % tabs.length];
    selectTab(next);
    next.focus();
  });
});

/* 1. Calculadora de clasificación */
$("#calcForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = $("#calcTeam").value;
  const spots = $("#calcSpots").value.trim();
  const out = $("#calcResult");
  await busy(e.target.querySelector("[type=submit]"), async () => {
    try {
      const { data: q } = await api(`/teams/${id}/qualification${spots ? `?spots=${encodeURIComponent(spots)}` : ""}`);
      const [cls, icon, label] = STATUS[q.status];
      out.innerHTML = `<div class="result-card ${cls}">
        <div class="rc-head"><span class="badge ${cls}">${icon}</span><div><h3>${esc(q.team)}</h3><p class="muted">${label} · posición ${q.position}º de la tabla</p></div></div>
        <div class="detail-grid">
          <div class="pts"><b>${q.current_points}</b><small>PTS</small></div>
          <div><b>${q.matches_played}</b><small>PJ</small></div>
          <div><b>${q.matches_remaining}</b><small>RESTANTES</small></div>
          <div><b>${q.max_possible_points}</b><small>MÁXIMO</small></div>
        </div>
        <p>${esc(q.message)}</p>
        <p class="muted">Cupos considerados: ${q.qualification_spots}${q.wins_needed_to_secure ? ` · Victorias para asegurar: <b>${q.wins_needed_to_secure}</b> (${q.points_needed_to_secure} pts)` : ""}</p>
      </div>`;
    } catch (err) {
      out.innerHTML = `<p class="form-error">${esc(errorText(err))}</p>`;
    }
  });
});

/* 2. Bota de Oro */
async function loadScorers() {
  const body = $("#scorersBody");
  try {
    const res = await api("/top-scorers?limit=20");
    if (!res.data.length) {
      body.innerHTML = `<tr><td colspan="5" class="empty">No hay goleadores registrados.</td></tr>`;
      return;
    }
    body.innerHTML = res.data
      .map(
        (p) => `<tr data-player="${p.id}">
          <td><span class="pos">${p.rank}</span></td>
          <td class="c-team"><div class="team-cell">${crest(p.team_name)}<div><div class="name">${esc(p.name)}</div><div class="country show-sm">${esc(p.team_name)}</div></div></div></td>
          <td class="c-team hide-sm">${esc(p.team_name)}</td>
          <td class="c-pts">${p.goals}</td>
          <td><div class="row-actions">
            <button class="btn-icon" type="button" data-goal="1" aria-label="Sumar un gol a ${esc(p.name)}">+1</button>
            <button class="btn-icon" type="button" data-goal="-1" aria-label="Restar un gol a ${esc(p.name)}">−1</button>
            <button class="btn-icon danger" type="button" data-del aria-label="Eliminar a ${esc(p.name)}">✕</button>
          </div></td>
        </tr>`
      )
      .join("");
  } catch (err) {
    body.innerHTML = `<tr><td colspan="5" class="empty">${esc(errorText(err))}</td></tr>`;
  }
}

$("#scorersBody").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  const row = btn.closest("tr[data-player]");
  const id = row.dataset.player;
  const name = row.querySelector(".name").textContent;
  if (btn.dataset.goal) {
    requireAuth(() =>
      busy(btn, async () => {
        try {
          const res = await api(`/players/${id}/goals`, { method: "PATCH", body: { goals: Number(btn.dataset.goal) }, auth: true });
          toast(res.message, "ok");
          loadScorers();
        } catch (err) {
          if (err.status !== 401) toast(errorText(err), "err");
        }
      })
    );
  }
  if ("del" in btn.dataset) {
    requireAuth(() =>
      confirmAction({
        title: "¿Eliminar jugador?",
        html: `Se eliminará a <b>${esc(name)}</b> de la Bota de Oro.`,
        yes: "Eliminar",
        onYes: async () => {
          const res = await api(`/players/${id}`, { method: "DELETE", auth: true });
          toast(res.message, "ok");
          loadScorers();
        },
      })
    );
  }
});

$("#playerForm").addEventListener("submit", (e) => {
  e.preventDefault();
  $("#playerError").textContent = "";
  const body = {
    name: $("#playerName").value.trim(),
    team_id: Number($("#playerTeam").value),
    goals: Number($("#playerGoals").value || 0),
  };
  if (!body.name) {
    $("#playerError").textContent = "Escribe el nombre del jugador.";
    return;
  }
  requireAuth(() =>
    busy(e.target.querySelector("[type=submit]"), async () => {
      try {
        const res = await api("/players", { method: "POST", body, auth: true });
        toast(res.message, "ok");
        $("#playerName").value = "";
        $("#playerGoals").value = 0;
        loadScorers();
      } catch (err) {
        if (err.status !== 401) $("#playerError").textContent = errorText(err);
      }
    })
  );
});

/* 3. Calendario */
$("#fixtureForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const out = $("#fixtureResult");
  const qs = new URLSearchParams({ double_round: $("#fxDouble").checked, only_pending: $("#fxPending").checked });
  await busy(e.target.querySelector("[type=submit]"), async () => {
    try {
      const res = await api(`/schedule?${qs}`);
      if (!res.data.length) {
        out.innerHTML = `<p class="empty">${esc(res.message)}</p>`;
        return;
      }
      out.innerHTML = `<p class="result-info">${esc(res.message)}</p><div class="rounds">` +
        res.data
          .map(
            (r) => `<div class="round"><p class="form-title">Jornada ${r.round}</p><ul>` +
              r.matches
                .map(
                  (m) => `<li class="fx ${m.status}"><span>${esc(m.home_team)}</span><small>vs</small><span>${esc(m.away_team)}</span>
                  ${m.status === "pendiente"
                    ? `<button class="btn-icon wide" type="button" data-home="${m.home_team_id}" data-away="${m.away_team_id}">Registrar</button>`
                    : `<em>Jugado</em>`}</li>`
                )
                .join("") +
              `</ul></div>`
          )
          .join("") +
        `</div>`;
    } catch (err) {
      out.innerHTML = `<p class="form-error">${esc(errorText(err))}</p>`;
    }
  });
});

// "Registrar" desde el calendario: prepara el formulario de partido
$("#fixtureResult").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-home]");
  if (!btn) return;
  $("#homeTeam").value = btn.dataset.home;
  $("#awayTeam").value = btn.dataset.away;
  updateCrests();
  $("#partidos").scrollIntoView({ behavior: "smooth" });
  setTimeout(() => $("#homeGoals").focus(), 400);
});

/* 4. Simulador de eliminatoria */
$("#koForm").addEventListener("submit", (e) => {
  e.preventDefault();
  $("#koError").textContent = "";
  const body = { team1_id: Number($("#koTeam1").value), team2_id: Number($("#koTeam2").value) };
  const seed = $("#koSeed").value.trim();
  if (seed !== "") body.seed = Number(seed);
  if (body.team1_id === body.team2_id) {
    $("#koError").textContent = "Elige dos equipos diferentes.";
    return;
  }
  requireAuth(
    () =>
      busy(e.target.querySelector("[type=submit]"), async () => {
        try {
          const { data: r } = await api("/knockout/simulate", { method: "POST", body, auth: true });
          const pen = r.penalties ? `<p class="muted">Global empatado · penales ${r.penalties.team1} - ${r.penalties.team2}</p>` : "";
          $("#koResult").innerHTML = `<div class="result-card b-ok">
            <div class="ko-legs">
              <div><small>IDA</small><p>${esc(r.leg_1.home)} <b>${r.leg_1.home_goals} - ${r.leg_1.away_goals}</b> ${esc(r.leg_1.away)}</p></div>
              <div><small>VUELTA</small><p>${esc(r.leg_2.home)} <b>${r.leg_2.home_goals} - ${r.leg_2.away_goals}</b> ${esc(r.leg_2.away)}</p></div>
            </div>
            <p class="ko-agg">Global: ${esc(r.team1.name)} <b>${r.aggregate.team1} - ${r.aggregate.team2}</b> ${esc(r.team2.name)}</p>
            ${pen}
            <div class="ko-winner">${crest(r.winner.name, true)}<div><small>CLASIFICA</small><h3>${esc(r.winner.name)}</h3></div></div>
            <p class="muted">Goles esperados por partido: ${esc(r.team1.name)} ${r.team1.expected_goals_per_match} · ${esc(r.team2.name)} ${r.team2.expected_goals_per_match}${r.seed != null ? ` · semilla ${r.seed}` : ""}</p>
          </div>`;
        } catch (err) {
          if (err.status !== 401) $("#koError").textContent = errorText(err);
        }
      })
  );
});

/* ---------- Modales y notificaciones ---------- */
let lastFocus = null;
function openModal(sel) {
  lastFocus = document.activeElement;
  $(sel).classList.remove("hidden");
  const first = $(sel).querySelector("input:not([type=hidden]), button:not(.modal-x)");
  if (first) setTimeout(() => first.focus(), 50);
}
function closeModal(sel) {
  $(sel).classList.add("hidden");
  if (sel === "#loginModal") state.pendingAction = null;
  if (lastFocus && document.contains(lastFocus)) lastFocus.focus();
}
document.addEventListener("click", (e) => {
  if (e.target.matches("[data-close]") || e.target.classList.contains("modal")) {
    closeModal("#" + e.target.closest(".modal").id);
  }
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") document.querySelectorAll(".modal:not(.hidden)").forEach((m) => closeModal("#" + m.id));
  // Mantiene el foco dentro del modal abierto
  if (e.key === "Tab") {
    const modal = document.querySelector(".modal:not(.hidden)");
    if (!modal) return;
    const items = [...modal.querySelectorAll("button, input:not([type=hidden]), select")].filter((x) => !x.disabled);
    if (!items.length) return;
    const first = items[0], last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
});

function toast(msg, type = "") {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.setAttribute("role", type === "err" ? "alert" : "status");
  el.textContent = msg;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), 4200);
}

/* ---------- Navegación activa ---------- */
const sections = ["clasificacion", "equipos", "partidos", "especiales"].map((id) => document.getElementById(id));
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

$("#refreshBtn").addEventListener("click", (e) => busy(e.currentTarget, loadAll));

restoreSession().then(loadAll);
