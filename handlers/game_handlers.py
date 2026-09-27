"""
handlers/game_handlers.py — Jugar ficha, avanzar turno, cancelar, cierre
============================================================================
"""

import asyncio
import html
from typing import Optional

from telegram import InputMediaPhoto, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, TelegramError, TimedOut, RetryAfter
from telegram.ext import ContextTypes

from config import CANCEL_VOTES_NEEDED, INACTIVIDAD_TIMEOUT_SEGUNDOS, VICTORIA_PIN_SEGUNDOS, logger
from database import db_record_win, db_record_win_pareja
from domino.game import Jugador, Partida
from domino.modos import MODOS
from domino.tiles import EMOJI_NUM
from games_state import partidas
from tablero_img import dibujar_tablero
from texto_teclados import (
    caption_tablero,
    emoji_ficha_marcada,
    recortar_caption,
    teclado_elegir_lado,
    teclado_ir_a_mesa,
    teclado_mano,
)


def quitar_jobs(context: ContextTypes.DEFAULT_TYPE, nombre: str) -> None:
    if getattr(context, "job_queue", None) is None:
        return
    for job in context.job_queue.get_jobs_by_name(nombre):
        job.schedule_removal()


def programar_inactividad(context: ContextTypes.DEFAULT_TYPE, partida: Partida) -> None:
    if getattr(context, "job_queue", None) is None:
        return
    nombre = f"inactividad_{partida.chat_id}"
    quitar_jobs(context, nombre)
    context.job_queue.run_once(
        _timeout_inactividad,
        INACTIVIDAD_TIMEOUT_SEGUNDOS,
        data=partida.chat_id,
        name=nombre,
    )


