"""
database.py — Persistencia SQLite (conteo de victorias)
===========================================================

Archivo 5 de la estructura nueva (ver ANALISIS_Y_PLAN_MODOS.txt,
sección 9, y el plan de 11 pasos).

Como en v1, esto es lo ÚNICO que persiste en disco. Las partidas
activas siguen viviendo solo en memoria (ver games_state.py, archivo
6) — si el bot se reinicia a mitad de una partida, esa partida se
pierde, decisión consciente para mantener todo simple (ver
DESCRIPCION_TECNICA.txt, sección 8).

QUÉ CAMBIA RESPECTO A V1
-------------------------
- La tabla `wins` (individual) se deja EXACTAMENTE igual — mismas
  columnas, mismo tipo, misma PRIMARY KEY. Si ya existe un wins.db de
  producción con datos reales de v1, esto abre y sigue funcionando
  sin ninguna migración.
- Se agrega una tabla nueva, `wins_parejas`, para los modos de
  equipos (66_eq, 99_eq). Es tabla nueva, no ALTER TABLE — cero costo
  de migración (ver ANALISIS_Y_PLAN_MODOS.txt sección 9, "mi
  sugerencia: dejarlo combinado... si deciden separar, hacerlo ANTES
  de que haya muchos datos").
- Por lo mismo (sección 9: "dejarlo combinado por ahora"), ninguna de
  las dos tablas distingue 66 de 99 — todas las victorias de un
  modo se suman igual, sin importar el set. Si en algún momento se
  decide separar por set, es agregar una columna `modo` a la
  PRIMARY KEY de ambas tablas.

SUPUESTO QUE ESTOY MARCANDO (no estaba 100% explícito en los
documentos, lo decido acá porque database.py lo necesita ya):
un jugador tiene DOS contadores separados que nunca se mezclan —
sus victorias jugando individual (tabla `wins`) y sus victorias
jugando en pareja (tabla `wins_parejas`, una fila POR DUPLA, no por
jugador suelto). Ganar en equipo NO incrementa tu fila individual en
`wins`; solo incrementa la fila de esa pareja específica. Esto es lo
que hace que tenga sentido un `/top_parejas` separado de `/top` (ver
el plan de 11 pasos, archivo 10) — si una victoria en equipo también
subiera tu contador individual, ambos rankings terminarían mezclando
lo mismo. Si en realidad querías que también contara para el
individual, es un cambio de una línea (llamar además a
db_record_win por cada integrante) y me avisas.

NORMALIZACIÓN DE LA PAREJA: como una dupla es "Juan y María" sin
importar quién se unió primero al equipo A o B, wins_parejas
identifica a la pareja por sus dos user_id ORDENADOS (el menor
siempre en user_id_1). Esto es responsabilidad de
db_record_win_pareja() (ver _normalizar_pareja) — así "Juan+María" y
"María+Juan" caen siempre en la misma fila, en vez de crear dos filas
distintas para la misma dupla real.

nombre_seguro() (la limpieza de caracteres que rompen Markdown) NO
vive acá — se aplica en texto_teclados.py (archivo 7) al crear al
Jugador, antes de que el nombre llegue a este módulo. database.py
asume que los nombres que recibe ya vienen limpios.
"""

import sqlite3

from config import DB_PATH


def db_connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def db_init() -> None:
    with db_connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS wins (
                user_id       INTEGER NOT NULL,
                chat_id       INTEGER NOT NULL,
                display_name  TEXT NOT NULL,
                wins_count    INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, chat_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS wins_parejas (
                user_id_1     INTEGER NOT NULL,
                user_id_2     INTEGER NOT NULL,
                chat_id       INTEGER NOT NULL,
                nombre_1      TEXT NOT NULL,
                nombre_2      TEXT NOT NULL,
                wins_count    INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id_1, user_id_2, chat_id)
            )
            """
        )
        conn.commit()


# ============================================================
# VICTORIAS — INDIVIDUAL (tabla wins, igual que v1)
# ============================================================


def db_record_win(user_id: int, chat_id: int, display_name: str) -> None:
    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO wins (user_id, chat_id, display_name, wins_count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(user_id, chat_id)
            DO UPDATE SET
                wins_count = wins_count + 1,
                display_name = excluded.display_name
            """,
            (user_id, chat_id, display_name),
        )
        conn.commit()


def db_top_chat(chat_id: int, limit: int = 10):
    """Top individual de ganadores de ESTE grupo."""
    with db_connect() as conn:
        cur = conn.execute(
            """
            SELECT display_name, wins_count
            FROM wins
            WHERE chat_id = ?
            ORDER BY wins_count DESC
            LIMIT ?
            """,
            (chat_id, limit),
        )
        return cur.fetchall()


def db_top_global(limit: int = 10):
    """Top individual sumando victorias de TODOS los grupos."""
    with db_connect() as conn:
        cur = conn.execute(
            """
            SELECT MAX(display_name) AS nombre, SUM(wins_count) AS total
            FROM wins
            GROUP BY user_id
            ORDER BY total DESC
            LIMIT ?
            """,
            (limit,),
        )
        return cur.fetchall()


# ============================================================
# VICTORIAS — POR PAREJA (tabla wins_parejas, NUEVA)
# ============================================================


def _normalizar_pareja(user_id_a: int, nombre_a: str, user_id_b: int, nombre_b: str):
    """
    Ordena la dupla por user_id para que "Juan+María" y "María+Juan"
    caigan siempre en la misma fila, sin importar quién entró primero
    al equipo. Devuelve (user_id_1, nombre_1, user_id_2, nombre_2) con
    user_id_1 <= user_id_2.
    """
    if user_id_a <= user_id_b:
        return user_id_a, nombre_a, user_id_b, nombre_b
    return user_id_b, nombre_b, user_id_a, nombre_a


def db_record_win_pareja(
    user_id_a: int, nombre_a: str, user_id_b: int, nombre_b: str, chat_id: int
) -> None:
    uid1, n1, uid2, n2 = _normalizar_pareja(user_id_a, nombre_a, user_id_b, nombre_b)
    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO wins_parejas
                (user_id_1, user_id_2, chat_id, nombre_1, nombre_2, wins_count)
            VALUES (?, ?, ?, ?, ?, 1)
            ON CONFLICT(user_id_1, user_id_2, chat_id)
            DO UPDATE SET
                wins_count = wins_count + 1,
                nombre_1 = excluded.nombre_1,
                nombre_2 = excluded.nombre_2
            """,
            (uid1, uid2, chat_id, n1, n2),
        )
        conn.commit()


def db_top_chat_parejas(chat_id: int, limit: int = 10):
    """Top de parejas de ESTE grupo."""
    with db_connect() as conn:
        cur = conn.execute(
            """
            SELECT nombre_1, nombre_2, wins_count
            FROM wins_parejas
            WHERE chat_id = ?
            ORDER BY wins_count DESC
            LIMIT ?
            """,
            (chat_id, limit),
        )
        return cur.fetchall()


def db_top_global_parejas(limit: int = 10):
    """Top de parejas sumando victorias de TODOS los grupos."""
    with db_connect() as conn:
        cur = conn.execute(
            """
            SELECT MAX(nombre_1) AS nombre_1, MAX(nombre_2) AS nombre_2,
                   SUM(wins_count) AS total
            FROM wins_parejas
            GROUP BY user_id_1, user_id_2
            ORDER BY total DESC
            LIMIT ?
            """,
            (limit,),
        )
        return cur.fetchall()
