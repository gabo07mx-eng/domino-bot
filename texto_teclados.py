"""
texto_teclados.py — Textos y teclados compartidos (grupo y DMs) en formato HTML
================================================================================
"""

import html
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import BOT_USERNAME
from domino.game import Jugador, Partida
from domino.modos import MODOS
from domino.tiles import EMOJI_NUM, emoji_ficha


def nombre_seguro(nombre: str) -> str:
    """Limpia el nombre del jugador y escapa caracteres HTML de forma segura."""
    limpio = nombre.strip()
    base = limpio if limpio else "Jugador"
    return html.escape(base)


def emoji_ficha_marcada(a: int, b: int) -> str:
    """
    Igual que emoji_ficha, pero un doble sale entre 【 】 para que se
    note a simple vista que es doble en los botones de la mano.
    """
    cara = emoji_ficha(a, b)
    return f"【{cara}】" if a == b else cara


def _orden_mano(ficha) -> tuple:
    """Dobles primero (del más alto al más bajo), luego el resto por valor."""
    a, b = ficha
    return (0 if a == b else 1, -(a + b), -max(a, b))


def texto_jugadores(partida: Partida) -> str:
    turno_actual = partida.jugador_actual()
    lineas = []
    for i, jugador in enumerate(partida.jugadores, start=1):
        marca = " 👈" if jugador is turno_actual else ""
        eq_sym = "🔸 " if jugador.equipo == "A" else ("🔹 " if jugador.equipo == "B" else "")
        fichas_mano = f"🫲 {len(jugador.mano)}"
        nombre_esc = nombre_seguro(jugador.nombre)
        lineas.append(f"{i}. {eq_sym}{fichas_mano} {nombre_esc}{marca}")
    return "\n".join(lineas)


# Telegram no acepta pies de foto de más de 1024 caracteres.
LIMITE_CAPTION = 1024


def recortar_caption(texto: str) -> str:
    """Último corte de seguridad para no pasarse del límite de Telegram."""
    if len(texto) <= LIMITE_CAPTION:
        return texto
    return texto[: LIMITE_CAPTION - 1].rstrip() + "…"


def caption_tablero(partida: Partida, extra: str = "") -> str:
    """
    Pie de foto del tablero en formato HTML.
    Muestra las puntas, de quién es el turno, el historial y la lista de jugadores.
    """
    modo_cfg = MODOS[partida.modo]
    izq, der = partida.extremo_izq(), partida.extremo_der()
    turno = partida.jugador_actual()

    punta_izq = EMOJI_NUM[izq] if izq is not None else "▫️"
    punta_der = EMOJI_NUM[der] if der is not None else "▫️"
    
    turno_esc = nombre_seguro(turno.nombre) if turno else "—"
    nombre_modo = html.escape(modo_cfg['nombre'])

    cabeza = (
        f"<b>🁫 {nombre_modo}</b>\n"
        f"En las puntas {punta_izq} y {punta_der}\n"
        f"👉 Turno de: <b>{turno_esc}</b>"
    )
    cola = "\n\n" + texto_jugadores(partida) + extra

    historial = []
    if partida.texto_apertura:
        historial.append(partida.texto_apertura)
    if partida.historial:
        historial.extend(partida.historial)

    while True:
        bloque = "\n\n📜 <b>Historial:</b>\n" + "\n".join(historial) if historial else ""
        texto = cabeza + bloque + cola
        if len(texto) <= LIMITE_CAPTION or not historial:
            return recortar_caption(texto)
        historial.pop(0)


def teclado_mano(partida: Partida, jugador: Jugador) -> InlineKeyboardMarkup:
    botones = []
    fila = []
    for ficha in sorted(jugador.mano, key=_orden_mano):
        callback = f"jugar_{partida.chat_id}_{ficha[0]}_{ficha[1]}"
        fila.append(
            InlineKeyboardButton(emoji_ficha_marcada(*ficha), callback_data=callback)
        )
        if len(fila) == 3:
            botones.append(fila)
            fila = []
    fila.append(
        InlineKeyboardButton("❌ Cancelar partida", callback_data=f"cancelar_{partida.chat_id}")
    )
    botones.append(fila)
    return InlineKeyboardMarkup(botones)


def teclado_elegir_lado(partida: Partida, ficha) -> InlineKeyboardMarkup:
    a, b = ficha
    izq, der = partida.extremo_izq(), partida.extremo_der()
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(EMOJI_NUM[izq], callback_data=f"lado_{partida.chat_id}_{a}_{b}_izq"),
                InlineKeyboardButton(EMOJI_NUM[der], callback_data=f"lado_{partida.chat_id}_{a}_{b}_der"),
            ],
            [InlineKeyboardButton("↩️ Volver a mi mano", callback_data=f"volver_{partida.chat_id}")],
        ]
    )


def teclado_ir_a_mesa() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🁫 Ir a la mesa", url=f"https://t.me/{BOT_USERNAME}")]]
    )


