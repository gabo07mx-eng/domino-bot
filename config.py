"""
config.py — Configuración general del bot de Dominó
=====================================================

Archivo 1 de la estructura nueva (ver ANALISIS_Y_PLAN_MODOS.txt).

Acá viven: el token del bot, el username, la ruta de la base de
datos, el logger compartido, y las pocas constantes que son
GLOBALES de verdad (no cambian según el modo de juego).

Lo que NO está acá a propósito:
- HAND_SIZE y MAX_PLAYERS: ya no son un número fijo para todo el
  bot. Cada modo tiene su propio hand_size y su propio rango
  min/max de jugadores. Eso vive en domino/modos.py (archivo 3).
- EMOJI_NUM: depende del set (doble-6 llega hasta 6, doble-9 hasta
  9). Vive en domino/tiles.py (archivo 2).
"""

import logging
import os

# ============================================================
# CREDENCIALES Y CONEXIÓN
# ============================================================
# Directo en el código, sin .env — decisión deliberada del dueño
# del proyecto (ver DESCRIPCION_TECNICA.txt, sección 6: .env dio
# problemas reales en Windows).
#
# ADVERTENCIA: como el token vive directo en el código fuente,
# este archivo NUNCA debe subirse a un repositorio público tal
# cual. Si en algún momento se sube a GitHub o se comparte, hay
# que volver primero al esquema de variables de entorno.

BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME")
DB_PATH = "wins.db"

# ============================================================
# CONSTANTES GLOBALES (no dependen del modo de juego)
# ============================================================

# Votos necesarios para cancelar una partida en curso.
# Nota pendiente (ANALISIS_Y_PLAN_MODOS.txt, sección 10, pregunta 3):
# quedó abierto si esto debería escalar con la cantidad de
# jugadores (con 3, dos votos ya es mayoría; con 4, no) en vez de
# quedar fijo. Se deja en 2 hasta que se decida.
CANCEL_VOTES_NEEDED = 2
# Temporizadores (en segundos). Los tres usan el JobQueue de
# python-telegram-bot, que NO viene en la instalación básica:
# hace falta `pip install "python-telegram-bot[job-queue]"`.
# Si el JobQueue no está disponible, el bot sigue funcionando
# igual que antes — simplemente no se aplican estos tiempos.
LOBBY_TIMEOUT_SEGUNDOS = 15 * 60        # mesa esperando jugadores
INACTIVIDAD_TIMEOUT_SEGUNDOS = 15 * 60  # partida ya arrancada, sin jugadas
VICTORIA_PIN_SEGUNDOS = 5 * 60          # cuánto queda fijado el mensaje final

# ============================================================
# LOGGING (compartido por todo el bot)
# ============================================================

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("domino_bot")
