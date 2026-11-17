"""Lógica del torneo (función especial, RF10).

Son funciones puras: reciben listas de diccionarios y devuelven resultados,
sin tocar la base de datos. Así se pueden probar fácilmente.

Reglas del torneo
-----------------
* Liga todos contra todos, ida y vuelta: cada pareja juega una vez con cada
  equipo como local (máximo 2 partidos entre dos equipos).
* Victoria 3 puntos, empate 1, derrota 0.
* Orden de la tabla: puntos, diferencia de goles, goles a favor, nombre.
"""
import math
import random

STAT_KEYS = ("points", "pj", "pg", "pe", "pp", "gf", "gc", "dg")


def empty_stats():
    return {k: 0 for k in STAT_KEYS}


def compute_stats(team_ids, matches):
    """Calcula las estadísticas de cada equipo a partir de los partidos jugados."""
    stats = {tid: empty_stats() for tid in team_ids}
    for m in matches:
        h, a = m["home_team_id"], m["away_team_id"]
        hg, ag = m["home_goals"], m["away_goals"]
        for tid, gf, gc in ((h, hg, ag), (a, ag, hg)):
            if tid not in stats:
                continue
            s = stats[tid]
            s["pj"] += 1
            s["gf"] += gf
            s["gc"] += gc
            if gf > gc:
                s["pg"] += 1
                s["points"] += 3
            elif gf == gc:
                s["pe"] += 1
                s["points"] += 1
            else:
                s["pp"] += 1
            s["dg"] = s["gf"] - s["gc"]
    return stats


def sort_standings(teams, stats):
    """Tabla ordenada de equipos (lista de dicts con estadísticas y posición)."""
    rows = [{**t, **stats[t["id"]]} for t in teams]
    rows.sort(key=lambda r: (-r["points"], -r["dg"], -r["gf"], r["name"].lower()))
    for pos, row in enumerate(rows, start=1):
        row["position"] = pos
    return rows


