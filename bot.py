"""
bot.py — Arranque del bot (registro de comandos y handlers)
==============================================================
"""

import functools
import pytz

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    Defaults,
)

from config import BOT_TOKEN, logger
from database import db_init
from domino.modos import MODOS
from handlers.game_handlers import (
    callback_cancelar,
    callback_elegir_lado,
    callback_jugar,
    callback_volver_mano,
)
from handlers.leaderboard_handlers import cmd_top, cmd_top_global, cmd_top_parejas
from handlers.lobby_handlers import (
    callback_iniciar_ya,
    cmd_help,
    cmd_jugar,
    cmd_kill,
    cmd_feedback,
    cmd_start,
)


def main() -> None:
    db_init()

    # Asignación correcta de la zona horaria para el JobQueue en PTB v20+
    defaults = Defaults(tzinfo=pytz.UTC)
    
    # Se aumentan los tiempos de espera a 30 segundos para evitar errores de Timeout
    # al subir imágenes generadas en máquinas de bajo rendimiento.
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .pool_timeout(30)
        .defaults(defaults)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("top", cmd_top))
    app.add_handler(CommandHandler("top_parejas", cmd_top_parejas))
    app.add_handler(CommandHandler("top_global", cmd_top_global))
    app.add_handler(CommandHandler(["help"], cmd_help))
    app.add_handler(CommandHandler(["feedback"], cmd_feedback))
    app.add_handler(CommandHandler(["kill"], cmd_kill))

    for clave, cfg in MODOS.items():
        app.add_handler(
            CommandHandler(cfg["comando"], functools.partial(cmd_jugar, modo=clave))
        )

    app.add_handler(CallbackQueryHandler(callback_jugar, pattern=r"^jugar_"))
    app.add_handler(CallbackQueryHandler(callback_elegir_lado, pattern=r"^lado_"))
    app.add_handler(CallbackQueryHandler(callback_volver_mano, pattern=r"^volver_"))
    app.add_handler(CallbackQueryHandler(callback_cancelar, pattern=r"^cancelar_"))
    app.add_handler(CallbackQueryHandler(callback_iniciar_ya, pattern=r"^iniciar_ya_"))

    logger.info("Bot arrancando (polling)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()