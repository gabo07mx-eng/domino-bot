"""
handlers/lobby_handlers.py — Armar la mesa, antes de jugar
==============================================================
"""

import html
from telegram import Update
from telegram.ext import ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest, Forbidden, TelegramError

from config import LOBBY_TIMEOUT_SEGUNDOS, logger
from domino.game import Jugador, Partida
from domino.modos import obtener_modo
from domino.tiles import generar_fichas
from games_state import partidas
from handlers.game_handlers import (
    _finalizar_partida,
    borrar_ping_turno,
    mandar_foto_tablero,
    programar_inactividad,
    quitar_jobs,
)
from texto_teclados import (
    caption_tablero,
    nombre_seguro,
    teclado_espera_lobby,
    teclado_ir_a_mesa,
    teclado_mano,
    teclado_unirse,
    texto_ayuda,
    texto_lobby,
)


async def _enviar_dm(context, user_id: int, texto: str, teclado=None):
    try:
        return await context.bot.send_message(
            chat_id=user_id, text=texto, parse_mode="HTML", reply_markup=teclado
        )
    except Forbidden:
        print("Error: El usuario bloqueó al bot.")
    except BadRequest as e:
        print(f"Error de petición de Telegram: {e}")
    except TelegramError as e:
        print(f"Error general de Telegram: {e}")


def _parsear_payload_join(payload: str):
    partes = payload.split("_")

    if len(partes) == 2 and partes[0] == "join":
        try:
            return int(partes[1]), None
        except ValueError:
            return None

    if len(partes) == 3 and partes[0] == "join" and partes[2] in ("A", "B"):
        try:
            return int(partes[1]), partes[2]
        except ValueError:
            return None

    return None


def _armar_orden_equipos(partida: Partida) -> None:
    equipo_a = partida.jugadores_equipo("A")
    equipo_b = partida.jugadores_equipo("B")
    intercalado = []
    for a, b in zip(equipo_a, equipo_b):
        intercalado.append(a)
        intercalado.append(b)
    partida.jugadores = intercalado


async def _refrescar_espera_lobby(partida: Partida, context) -> None:
    teclado = teclado_espera_lobby(partida)
    for jugador in partida.jugadores:
        if not jugador.dm_message_id:
            continue
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=jugador.user_id,
                message_id=jugador.dm_message_id,
                reply_markup=teclado,
            )
        except Exception as e:
            logger.info(f"No se pudo refrescar el teclado de espera de {jugador.user_id}: {e}")


async def _timeout_lobby(context) -> None:
    chat_id = context.job.data
    partida = partidas.get(chat_id)
    if partida is None or partida.estado != "lobby":
        return

    partida.estado = "Se acabó"
    partidas.pop(chat_id, None)

    for jugador in partida.jugadores:
        if not jugador.dm_message_id:
            continue
        try:
            await context.bot.edit_message_text(
                chat_id=jugador.user_id,
                message_id=jugador.dm_message_id,
                text="⌛ La mesa se cerró: pasaron 15 minutos sin completarse.",
            )
        except Exception:
            pass

    try:
        await context.bot.unpin_chat_message(
            chat_id=chat_id, message_id=partida.group_message_id
        )
    except Exception:
        pass
    try:
        await context.bot.delete_message(
            chat_id=chat_id, message_id=partida.group_message_id
        )
    except Exception as e:
        logger.info(f"No se pudo borrar el lobby vencido del chat {chat_id}: {e}")


