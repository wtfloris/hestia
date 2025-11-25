# This script is put on a separate server and run when the server hosting Hestia is down for maintenance
from telegram import Update
from datetime import datetime
from telegram.ext import filters, MessageHandler, ApplicationBuilder, ContextTypes

TOKEN = ''


async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg =  f"Hestia is currently down for maintenance, please try again in a few hours!\n\nMaintenance started at {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)


if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(MessageHandler(filters.ALL, reply))
    application.run_polling()