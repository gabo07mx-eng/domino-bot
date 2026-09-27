"""
games_state.py — Estado en memoria de las partidas activas
==============================================================

Archivo 6 de la estructura nueva. Sin cambios de fondo respecto a v1
(bot.py, SECCIÓN 5) — sigue siendo un diccionario simple, una sola
partida activa (o en lobby) por grupo.

Lo único que cambió es de dónde viene el tipo Partida (ahora
domino/game.py, archivo 4, en vez de vivir en el mismo archivo). El
diccionario en sí no necesita saber nada de modos: da igual si el
chat_id tiene una partida de 66 individual o de 99 por equipos,
Partida.modo (domino/game.py) ya lleva esa información — este archivo
no necesita una entrada por modo ni ninguna rama especial.

Como en v1: si el bot se reinicia, todas las partidas en curso se
pierden (decisión consciente, ver DESCRIPCION_TECNICA.txt sección 8,
"ESTADO SOLO EN MEMORIA"). Lo único que persiste en disco es el
conteo de victorias (database.py, archivo 5).
"""

from domino.game import Partida

partidas: dict[int, Partida] = {}
