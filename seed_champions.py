"""Reinicia la base de datos con los 36 equipos reales de la UEFA Champions League 2026/27.

Borra todos los equipos, partidos y jugadores existentes y crea:
  - los 36 clubes de la fase de liga 2026/27 (todos con estadísticas en cero)
  - 3 jugadores por club (108 en total), con 0 goles

Jugadores tomados de la guía oficial de UEFA "Meet the 2026/27 Champions League
league phase teams": jugador clave, jugador a seguir y gran fichaje de verano.

Uso:
  python seed_champions.py
"""

import sqlite3

from app import init_db

DB_PATH = "champions.db"

# (club, país, [jugador clave, jugador a seguir, gran fichaje])
TEAMS = [
    ("Real Madrid", "España", ["Kylian Mbappé", "Yan Diomande", "Marc Cucurella"]),
    ("FC Barcelona", "España", ["Lamine Yamal", "Marc Bernal", "Rodri"]),
    ("Atlético de Madrid", "España", ["Julián Álvarez", "Rodrigo Mendoza", "Morten Hjulmand"]),
    ("Real Betis", "España", ["Antony", "Abde Ezzalzouli", "Fran García"]),
    ("Villarreal", "España", ["Georges Mikautadze", "Alberto Moleiro", "Nathan Saliba"]),
    ("Liverpool", "Inglaterra", ["Virgil van Dijk", "Rio Ngumoha", "Bradley Barcola"]),
    ("Manchester City", "Inglaterra", ["Erling Haaland", "Nico O'Reilly", "Elliot Anderson"]),
    ("Arsenal", "Inglaterra", ["Bukayo Saka", "Max Dowman", "Bruno Guimarães"]),
    ("Aston Villa", "Inglaterra", ["Boubacar Kamara", "Ibrahim Mbaye", "Johan Manzambi"]),
    ("Manchester United", "Inglaterra", ["Bruno Fernandes", "Leny Yoro", "Youri Tielemans"]),
    ("Bayern München", "Alemania", ["Harry Kane", "Lennart Karl", "Ismael Saibari"]),
    ("Borussia Dortmund", "Alemania", ["Serhou Guirassy", "Jobe Bellingham", "Konstantinos Karetsas"]),
    ("RB Leipzig", "Alemania", ["Christoph Baumgartner", "Antonio Nusa", "Maxime Estève"]),
    ("VfB Stuttgart", "Alemania", ["Deniz Undav", "Finn Jeltsch", "Bilal El Khannouss"]),
    ("Paris Saint-Germain", "Francia", ["Khvicha Kvaratskhelia", "Maghnes Akliouche", "Ferran Torres"]),
    ("Lille", "Francia", ["Benjamin André", "Nathan Ngoy", "Ayase Ueda"]),
    ("Lens", "Francia", ["Florian Thauvin", "Robin Risser", "Thorgan Hazard"]),
    ("Inter", "Italia", ["Lautaro Martínez", "Pio Esposito", "John Stones"]),
    ("Napoli", "Italia", ["Rasmus Højlund", "Alisson Santos", "Benoît Badiashile"]),
    ("Roma", "Italia", ["Manu Koné", "Niccolò Pisilli", "Donyell Malen"]),
    ("Como", "Italia", ["Nico Paz", "Jacobo Ramón", "Trevoh Chalobah"]),
    ("Sporting CP", "Portugal", ["Luis Suárez", "Gonçalo Inácio", "Rodrigo Zalazar"]),
    ("Porto", "Portugal", ["Diogo Costa", "Victor Froholdt", "Jakub Kiwior"]),
    ("PSV Eindhoven", "Países Bajos", ["Ricardo Pepi", "Noah Fernandez", "Sven Mijnans"]),
    ("Feyenoord", "Países Bajos", ["Luciano Valente", "Givairo Read", "Nacho Ferri"]),
    ("Club Brugge", "Bélgica", ["Hans Vanaken", "Joaquin Seys", "Yann Sommer"]),
    ("Galatasaray", "Turquía", ["Victor Osimhen", "Renato Nhaga", "Lesley Ugochukwu"]),
    ("Fenerbahçe", "Turquía", ["N'Golo Kanté", "Dorgeles Nene", "Romelu Lukaku"]),
    ("Bodø/Glimt", "Noruega", ["Patrick Berg", "Andreas Helmersen", "Joshua Kitolano"]),
    ("Viking", "Noruega", ["Zlatko Tripić", "Henrik Falchener", "Erik Botheim"]),
    ("Shakhtar Donetsk", "Ucrania", ["Pedrinho", "Kauã Elias", "Bruninho"]),
    ("Slavia Praga", "República Checa", ["Lukáš Provod", "Wiktor Nowak", "Ange N'Guessan"]),
    ("Slovan Bratislava", "Eslovaquia", ["Andraž Šporar", "Nino Marcelli", "Suleiman Camara"]),
    ("AEK Atenas", "Grecia", ["Luka Jović", "Zini", "Oleksandr Zubkov"]),
    ("LASK", "Austria", ["Samuel Adeniran", "Moses Usor", "Robert Ljubičić"]),
    ("Sabah", "Azerbaiyán", ["Veljko Simić", "Joy-Lance Mickels", "Tymoteusz Puchacz"]),
]


def seed():
  init_db()  # garantiza que existan las tablas
  conn = sqlite3.connect(DB_PATH)
  cur = conn.cursor()

  cur.execute("DELETE FROM players")
  cur.execute("DELETE FROM matches")
  cur.execute("DELETE FROM teams")
  # Reinicia los contadores de ID para que empiecen en 1
  cur.execute(
      "DELETE FROM sqlite_sequence WHERE name IN ('players', 'matches', 'teams')"
  )

  for name, country, players in TEAMS:
    cur.execute(
        "INSERT INTO teams (name, country) VALUES (?, ?)", (name, country)
    )
    team_id = cur.lastrowid
    cur.executemany(
        "INSERT INTO players (name, team_id, goals) VALUES (?, ?, 0)",
        [(p, team_id) for p in players],
    )

  conn.commit()
  teams = cur.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
  players = cur.execute("SELECT COUNT(*) FROM players").fetchone()[0]
  conn.close()
  print(f"Base de datos reiniciada: {teams} equipos y {players} jugadores.")


if __name__ == "__main__":
  seed()
