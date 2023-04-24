import logging
import asyncio
import pickle
from os.path import exists
from telegram import Update
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, ContextTypes
from secrets import OWN_CHAT_ID, TOKEN

WORKDIR = "/data/"

logging.basicConfig(
    format="%(asctime)s [%(levelname)s]: %(message)s",
    level=logging.INFO,
    filename=WORKDIR + "hestia.log"
)

def initialize():
    if not exists(WORKDIR + "subscribers"):
        logging.info("Initializing new subscribers database file...")
        with open(WORKDIR + "subscribers", 'wb') as file:
            pickle.dump(set([OWN_CHAT_ID]), file)

async def load_subs(update, context):
    try:
        with open(WORKDIR + "subscribers", 'rb') as file:
            return pickle.load(file)
    except BaseException as e:
        await transmit_error(e, update, context)
        return None

async def transmit_error(e, update, context):
    log_msg = f'''Error loading file for subscriber: {update.effective_chat.username} ({update.effective_chat.id})
{repr(e)}'''
    logging.error(log_msg)
    await context.bot.send_message(chat_id=OWN_CHAT_ID, text=log_msg)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Something went wrong there, but I've let @WTFloris know! He'll let you know once he's fixed his buggy-ass code."
    )
    return 1

async def new_sub(subs, update, context):
    log_msg = f"New subscriber: {update.effective_chat.username} ({update.effective_chat.id})"
    logging.info(log_msg)
    await context.bot.send_message(chat_id=OWN_CHAT_ID, text=log_msg)
    subs.add(update.effective_chat.id)
    with open(WORKDIR + "subscribers", 'wb') as file:
        pickle.dump(subs, file)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="""Hi there!

I scrape real estate websites for new rental homes in and around Amsterdam. Any new listings with a monthly rent between €900 and €1500 will be automatically sent in this chat.
            
You are now recieving updates when I find something new! If you want me to stop, just say /stop.

If you have any issues or questions, let @WTFloris know!"""
    )

async def start(update, context):
    subs = await load_subs(update, context)

    if subs is None:
        return 1

    if update.effective_chat.id in subs:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="You are already a subscriber, I'll let you know if I see any new rental homes online!"
        )
    else:
        await new_sub(subs, update, context)
        

async def stop(update, context):
    subs = await load_subs(update, context)

    if subs is None:
        return 1

    if update.effective_chat.id in subs:
        subs.remove(update.effective_chat.id)
        with open(WORKDIR + "subscribers", 'wb') as file:
            pickle.dump(subs, file)
        logging.info(f"Removed subscriber: {update.effective_chat.username} ({update.effective_chat.id})")

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="You will no longer recieve updates for new listings."
    )

async def reply(update, context):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Sorry, I can't talk to you, I'm a just a scraper. If you want to stop updates, reply with /stop."
    )

async def announce(update, context):
    logging.info(f"Incoming announcement by {update.effective_chat.username} ({update.effective_chat.id}): {update.message.text}")

    if update.effective_chat.id != OWN_CHAT_ID:
        logging.warning(f"Unauthorized announcement by {update.effective_chat.username} ({update.effective_chat.id}).")
        await context.bot.send_message(text="You are not allowed to do that!", chat_id=update.effective_chat.id)
        return

    with open(WORKDIR + "subscribers", 'rb') as subscribers_file:
        subs = pickle.load(subscribers_file)

    for sub in subs:
        try:
            # If a user blocks the bot, this would throw an error and kill the entire broadcast
            await context.bot.send_message(text=update.message.text[10:], chat_id=sub)
        except BaseException as e:
            logging.warning(f"Exception while broadcasting announcement to {sub}: {repr(e)}")
            continue

if __name__ == '__main__':
    initialize()

    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("announce", announce))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), reply))
    
    application.run_polling()
