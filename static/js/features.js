/* =========================================================
   API Champions · Nuevas funcionalidades
   Usa las utilidades globales de app.js (api, state, crest, flag, esc, toast...)
     POST /api/players                              → registrar jugador
     GET  /api/top-scorers  POST /api/top-scorers   → Bota de Oro / sumar goles
     POST /api/schedule/generate                    → calendario automático
     POST /api/knockout/simulate                    → eliminatoria ida y vuelta
     GET  /api/teams/<id>/qualification-calculator  → calculadora de clasificación
   ========================================================= */

state.scorers = [];
state.schedule = null;

// Se llama desde loadAll() de app.js cada vez que se recargan los datos
function onDataLoaded() {
  fillTeamSelect("#ko1", 0);
  fillTeamSelect("#ko2", 1);
  fillTeamSelect("#qualTeam", 0);
  fillTeamSelect("#playerTeam", 0);
  updateKoCrests();
  loadScorers();
}

function fillTeamSelect(sel, defaultIdx) {
  const el = $(sel);
  const prev = el.value;
  el.innerHTML = state.teams.map((t) => `<option value="${t.id}">${esc(t.name)}</option>`).join("");
  if (state.teams.some((t) => String(t.id) === prev)) el.value = prev;
  else if (state.teams[defaultIdx]) el.value = state.teams[defaultIdx].id;
}

const teamByName = (name) => state.teams.find((t) => t.name === name);

/* ---------- Bota de Oro ---------- */
async function loadScorers() {
  try {
    const data = await api("/top-scorers");
    state.scorers = data.top_scorers;
    renderScorers();
  } catch (err) {
    toast("No se pudo cargar la Bota de Oro: " + err.message, "err");
  }
}

function renderScorers(bumpId) {
  const podium = $("#podium");
  const list = $("#scorersList");
  if (!state.scorers.length) {
    podium.innerHTML = `<p class="empty">Aún no hay goleadores registrados.</p>`;
    list.innerHTML = "";
    return;
  }
  podium.innerHTML = state.scorers
    .slice(0, 3)
    .map(
      (p, i) => `<div class="podium-spot p${i + 1}" style="animation-delay:${i * 120}ms">
        <span class="boot">${["🥇", "🥈", "🥉"][i]}</span>
        ${crest(p.team_name)}
        <span class="p-name">${esc(p.player_name)}</span>
        <span class="p-team">${flag(p.country)} ${esc(p.team_name)}</span>
        <div class="podium-block"><span class="g">${p.goals}</span><small>GOLES</small></div>
      </div>`
    )
    .join("");
  list.innerHTML = state.scorers
    .map(
      (p, i) => `<li class="scorer${p.id === bumpId ? " bump" : ""}" style="animation-delay:${i * 30}ms">
        <span class="rk">${i + 1}</span>
        <div class="who"><b>${esc(p.player_name)}</b><span>${flag(p.country)} ${esc(p.team_name)}</span></div>
        <span class="gl">${p.goals}<small>G</small></span>
        <button class="goal-btn" data-player="${p.id}" title="Sumar un gol">+1 ⚽</button>
      </li>`
    )
    .join("");
}

// POST /api/top-scorers → sumar un gol
$("#scorersList").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-player]");
  if (!btn) return;
  const id = Number(btn.dataset.player);
  requireAuth(async () => {
    try {
      const data = await api("/top-scorers", { method: "POST", body: { player_id: id, goals: 1 }, auth: true });
      toast(`⚽ ${data.message} · ${data.total_goals} goles`, "ok");
      const res = await api("/top-scorers");
      state.scorers = res.top_scorers;
      renderScorers(id);
    } catch (err) {
      toast(err.message, "err");
    }
  });
});

// POST /api/players → registrar jugador
$("#addPlayerBtn").addEventListener("click", () =>
  requireAuth(() => {
    const f = $("#playerForm");
    f.reset();
    $("#playerError").textContent = "";
    fillTeamSelect("#playerTeam", 0);
    openModal("#playerModal");
  })
);

$("#playerForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const body = { name: f.name.value.trim(), team_id: Number(f.team_id.value), goals: Number(f.goals.value) };
  try {
    const data = await api("/players", { method: "POST", body, auth: true });
    closeModal("#playerModal");
    toast(`${data.player.name} (${data.player.team_name}) registrado`, "ok");
    loadScorers();
  } catch (err) {
    if (err.status === 401) {
      closeModal("#playerModal");
      toast(err.message, "err");
    } else {
      $("#playerError").textContent = err.message;
    }
  }
});

/* ---------- Calendario ---------- */
// POST /api/schedule/generate
$("#genScheduleBtn").addEventListener("click", () =>
  requireAuth(async () => {
    try {
      state.schedule = await api("/schedule/generate", { method: "POST", auth: true });
      renderSchedule();
      toast(state.schedule.message, "ok");
    } catch (err) {
      toast(err.message, "err");
    }
  })
);

function renderSchedule() {
  const s = state.schedule;
  if (!s) return;
  $("#scheduleInfo").innerHTML = `<div class="schedule-summary">
      <span class="chip"><b>${s.schedule.length}</b> encuentros</span>
      <span class="chip"><b>${s.total_rounds}</b> jornadas</span>
      <span class="chip"><b>${state.teams.length}</b> equipos</span>
    </div>`;
  $("#scheduleGrid").innerHTML = s.schedule
    .map(
      (m, i) => `<div class="fixture" style="animation-delay:${Math.min(i, 20) * 25}ms">
        <span class="num">PARTIDO ${i + 1}</span>
        <span class="status">${esc(m.status)}</span>
        <div class="team">${crest(m.home_team)}<span>${esc(m.home_team)}</span></div>
        <span class="vs">VS</span>
        <div class="team">${crest(m.away_team)}<span>${esc(m.away_team)}</span></div>
        <button class="play" data-home="${esc(m.home_team)}" data-away="${esc(m.away_team)}">Registrar resultado →</button>
      </div>`
    )
    .join("");
}

