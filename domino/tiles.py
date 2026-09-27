"""
domino/tiles.py — Fichas del dominó
=====================================

Archivo 2 de la estructura nueva (ver ANALISIS_Y_PLAN_MODOS.txt).

Antes esto estaba hardcodeado al doble-6 (range(7) fijo). Ahora
generar_fichas() recibe doble_max como parámetro — quien la llama
(el motor de partida, usando domino/modos.py) decide si arma un
set de 28 fichas (doble_max=6) o de 55 (doble_max=9).

A propósito NO se le puso un valor por default a doble_max: el
análisis previo (sección 2, hallazgos) marcó como bug justamente
que el código viejo diera por hecho un tamaño de set fijo en un
punto donde no debía. Obligar a que quien llama lo pase explícito
evita que se cuele el mismo tipo de supuesto oculto otra vez.

    0: "🍓",
    1: "🫐",
    2: "🍊",
    3: "🍉",
    4: "🥥",
    5: "🍋",
    6: "🍇",
    7: "🍌",
    8: "🍐",
    9: "🥭",

"""

EMOJI_NUM = {
    0: "0️⃣",
    1: "1️⃣",
    2: "2️⃣",
    3: "3️⃣",
    4: "4️⃣",
    5: "5️⃣",
    6: "6️⃣",
    7: "7️⃣",
    8: "8️⃣",
    9: "9️⃣",
}


def generar_fichas(doble_max: int) -> list:
    """
    Todas las fichas del set, sin repetir: (0,0) hasta (doble_max,
    doble_max).

    doble_max=6 -> set doble-6, 28 fichas.
    doble_max=9 -> set doble-9, 55 fichas.
    """
    return [(a, b) for a in range(doble_max + 1) for b in range(a, doble_max + 1)]


def emoji_ficha(a: int, b: int) -> str:
    return f"{EMOJI_NUM[a]}{EMOJI_NUM[b]}"


def valor_ficha(ficha) -> int:
    """
    Suma de pips de una ficha, ej. (4, 2) -> 6.

    Se saca como función propia (en vez de dejarlo repetido como
    'a + b' suelto en cada lugar que lo necesita) porque dos piezas
    futuras van a usar exactamente este cálculo: Partida.puntos_mano
    (domino/game.py) para el desempate por bloqueo, y la regla de
    apertura con fallback cuando nadie tiene el doble más alto
    repartido (también en domino/game.py) — ahí se busca la ficha
    de mayor valor total en toda la mesa.
    """
    a, b = ficha
    return a + b
