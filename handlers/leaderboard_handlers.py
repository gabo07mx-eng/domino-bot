"""
handlers/leaderboard_handlers.py — Leaderboard (/top, /top_parejas, /top_global)
================================================================================
"""

import html
from telegram import Update
from telegram.ext import ContextTypes

from database import (
    db_top_chat,
    db_top_global,
    db_top_global_parejas,
    db_top_chat_parejas,
)


async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("Este comando se usa dentro de un grupo.")
        return

    top = db_top_chat(chat.id, limit=10)
    if not top:
        await update.message.reply_text("🏆 <b>Tabla de Posiciones</b>\n\nAún no hay victorias registradas en este grupo.", parse_mode="HTML")
        return

    lineas = ["🏆 <b>Tabla de Posiciones (Individual)</b>\n"]
    for i, (nombre, wins) in enumerate(top, start=1):
        nombre_esc = html.escape(nombre)
        lineas.append(f"{i}. {nombre_esc} — {wins} 🏅")

    await update.message.reply_text("\n".join(lineas), parse_mode="HTML")


async def cmd_top_parejas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("Este comando se usa dentro de un grupo.")
        return

    top = db_top_chat_parejas(chat.id, limit=10)
    if not top:
        await update.message.reply_text("🏆 <b>Tabla de Posiciones (Parejas)</b>\n\nAún no hay victorias de parejas en este grupo.", parse_mode="HTML")
        return

    lineas = ["🏆 <b>Tabla de Posiciones (Parejas)</b>\n"]
    for i, (p1, p2, wins) in enumerate(top, start=1):
        p1_esc = html.escape(p1)
        p2_esc = html.escape(p2)
        lineas.append(f"{i}. {p1_esc} y {p2_esc} — {wins} 🎖")

    await update.message.reply_text("\n".join(lineas), parse_mode="HTML")


async def cmd_top_global(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    top_ind = db_top_global(limit=5)
    top_parejas = db_top_global_parejas(limit=5)

    if not top_ind and not top_parejas:
        await update.message.reply_text("🌍 <b>Top Global</b>\n\nAún no hay victorias registradas.", parse_mode="HTML")
        return

    texto = "🌍 <b>Top Global</b>\n\n"

    texto += "👤 <b>Top 5 Individual:</b>\n"
    if top_ind:
        for i, (nombre, wins) in enumerate(top_ind, start=1):
            nombre_esc = html.escape(nombre)
            texto += f"{i}. {nombre_esc} — {wins} 🏅\n"
    else:
        texto += "<i>(sin registros)</i>\n"

    texto += "\n👥 <b>Top 5 Parejas:</b>\n"
    if top_parejas:
        for i, (p1, p2, wins) in enumerate(top_parejas, start=1):
            p1_esc = html.escape(p1)
            p2_esc = html.escape(p2)
            texto += f"{i}. {p1_esc} y {p2_esc} — {wins} 🎖\n"
    else:
        texto += "<i>(sin registros)</i>\n"

    await update.message.reply_text(texto, parse_mode="HTML")