async def _arrancar_partida(partida: Partida, context) -> None:
    if partida.es_equipos:
        _armar_orden_equipos(partida)

    modo_cfg = obtener_modo(partida.modo)
    try:
        partida.iniciar(generar_fichas(modo_cfg["doble_max"]))
    except ValueError as e:
        logger.info(f"_arrancar_partida no hizo nada (chat {partida.chat_id}): {e}")
        return

    quitar_jobs(context, f"lobby_{partida.chat_id}")

    mensaje_lobby = partida.group_message_id
    nuevo = await mandar_foto_tablero(
        context,
        partida.chat_id,
        partida,
        caption_tablero(partida),
        teclado_ir_a_mesa(),
    )

    if nuevo is None:
        logger.warning(f"No se pudo mostrar el tablero en el chat {partida.chat_id}")
    else:
        partida.group_message_id = nuevo.message_id
        if mensaje_lobby:
            try:
                await context.bot.delete_message(
                    chat_id=partida.chat_id, message_id=mensaje_lobby
                )
            except Exception as e:
                logger.info(f"No se pudo borrar el mensaje del lobby: {e}")
        try:
            await context.bot.pin_chat_message(
                chat_id=partida.chat_id,
                message_id=nuevo.message_id,
                disable_notification=True,
            )
        except Exception as e:
            logger.info(f"No se pudo pinear el tablero del chat {partida.chat_id}: {e}")

    if not any(partida.tiene_jugada(j) for j in partida.jugadores):
        ganador = min(partida.jugadores, key=partida.puntos_mano)
        await _finalizar_partida(context, partida, jugador_referencia=ganador, bloqueo=True)
        return

    for jugador in partida.jugadores:
        texto = caption_tablero(partida, extra="\n\n✋ <b>Tu mano:</b>")
        enviado = await mandar_foto_tablero(
            context, jugador.user_id, partida, texto, teclado_mano(partida, jugador)
        )
        if enviado:
            jugador.dm_message_id = enviado.message_id

    jugador_en_turno = partida.jugador_actual()
    tag_esc = html.escape(jugador_en_turno.tag)
    ping = await _enviar_dm(context, jugador_en_turno.user_id, f"👉 Te toca, {tag_esc}")
    if ping:
        partida.turno_ping_message_id = ping.message_id

    programar_inactividad(context, partida)


async def cmd_jugar(update: Update, context: ContextTypes.DEFAULT_TYPE, modo: str) -> None:
    chat = update.effective_chat

    if chat.type == "private":
        await update.message.reply_text(
            "Este comando se usa dentro del grupo donde van a jugar, no aquí."
        )
        return

    existente = partidas.get(chat.id)
    if existente is not None and existente.estado in ("lobby", "jugando"):
        await update.message.reply_text(
            "Ya hay una partida en curso (o esperando jugadores) en este grupo."
        )
        return

    partida = Partida(chat_id=chat.id, modo=modo)
    partidas[chat.id] = partida

    mensaje = await update.message.reply_text(
        texto_lobby(partida), parse_mode="HTML", reply_markup=teclado_unirse(partida)
    )
    partida.group_message_id = mensaje.message_id

    try:
        await context.bot.pin_chat_message(
            chat_id=chat.id, message_id=mensaje.message_id, disable_notification=True
        )
    except Exception as e:
        logger.info(f"No se pudo pinear el lobby del chat {chat.id}: {e}")

    if getattr(context, "job_queue", None) is not None:
        context.job_queue.run_once(
            _timeout_lobby,
            LOBBY_TIMEOUT_SEGUNDOS,
            data=chat.id,
            name=f"lobby_{chat.id}",
        )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private":
        return

    if not context.args:
        await update.message.reply_text(
            "¡Hola! 🁫 Para jugar, Usa uno de los comandos para armar la mesa "
            "dentro de tu grupo, y después únete desde el botón."
        )
        return

    resultado = _parsear_payload_join(context.args[0])
    if resultado is None:
        await update.message.reply_text("Ese enlace no es válido.")
        return
    chat_id, letra = resultado

    partida = partidas.get(chat_id)
    if partida is None or partida.estado != "lobby":
        await update.message.reply_text("Esa mesa ya no existe o la partida ya arrancó.")
        return

    user = update.effective_user
    if any(j.user_id == user.id for j in partida.jugadores):
        await update.message.reply_text("Ya estás en esta mesa. 🙂")
        return

    modo_cfg = obtener_modo(partida.modo)

    if modo_cfg["equipos"]:
        if letra not in ("A", "B"):
            await update.message.reply_text("Ese enlace no indica un equipo válido.")
            return
        if partida.equipo_lleno(letra):
            await update.message.reply_text(
                f"El Equipo {letra} ya está completo — intenta con el otro "
                "desde el mensaje del grupo."
            )
            return
        nuevo = Jugador(
            user_id=user.id,
            nombre=nombre_seguro(user.first_name),
            username=user.username,
            equipo=letra,
        )
    else:
        if partida.cupo_completo():
            await update.message.reply_text("Esta mesa ya está completa.")
            return
        nuevo = Jugador(
            user_id=user.id,
            nombre=nombre_seguro(user.first_name),
            username=user.username,
        )

    partida.jugadores.append(nuevo)

    if modo_cfg["equipos"]:
        companeros = [j for j in partida.jugadores_equipo(letra) if j.user_id != user.id]
        if companeros:
            comp_esc = html.escape(companeros[0].nombre)
            extra = f" Tu compañero es {comp_esc}."
        else:
            extra = " Eres el primero de tu equipo."
        texto_confirmacion = f"¡Te uniste al Equipo {letra}!{extra}"
    else:
        nombre_modo = html.escape(modo_cfg['nombre'])
        texto_confirmacion = f"¡Te uniste a la mesa de <b>{nombre_modo}</b>!"

    enviado = await _enviar_dm(context, user.id, texto_confirmacion, teclado_espera_lobby(partida))
    if enviado:
        nuevo.dm_message_id = enviado.message_id

    try:
        await context.bot.edit_message_text(
            chat_id=partida.chat_id,
            message_id=partida.group_message_id,
            text=texto_lobby(partida),
            parse_mode="HTML",
            reply_markup=teclado_unirse(partida),
        )
    except Exception as e:
        logger.warning(f"No se pudo actualizar el lobby del chat {partida.chat_id}: {e}")

    if partida.cupo_completo():
        await _arrancar_partida(partida, context)
    elif partida.cumple_minimo():
        await _refrescar_espera_lobby(partida, context)