def default_spots(n_teams, configured=0):
    """Cupos de clasificación: los configurados o la mitad de los equipos."""
    if configured and 0 < configured < n_teams:
        return configured
    return max(1, n_teams // 2)


def _played_between(matches):
    """Cuántos partidos se han jugado entre cada pareja (sin importar localía)."""
    played = {}
    for m in matches:
        key = frozenset((m["home_team_id"], m["away_team_id"]))
        played[key] = played.get(key, 0) + 1
    return played


def remaining_matches(team_id, active_ids, matches):
    """Partidos que le faltan a un equipo contra los demás equipos activos."""
    played = _played_between(matches)
    return sum(max(0, 2 - played.get(frozenset((team_id, o)), 0)) for o in active_ids if o != team_id)


def qualification(team_id, active_teams, matches, spots):
    """Calculadora matemática de clasificación.

    Un equipo está:
    * CLASIFICADO si menos de `spots` rivales pueden llegar a sus puntos actuales.
    * ELIMINADO si al menos `spots` rivales ya tienen más puntos que el máximo
      que él podría alcanzar ganando todo lo que le falta.
    * EN DISPUTA en cualquier otro caso.

    Para los equipos en disputa calcula cuántas victorias necesita para
    asegurar el cupo sin depender de nadie. Cada victoria contra un rival
    directo también le quita 3 puntos posibles a ese rival, por eso se
    eligen primero los partidos contra los rivales más peligrosos.
    """
    names = {t["id"]: t["name"] for t in active_teams}
    ids = list(names)
    stats = compute_stats(ids, matches)
    played = _played_between(matches)
    rem = {tid: remaining_matches(tid, ids, matches) for tid in ids}
    max_pts = {tid: stats[tid]["points"] + 3 * rem[tid] for tid in ids}

    me = stats[team_id]
    current = me["points"]
    my_rem = rem[team_id]
    my_max = current + 3 * my_rem
    rivals = [o for o in ids if o != team_id]
    left_vs_me = {o: max(0, 2 - played.get(frozenset((team_id, o)), 0)) for o in rivals}

    above_my_max = sum(1 for o in rivals if stats[o]["points"] > my_max)
    can_reach_me = sum(1 for o in rivals if max_pts[o] >= current)

    wins_needed = None
    beat = []
    if above_my_max >= spots:
        status = "eliminado"
    elif can_reach_me < spots:
        status = "clasificado"
        wins_needed = 0
    else:
        status = "en_disputa"
        adjusted = dict(max_pts)
        left = dict(left_vs_me)
        for wins in range(1, my_rem + 1):
            # gana el partido contra el rival que más puntos puede alcanzar
            target = max((o for o in rivals if left[o] > 0), key=lambda o: adjusted[o])
            adjusted[target] -= 3
            left[target] -= 1
            beat.append(target)
            if sum(1 for o in rivals if adjusted[o] >= current + 3 * wins) < spots:
                wins_needed = wins
                break

    if status == "clasificado":
        message = "Clasificación asegurada matemáticamente."
    elif status == "eliminado":
        message = (
            f"Eliminado matemáticamente: aun ganando todo llegaría a {my_max} puntos "
            f"y {above_my_max} rivales ya tienen más."
        )
    elif wins_needed is not None:
        direct = list(dict.fromkeys(names[o] for o in beat))[:3]
        cuantos = f"todos sus {my_rem}" if wins_needed == my_rem else f"{wins_needed} de sus {my_rem}"
        message = (
            f"Asegura la clasificación si gana {cuantos} partidos restantes, "
            f"empezando por sus rivales directos ({', '.join(direct)})."
        )
    elif my_rem == 0:
        message = "Ya jugó todos sus partidos: su clasificación depende de otros resultados y del desempate."
    else:
        message = "Sigue con opciones, pero aunque gane todo depende de los resultados de otros equipos."

    return {
        "team_id": team_id,
        "current_points": current,
        "matches_played": me["pj"],
        "matches_remaining": my_rem,
        "max_possible_points": my_max,
        "qualification_spots": spots,
        "status": status,
        "wins_needed_to_secure": wins_needed,
        "points_needed_to_secure": None if wins_needed is None else 3 * wins_needed,
        "message": message,
    }


def generate_fixture(teams, matches=(), double_round=True, only_pending=False):
    """Calendario todos contra todos con el método del círculo.

    Cada jornada empareja a todos los equipos (si son impares, uno descansa).
    Con `double_round` se agrega la vuelta invirtiendo la localía.
    Con `only_pending` se omiten los partidos que ya se jugaron.
    """
    ids = [t["id"] for t in teams]
    names = {t["id"]: t["name"] for t in teams}
    if len(ids) < 2:
        return []
    slots = ids + ([None] if len(ids) % 2 else [])
    n = len(slots)
    played = {(m["home_team_id"], m["away_team_id"]) for m in matches}

    first_leg = []
    rotation = slots[:]
    for rnd in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = rotation[i], rotation[n - 1 - i]
            if a is None or b is None:
                continue
            # alterna la localía para que nadie juegue siempre en casa
            home, away = (a, b) if (rnd + i) % 2 == 0 else (b, a)
            pairs.append((home, away))
        first_leg.append(pairs)
        rotation = [rotation[0]] + [rotation[-1]] + rotation[1:-1]

    legs = first_leg + ([[(a, h) for h, a in r] for r in first_leg] if double_round else [])

    rounds = []
    for number, pairs in enumerate(legs, start=1):
        games = [
            {
                "home_team_id": h,
                "home_team": names[h],
                "away_team_id": a,
                "away_team": names[a],
                "status": "jugado" if (h, a) in played else "pendiente",
            }
            for h, a in pairs
        ]
        if only_pending:
            games = [g for g in games if g["status"] == "pendiente"]
        if games:
            rounds.append({"round": number, "matches": games})
    return rounds


def _poisson(rng, lam):
    """Número aleatorio con distribución de Poisson (algoritmo de Knuth)."""
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def simulate_knockout(t1, t2, stats, seed=None):
    """Simula una eliminatoria ida y vuelta.

    La fuerza de cada equipo sale de sus puntos por partido en la liga:
    goles esperados = 1.3 + 0.4 * (ppp propio - ppp rival), entre 0.3 y 3.
    Si el global queda empatado se define por penales (5 tiros y muerte súbita).
    Con la misma `seed` el resultado siempre es el mismo (reproducible).
    """
    rng = random.Random(seed)

    def ppg(tid):
        s = stats.get(tid) or empty_stats()
        return s["points"] / s["pj"] if s["pj"] else 1.0

    def expected(own, rival):
        return min(3.0, max(0.3, 1.3 + 0.4 * (ppg(own) - ppg(rival))))

    xg1, xg2 = expected(t1["id"], t2["id"]), expected(t2["id"], t1["id"])
    leg1 = (_poisson(rng, xg1 * 1.1), _poisson(rng, xg2 * 0.9))  # t1 local
    leg2 = (_poisson(rng, xg2 * 1.1), _poisson(rng, xg1 * 0.9))  # t2 local
    agg1, agg2 = leg1[0] + leg2[1], leg1[1] + leg2[0]

    penalties = None
    if agg1 > agg2:
        winner = t1
    elif agg2 > agg1:
        winner = t2
    else:
        p1 = p2 = 0
        for _ in range(5):
            p1 += rng.random() < 0.76
            p2 += rng.random() < 0.76
        while p1 == p2:
            p1 += rng.random() < 0.76
            p2 += rng.random() < 0.76
        penalties = {"team1": p1, "team2": p2}
        winner = t1 if p1 > p2 else t2

    return {
        "team1": {"id": t1["id"], "name": t1["name"], "expected_goals_per_match": round(xg1, 2)},
        "team2": {"id": t2["id"], "name": t2["name"], "expected_goals_per_match": round(xg2, 2)},
        "leg_1": {"home": t1["name"], "away": t2["name"], "home_goals": leg1[0], "away_goals": leg1[1]},
        "leg_2": {"home": t2["name"], "away": t1["name"], "home_goals": leg2[0], "away_goals": leg2[1]},
        "aggregate": {"team1": agg1, "team2": agg2},
        "penalties": penalties,
        "winner": {"id": winner["id"], "name": winner["name"]},
        "seed": seed,
    }