// Lleva el cruce elegido al formulario de partidos
$("#scheduleGrid").addEventListener("click", (e) => {
  const btn = e.target.closest(".play");
  if (!btn) return;
  const home = teamByName(btn.dataset.home);
  const away = teamByName(btn.dataset.away);
  if (!home || !away) {
    toast("Alguno de los equipos ya no existe", "err");
    return;
  }
  $("#homeTeam").value = home.id;
  $("#awayTeam").value = away.id;
  $("#homeGoals").value = 0;
  $("#awayGoals").value = 0;
  updateCrests();
  document.getElementById("partidos").scrollIntoView();
  setTimeout(() => $("#homeGoals").focus(), 400);
});

/* ---------- Eliminatoria ida y vuelta ---------- */
function updateKoCrests() {
  for (const [sel, slot] of [["#ko1", "#ko1Crest"], ["#ko2", "#ko2Crest"]]) {
    const t = state.teams.find((x) => String(x.id) === $(sel).value);
    $(slot).innerHTML = t ? crest(t.name, true) : "";
  }
}
$("#ko1").addEventListener("change", updateKoCrests);
$("#ko2").addEventListener("change", updateKoCrests);

// "Equipo A 2 - 1 Equipo B" → [2, 1]
function legScore(text, firstTeam) {
  const m = text.slice(firstTeam.length).match(/^\s*(\d+)\s*-\s*(\d+)/);
  return m ? [Number(m[1]), Number(m[2])] : [0, 0];
}

function legRow(label, home, away, [h, a], extra = "") {
  return `<div class="leg ${extra}">
    <span class="lbl">${label}</span>
    <span class="h ${h > a ? "win" : ""}">${esc(home)}</span>
    <span class="sc">${h} - ${a}</span>
    <span class="a ${a > h ? "win" : ""}">${esc(away)}</span>
  </div>`;
}

// POST /api/knockout/simulate
$("#knockoutForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const t1 = state.teams.find((t) => String(t.id) === $("#ko1").value);
  const t2 = state.teams.find((t) => String(t.id) === $("#ko2").value);
  if (!t1 || !t2 || t1.id === t2.id) {
    toast("Elige dos equipos diferentes", "err");
    return;
  }
  requireAuth(async () => {
    try {
      const r = await api("/knockout/simulate", { method: "POST", body: { team1_id: t1.id, team2_id: t2.id }, auth: true });
      $("#koResult").innerHTML = `<div class="ko-legs">
          ${legRow("Ida", t1.name, t2.name, legScore(r.leg_1, t1.name))}
          ${legRow("Vuelta", t2.name, t1.name, legScore(r.leg_2, t2.name))}
          ${legRow("Global", t1.name, t2.name, legScore(r.aggregate_score, t1.name), "agg")}
        </div>
        <div class="qualified">
          <small>Clasificado a la siguiente ronda</small>
          ${crest(r.qualified_to_next_round, true)}
          <b>${esc(r.qualified_to_next_round)}</b>
          ${r.penalties_needed ? `<span class="pens">Decidido en penaltis</span>` : ""}
        </div>`;
    } catch (err) {
      toast(err.message, "err");
    }
  });
});

/* ---------- Calculadora de clasificación ---------- */
// GET /api/teams/<id>/qualification-calculator
async function renderQualification(teamId, target) {
  try {
    const q = await api(`/teams/${teamId}/qualification-calculator`);
    const pct = q.qualification_threshold_points
      ? Math.min(100, Math.round((q.current_points / q.qualification_threshold_points) * 100))
      : 100;
    const secured = q.is_mathematically_eligible && q.points_needed_to_qualify === 0;
    const badge = !q.is_mathematically_eligible
      ? `<span class="qual-badge no">Eliminado</span>`
      : secured
        ? `<span class="qual-badge done">Clasificado</span>`
        : `<span class="qual-badge ok">En carrera</span>`;
    target.innerHTML = `<div class="qual-box">
        <div class="qual-head">${crest(q.team)}<b>${esc(q.team)}</b>${badge}</div>
        <div class="meter ${q.is_mathematically_eligible ? "" : "no"}"><span></span></div>
        <div class="meter-lbl"><span>${q.current_points} pts</span><span>Meta: ${q.qualification_threshold_points} pts</span></div>
        <div class="qual-grid">
          <div><b>${q.points_needed_to_qualify}</b><small>Puntos que faltan</small></div>
          <div><b>${q.matches_remaining}</b><small>Partidos restantes</small></div>
          <div><b>${q.matches_played}</b><small>Partidos jugados</small></div>
          <div><b>${q.matches_remaining * 3}</b><small>Puntos en juego</small></div>
        </div>
        <p class="qual-msg ${q.is_mathematically_eligible ? "" : "no"}">${esc(q.status_message)}</p>
      </div>`;
    // animar la barra después de pintarla
    setTimeout(() => {
      target.querySelector(".meter span").style.width = pct + "%";
    }, 60);
  } catch (err) {
    target.innerHTML = "";
    toast(err.message, "err");
  }
}

$("#qualForm").addEventListener("submit", (e) => {
  e.preventDefault();
  renderQualification(Number($("#qualTeam").value), $("#qualResult"));
});

/* ---------- Navegación ---------- */
["goleadores", "calendario", "simulador"].forEach((id) => observer.observe(document.getElementById(id)));