async def callback_iniciar_ya(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = int(query.data.removeprefix("iniciar_ya_"))

    partida = partidas.get(chat_id)
    if partida is None or partida.estado != "lobby":
        await query.answer("Esta mesa ya no está esperando en el lobby.", show_alert=True)
        return

    jugador = next((j for j in partida.jugadores if j.user_id == query.from_user.id), None)
    if jugador is None:
        await query.answer("No estás en esta mesa.", show_alert=True)
        return

    if not partida.cumple_minimo():
        await query.answer("Todavía no se llenó la mesa.", show_alert=True)
        return

    jugador.voto_iniciar = True
    await query.answer("Votaste para iniciar así mismo.")

    if partida.todos_votaron_iniciar():
        await _arrancar_partida(partida, context)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        texto_ayuda(),
        parse_mode="HTML",
    )


async def cmd_kill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text(
            "Este comando se usa dentro del grupo donde están jugando, no aquí."
        )
        return

    partida = partidas.pop(chat.id, None)
    if not partida:
        await update.message.reply_text("No hay ninguna mesa activa o esperando en este grupo.")
        return

    quitar_jobs(context, f"lobby_{chat.id}")
    quitar_jobs(context, f"inactividad_{chat.id}")

    if partida.group_message_id:
        try:
            await context.bot.unpin_chat_message(
                chat_id=chat.id, message_id=partida.group_message_id
            )
        except Exception:
            pass

    await borrar_ping_turno(context, partida)

    await update.message.reply_text(
        "🧹 <b>Mesa eliminada.</b> Pueden iniciar una nueva partida.",
        parse_mode="HTML",
    )


async def cmd_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    teclado = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "---", 
                    url="https://t.me/PartidoComunistadeCuba" 
                )
            ]
        ]
    )
    
    await update.message.reply_text(
        "⁉️ Las quejas al",
        reply_markup=teclado
    )