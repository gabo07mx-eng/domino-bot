"""
domino/modos.py — Registro de modos de juego
===============================================

Archivo 3 de la estructura nueva (ver ANALISIS_Y_PLAN_MODOS.txt,
sección 3 y 4).

Esta es la pieza central de la arquitectura "motor único": las
diferencias entre los 4 modos (66 Individual, 66 Equipos, 99
Individual, 99 Equipos) NO están repartidas en código duplicado —
están concentradas acá, como datos. El resto del proyecto
(domino/game.py, los handlers) lee esta tabla en vez de tener un
"if modo == '66'" regado por todos lados.

Supuesto explícito (pregunta abierta #1 del análisis): los modos
de equipos son siempre 2v2 fijo con 4 jugadores — por eso ahí
min_jugadores == max_jugadores. Si en algún momento quieren un
modo de equipos a 3 (2v1), es un cambio de diseño aparte, no solo
una fila nueva en esta tabla.
"""

from .tiles import generar_fichas

MODOS = {
    "66_ind": {
        "nombre": "Dominó 6-6 — Individual",
        "doble_max": 6,
        "hand_size": 7,
        "min_jugadores": 2,
        "max_jugadores": 4,
        "equipos": False,
        "comando": "jugar_66_ind",
    },
    "66_eq": {
        "nombre": "Dominó 6-6 — Por Equipos",
        "doble_max": 6,
        "hand_size": 7,
        "min_jugadores": 4,
        "max_jugadores": 4,
        "equipos": True,
        "comando": "jugar_66_par",
    },
    "99_ind": {
        "nombre": "Dominó 9-9 — Individual",
        "doble_max": 9,
        "hand_size": 10,
        "min_jugadores": 2,
        "max_jugadores": 4,
        "equipos": False,
        "comando": "jugar_99_ind",
    },
    "99_eq": {
        "nombre": "Dominó 9-9 — Por Equipos",
        "doble_max": 9,
        "hand_size": 10,
        "min_jugadores": 4,
        "max_jugadores": 4,
        "equipos": True,
        "comando": "jugar_99_par",
    },
}


def obtener_modo(clave: str) -> dict:
    """
    Devuelve la configuración de un modo por su clave. Falla con un
    mensaje claro (en vez de un KeyError crudo sin contexto) si
    algún handler pide una clave que no existe.
    """
    try:
        return MODOS[clave]
    except KeyError:
        raise KeyError(
            f"'{clave}' no es un modo válido. Modos disponibles: "
            f"{', '.join(MODOS)}"
        )


def _validar_modos() -> None:
    """
    Chequeo de consistencia interna de la tabla, corre una sola vez
    al importar este archivo. No es lógica de juego — es una red de
    seguridad para que un error de tipeo acá (un hand_size que ya
    no cabe en el set, un modo de equipos con min distinto de max)
    truene en el arranque del bot con un mensaje claro, en vez de
    aparecer como un bug raro a mitad de una partida real.
    """
    for clave, cfg in MODOS.items():
        total_fichas = len(generar_fichas(cfg["doble_max"]))

        if cfg["min_jugadores"] > cfg["max_jugadores"]:
            raise ValueError(f"Modo '{clave}': min_jugadores > max_jugadores.")

        if cfg["hand_size"] * cfg["max_jugadores"] > total_fichas:
            raise ValueError(
                f"Modo '{clave}': hand_size ({cfg['hand_size']}) x "
                f"max_jugadores ({cfg['max_jugadores']}) supera las "
                f"{total_fichas} fichas del set doble-{cfg['doble_max']}."
            )

        if cfg["equipos"] and cfg["min_jugadores"] != cfg["max_jugadores"]:
            raise ValueError(
                f"Modo '{clave}': los modos de equipos deben tener "
                "min_jugadores == max_jugadores (2v2 fijo, sin rango)."
            )


_validar_modos()