def texto_lobby(partida: Partida) -> str:
    modo_cfg = MODOS[partida.modo]
    nombre_modo = html.escape(modo_cfg['nombre'])
    encabezado = f"<b>🁫 {nombre_modo}</b>\n\n"

    if not modo_cfg["equipos"]:
        total = len(partida.jugadores)
        cuerpo = f"{total}/{modo_cfg['max_jugadores']} jugadores en la mesa."
        if modo_cfg["min_jugadores"] < modo_cfg["max_jugadores"]:
            cuerpo += f" (mínimo {modo_cfg['min_jugadores']} para poder iniciar)"

        if partida.jugadores:
            cuerpo += "\n\n<b>Esperando:</b>\n" + "\n".join(nombre_seguro(j.nombre) for j in partida.jugadores)
        return encabezado + cuerpo + "\n"

    cupo = modo_cfg["max_jugadores"] // 2
    equipo_a = partida.jugadores_equipo("A")
    equipo_b = partida.jugadores_equipo("B")
    
    equipo_a_str = ', '.join(nombre_seguro(j.nombre) for j in equipo_a) or '—'
    equipo_b_str = ', '.join(nombre_seguro(j.nombre) for j in equipo_b) or '—'

    lineas = [
        f"🔸 <b>Equipo A</b> ({len(equipo_a)}/{cupo}): {equipo_a_str}",
        f"🔹 <b>Equipo B</b> ({len(equipo_b)}/{cupo}): {equipo_b_str}",
    ]

    for letra, equipo in (("A", equipo_a), ("B", equipo_b)):
        faltan = cupo - len(equipo)
        if faltan == 1:
            lineas.append(f"Falta 1 para el Equipo {letra}.")
        elif faltan > 1:
            lineas.append(f"Faltan {faltan} para el Equipo {letra}.")

    return encabezado + "\n".join(lineas) + "\n"


def teclado_unirse(partida: Partida) -> InlineKeyboardMarkup:
    modo_cfg = MODOS[partida.modo]
    chat_id = partida.chat_id

    if not modo_cfg["equipos"]:
        deep_link = f"https://t.me/{BOT_USERNAME}?start=join_{chat_id}"
        return InlineKeyboardMarkup([[InlineKeyboardButton("➕ Unirme", url=deep_link)]])

    cupo = modo_cfg["max_jugadores"] // 2
    n_a = len(partida.jugadores_equipo("A"))
    n_b = len(partida.jugadores_equipo("B"))

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"🔸 Unirme Equipo A ({n_a}/{cupo})",
                    url=f"https://t.me/{BOT_USERNAME}?start=join_{chat_id}_A",
                )
            ],
            [
                InlineKeyboardButton(
                    f"🔹 Unirme Equipo B ({n_b}/{cupo})",
                    url=f"https://t.me/{BOT_USERNAME}?start=join_{chat_id}_B",
                )
            ],
        ]
    )


def teclado_espera_lobby(partida: Partida) -> InlineKeyboardMarkup:
    modo_cfg = MODOS[partida.modo]
    chat_id = partida.chat_id

    botones = [
        [InlineKeyboardButton("❌ Hacer agua el juego", callback_data=f"cancelar_{chat_id}")]
    ]

    total = len(partida.jugadores)
    puede_iniciar_antes = (
        not modo_cfg["equipos"]
        and modo_cfg["min_jugadores"] < modo_cfg["max_jugadores"]
        and modo_cfg["min_jugadores"] <= total < modo_cfg["max_jugadores"]
    )
    if puede_iniciar_antes:
        botones.append(
            [
                InlineKeyboardButton(
                    f"▶️ Iniciar ya ({total}/{modo_cfg['max_jugadores']})",
                    callback_data=f"iniciar_ya_{chat_id}",
                )
            ]
        )

    return InlineKeyboardMarkup(botones)


def texto_ayuda() -> str:
    return (
        "📖 <b>Comandos y Modos</b>\n\n"
        "🎮 <b>Comandos:</b>\n"
        "• <code>/jugar_66_ind</code>\n"
        " — Doble-6 Individual para 2 o 4.\n"
        "• <code>/jugar_66_par</code>\n"
        " — Doble-6 Por Equipos 2vs2.\n"
        "• <code>/jugar_99_ind</code>\n"
        " — Doble-9 Individual para 2 o 4.\n"
        "• <code>/jugar_99_par</code>\n"
        " — Doble-9 Por Equipos 2vs2.\n\n"
        "📊 <b>Estadísticas y otros:</b>\n"
        "• <code>/top</code> — Top del grupo actual.\n"
        "• <code>/top_global</code> — Top 5 global.\n"
        "• <code>/help</code> — Menú de ayuda.\n"
        "• <code>/kill</code> — Elimina la mesa activa.\n"
        "• <code>/feedback</code> — Quejas y sugerencias\n\n"
        "ℹ️ <b>Reglas Generales:</b>\n"
        "• <b>Doble-6:</b> Set de 28 fichas, 7 por jugador, Sin robar.\n"
        "• <b>Doble-9:</b> Set de 55 fichas, 10 por jugador, Sin robar, Sobran fichas.\n"
        "• <b>Individuales:</b> Se puede jugar entre 2 o 3, pulsando todos <code>▶️ Iniciar ya</code>.\n"
        "• <b>Equipos:</b> Te unes al equipo A o B. Ganan cuando cualquiera de los dos vacía su mano o tenga menos puntos al trancar.\n"
        "• <b>Inicio y pases:</b> Sale automatico la ficha mas alta de todas las manos, los pases son automaticos se muestran en el historial.\n\n"
    )