async def _timeout_inactividad(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = context.job.data
    partida = partidas.get(chat_id)
    if partida is None or partida.estado != "jugando":
        return
    await _cancelar_partida(
        context, partida, texto="⌛ Partida cerrada por inactividad."
    )


async def _despinear_victoria(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id, message_id = context.job.data
    try:
        await context.bot.unpin_chat_message(chat_id=chat_id, message_id=message_id)
    except (Forbidden, BadRequest) as e:
        logger.info("No pude despinear el mensaje final del chat %s: %s", chat_id, e)


# ── Mandar y actualizar la foto del tablero ───────────────────────────


def recordar_file_id(partida: Partida, mensaje) -> None:
    if mensaje is not None and getattr(mensaje, "photo", None):
        partida.tablero_file_id = mensaje.photo[-1].file_id


async def _foto_tablero(partida: Partida):
    if partida.tablero_file_id:
        return partida.tablero_file_id
    
    return await asyncio.to_thread(dibujar_tablero, partida.tablero)


async def actualizar_mensaje(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: Optional[int],
    texto: str,
    partida: Optional[Partida] = None,
    teclado=None,
    con_tablero: bool = False,
) -> bool:
    if message_id is None:
        return False

    intentos = []
    if con_tablero and partida is not None:
        intentos += [("foto", ParseMode.HTML), ("foto", None)]
    intentos += [
        ("pie", ParseMode.HTML),
        ("pie", None),
        ("texto", ParseMode.HTML),
        ("texto", None),
    ]

    ultimo_error = None
    for tipo, parse_mode in intentos:
        try:
            if tipo == "foto":
                foto_media = await _foto_tablero(partida)
                media = InputMediaPhoto(
                    media=foto_media,
                    caption=texto,
                    parse_mode=parse_mode,
                )
                msg = await context.bot.edit_message_media(
                    chat_id=chat_id,
                    message_id=message_id,
                    media=media,
                    reply_markup=teclado,
                )
                recordar_file_id(partida, msg)
            elif tipo == "pie":
                await context.bot.edit_message_caption(
                    chat_id=chat_id,
                    message_id=message_id,
                    caption=texto,
                    parse_mode=parse_mode,
                    reply_markup=teclado,
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=texto,
                    parse_mode=parse_mode,
                    reply_markup=teclado,
                )
            return True
        except TimedOut:
            logger.warning("Timeout al editar mensaje en %s. Asumiendo éxito para no bloquear.", chat_id)
            return True
        except RetryAfter as e:
            logger.warning("Telegram pide esperar %s segs. Durmiendo...", e.retry_after)
            await asyncio.sleep(e.retry_after + 1)
            ultimo_error = e
            continue
        except BadRequest as e:
            if "not modified" in str(e).lower():
                return True
            ultimo_error = e
        except Forbidden as e:
            logger.warning("Sin permiso para editar el mensaje de %s: %s", chat_id, e)
            return False

    logger.warning("No pude actualizar el mensaje de %s: %s", chat_id, ultimo_error)
    return False


async def mandar_foto_tablero(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    partida: Partida,
    texto: str,
    teclado=None,
):
    foto_media = await _foto_tablero(partida)
    
    for parse_mode in (ParseMode.HTML, None):
        try:
            msg = await context.bot.send_photo(
                chat_id=chat_id,
                photo=foto_media,
                caption=texto,
                parse_mode=parse_mode,
                reply_markup=teclado,
            )
            recordar_file_id(partida, msg)
            return msg
        except TimedOut:
            logger.warning("Timeout al mandar foto inicial a %s.", chat_id)
            return None
        except RetryAfter as e:
            logger.warning("Flood control mandando foto: esperar %s segs.", e.retry_after)
            await asyncio.sleep(e.retry_after + 1)
            continue
        except BadRequest as e:
            if "can't parse entities" in str(e).lower() and parse_mode is not None:
                logger.warning("Pie de foto inválido, reintento sin formato: %s", e)
                continue
            logger.warning("No pude mandar la foto del tablero a %s: %s", chat_id, e)
            return None
        except Forbidden:
            logger.warning("No puedo escribirle a %s (no ha iniciado el bot).", chat_id)
            return None
    return None


async def enviar_o_actualizar_dm(
    context: ContextTypes.DEFAULT_TYPE, partida: Partida, jugador: Jugador
) -> None:
    texto = caption_tablero(partida, extra="\n\n✋ <b>Tu mano:</b>")
    teclado = teclado_mano(partida, jugador)

    if jugador.dm_message_id:
        listo = await actualizar_mensaje(
            context,
            jugador.user_id,
            jugador.dm_message_id,
            texto,
            partida=partida,
            teclado=teclado,
            con_tablero=True,
        )
        if listo:
            return
        jugador.dm_message_id = None

    msg = await mandar_foto_tablero(context, jugador.user_id, partida, texto, teclado)
    if msg:
        jugador.dm_message_id = msg.message_id


async def actualizar_tablero_grupo(
    context: ContextTypes.DEFAULT_TYPE, partida: Partida
) -> None:
    await actualizar_mensaje(
        context,
        partida.chat_id,
        partida.group_message_id,
        caption_tablero(partida),
        partida=partida,
        teclado=teclado_ir_a_mesa(),
        con_tablero=True,
    )


async def notificar_turno(context: ContextTypes.DEFAULT_TYPE, partida: Partida) -> None:
    jugador = partida.jugador_actual()
    tag_esc = html.escape(jugador.tag)

    if partida.turno_ping_message_id:
        try:
            await context.bot.delete_message(
                chat_id=partida.chat_id, message_id=partida.turno_ping_message_id
            )
        except (BadRequest, Forbidden):
            pass
        partida.turno_ping_message_id = None

    try:
        msg = await context.bot.send_message(
            chat_id=partida.chat_id,
            text=f"👉 Te toca, {tag_esc}",
            parse_mode=ParseMode.HTML,
        )
        partida.turno_ping_message_id = msg.message_id
    except BadRequest as e:
        if "can't parse entities" in str(e).lower():
            try:
                msg = await context.bot.send_message(
                    chat_id=partida.chat_id, text=f"👉 Te toca, {tag_esc}"
                )
                partida.turno_ping_message_id = msg.message_id
            except (BadRequest, Forbidden) as e2:
                logger.warning("No pude mandar el aviso de turno: %s", e2)
        else:
            logger.warning("No pude mandar el aviso de turno: %s", e)
    except Forbidden as e:
        logger.warning("No pude mandar el aviso de turno: %s", e)


async def borrar_ping_turno(context: ContextTypes.DEFAULT_TYPE, partida: Partida) -> None:
    if partida.turno_ping_message_id:
        try:
            await context.bot.delete_message(
                chat_id=partida.chat_id, message_id=partida.turno_ping_message_id
            )
        except (BadRequest, Forbidden):
            pass
        partida.turno_ping_message_id = None


async def callback_jugar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    _, chat_id_str, a_str, b_str = query.data.split("_")
    chat_id = int(chat_id_str)
    ficha = (int(a_str), int(b_str))

    partida = partidas.get(chat_id)
    if not partida or partida.estado != "jugando":
        await query.answer("Esta partida ya no está activa.", show_alert=True)
        return

    jugador = partida.jugador_actual()
    if query.from_user.id != jugador.user_id:
        await query.answer("Todavía no es tu turno.", show_alert=True)
        return

    if ficha not in jugador.mano:
        await query.answer("Ya no tienes esa ficha.", show_alert=True)
        return

    izq, der = partida.extremo_izq(), partida.extremo_der()
    if ficha[0] not in (izq, der) and ficha[1] not in (izq, der):
        await query.answer("Esa ficha no combina con ningún extremo.", show_alert=True)
        return

    if partida.es_jugada_ambigua(ficha):
        await query.answer()
        await mostrar_elegir_lado(context, partida, jugador, ficha)
        return

    await query.answer()
    await _confirmar_jugada(context, partida, jugador, ficha, lado=None)


async def mostrar_elegir_lado(
    context: ContextTypes.DEFAULT_TYPE, partida: Partida, jugador: Jugador, ficha
) -> None:
    texto = caption_tablero(
        partida,
        extra=f"\n\n🤔 Capicúa {emoji_ficha_marcada(*ficha)}. Por dónde quieres jugarla:",
    )
    await actualizar_mensaje(
        context,
        jugador.user_id,
        jugador.dm_message_id,
        texto,
        partida=partida,
        teclado=teclado_elegir_lado(partida, ficha),
    )


async def callback_elegir_lado(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    _, chat_id_str, a_str, b_str, lado = query.data.split("_")
    chat_id = int(chat_id_str)
    ficha = (int(a_str), int(b_str))

    partida = partidas.get(chat_id)
    if not partida or partida.estado != "jugando":
        await query.answer("Esta partida ya no está activa.", show_alert=True)
        return

    jugador = partida.jugador_actual()
    if query.from_user.id != jugador.user_id:
        await query.answer("Todavía no es tu turno.", show_alert=True)
        return

    if ficha not in jugador.mano:
        await query.answer("Ya no tienes esa ficha.", show_alert=True)
        return

    await query.answer()
    await _confirmar_jugada(context, partida, jugador, ficha, lado=lado)


async def callback_volver_mano(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = int(query.data.split("_", 1)[1])
    partida = partidas.get(chat_id)
    if not partida:
        await query.answer()
        return
    jugador = next((j for j in partida.jugadores if j.user_id == query.from_user.id), None)
    if not jugador:
        await query.answer()
        return
    await query.answer()
    await enviar_o_actualizar_dm(context, partida, jugador)


async def _confirmar_jugada(
    context: ContextTypes.DEFAULT_TYPE, partida: Partida, jugador: Jugador, ficha, lado: Optional[str]
) -> None:
    partida.colocar_ficha(ficha, lado=lado)
    jugador.mano.remove(ficha)
    partida.pases_seguidos = 0
    nombre_esc = html.escape(jugador.nombre)
    partida.historial = [f"⏭ {nombre_esc} jugó {emoji_ficha_marcada(*ficha)}"]

    partida.tablero_file_id = None

    if not jugador.mano:
        await _finalizar_partida(context, partida, jugador_referencia=jugador, por_dominar=True)
        return

    await _avanzar_turno(context, partida)


async def _avanzar_turno(context: ContextTypes.DEFAULT_TYPE, partida: Partida) -> None:
    partida.siguiente_turno()

    intentos = 0
    while intentos < len(partida.jugadores):
        jugador = partida.jugador_actual()
        if partida.tiene_jugada(jugador):
            break
        izq, der = partida.extremo_izq(), partida.extremo_der()
        nombre_esc = html.escape(jugador.nombre)
        partida.historial.append(
            f"⏭️ {nombre_esc} no lleva {EMOJI_NUM[izq]} {EMOJI_NUM[der]}"
        )
        partida.pases_seguidos += 1
        if partida.pases_seguidos >= len(partida.jugadores):
            ganador_bloqueo = min(partida.jugadores, key=lambda j: partida.puntos_mano(j))
            await _finalizar_partida(context, partida, jugador_referencia=ganador_bloqueo, bloqueo=True)
            return
        partida.siguiente_turno()
        intentos += 1

    await actualizar_tablero_grupo(context, partida)
    for j in partida.jugadores:
        try:
            await enviar_o_actualizar_dm(context, partida, j)
        except Forbidden:
            print("Error: El usuario bloqueó al bot.")
        except BadRequest as e:
            print(f"Error de petición de Telegram: {e}")
        except TelegramError as e:
            print(f"Error general de Telegram: {e}")

    await notificar_turno(context, partida)
    programar_inactividad(context, partida)


async def _finalizar_partida(
    context: ContextTypes.DEFAULT_TYPE,
    partida: Partida,
    jugador_referencia: Jugador,
    bloqueo: bool = False,
    por_dominar: bool = False,
) -> None:
    if bloqueo:
        motivo = "🔒 Trancao por las dos cabezas.\n¡Ganó el botagordas!"
    else:
        motivo = "¡Pegao!"

    equipos = MODOS[partida.modo]["equipos"]
    ganadores = (
        partida.jugadores_equipo(jugador_referencia.equipo) if equipos else [jugador_referencia]
    )

    partida.estado = "Se acabó"

    if equipos:
        a, b = ganadores
        db_record_win_pareja(a.user_id, a.nombre, b.user_id, b.nombre, partida.chat_id)
        n_a_esc = html.escape(a.nombre)
        n_b_esc = html.escape(b.nombre)
        nombres_ganadores = f"{n_a_esc} y {n_b_esc} (Equipo {jugador_referencia.equipo})"
    else:
        db_record_win(jugador_referencia.user_id, partida.chat_id, jugador_referencia.nombre)
        nombres_ganadores = html.escape(jugador_referencia.nombre)

    lineas_manos = []
    for j in partida.jugadores:
        n_esc = html.escape(j.nombre)
        if j.mano:
            fichas_str = " ".join(emoji_ficha_marcada(x, y) for x, y in j.mano)
            lineas_manos.append(f"<b>{n_esc}</b>\n{fichas_str}")
        else:
            lineas_manos.append(f"<b>{n_esc}</b>\n<i>(sin fichas)</i>")

    texto_final = recortar_caption(
        f"{motivo}\n\n🏆 Ganador: <b>{nombres_ganadores}</b>\n\n"
        "✋ <b>En mano:</b>\n" + "\n\n".join(lineas_manos)
    )

    cerrado = await actualizar_mensaje(
        context,
        partida.chat_id,
        partida.group_message_id,
        texto_final,
        partida=partida,
        con_tablero=True,
    )

    if cerrado:
        try:
            await context.bot.pin_chat_message(
                chat_id=partida.chat_id,
                message_id=partida.group_message_id,
                disable_notification=False,
            )
        except (Forbidden, BadRequest) as e:
            logger.info("No se pudo fijar el mensaje final en %s: %s", partida.chat_id, e)

        if getattr(context, "job_queue", None) is not None:
            context.job_queue.run_once(
                _despinear_victoria,
                VICTORIA_PIN_SEGUNDOS,
                data=(partida.chat_id, partida.group_message_id),
                name=f"unpin_{partida.chat_id}",
            )
        else:
            try:
                await context.bot.unpin_chat_message(
                    chat_id=partida.chat_id, message_id=partida.group_message_id
                )
            except (Forbidden, BadRequest) as e:
                logger.info("No se pudo despinear en %s: %s", partida.chat_id, e)

    for j in partida.jugadores:
        await actualizar_mensaje(
            context,
            j.user_id,
            j.dm_message_id,
            texto_final,
            partida=partida,
            con_tablero=True,
        )

    await borrar_ping_turno(context, partida)
    quitar_jobs(context, f"inactividad_{partida.chat_id}")
    partidas.pop(partida.chat_id, None)


async def callback_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = int(query.data.split("_", 1)[1])
    partida = partidas.get(chat_id)

    if not partida:
        await query.answer("Esta partida ya no existe.", show_alert=True)
        return

    jugador = next((j for j in partida.jugadores if j.user_id == query.from_user.id), None)
    if not jugador:
        await query.answer("No formas parte de esta partida.", show_alert=True)
        return

    jugador.voto_cancelar = True
    votos = sum(1 for j in partida.jugadores if j.voto_cancelar)
    await query.answer(f"Voto para cancelar registrado ({votos}/{CANCEL_VOTES_NEEDED}).")

    if votos >= CANCEL_VOTES_NEEDED:
        await _cancelar_partida(context, partida)


async def _cancelar_partida(
    context: ContextTypes.DEFAULT_TYPE, partida: Partida, texto: str = "🚫 Agua, repartan de nuevo."
) -> None:
    estado_previo = partida.estado
    partida.estado = "Se acabó"

    await actualizar_mensaje(
        context, partida.chat_id, partida.group_message_id, texto
    )

    if estado_previo == "jugando":
        try:
            await context.bot.unpin_chat_message(
                chat_id=partida.chat_id, message_id=partida.group_message_id
            )
        except (Forbidden, BadRequest):
            pass

    for j in partida.jugadores:
        if j.dm_message_id:
            await actualizar_mensaje(context, j.user_id, j.dm_message_id, texto)

    await borrar_ping_turno(context, partida)
    quitar_jobs(context, f"inactividad_{partida.chat_id}")
    quitar_jobs(context, f"lobby_{partida.chat_id}")
    partidas.pop(partida.chat_id, None)