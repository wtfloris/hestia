import logging
import asyncio
import pickle
from os.path import exists
from telegram import Update
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, ContextTypes
from secrets import OWN_CHAT_ID, TOKEN, PRIVILEGED_USERS
from targets import targets
from time import sleep

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
    await context.bot.send_message(OWN_CHAT_ID, log_msg)
    
    message = "Something went wrong there, but I've let @WTFloris know! He'll let you know once he's fixed his buggy-ass code."
    await context.bot.send_message(update.effective_chat.id, message)
    
async def privileged(update, context, command):
    logging.info(f"Command {command} by ID {update.effective_chat.id}: {update.message.text}")

    if not update.effective_chat.id in PRIVILEGED_USERS:
        logging.warning(f"Unauthorized {command} attempted by ID {update.effective_chat.id}.")
        await context.bot.send_message(update.effective_chat.id, "You're not allowed to do that!")
        return 0
    return 1
    
async def new_sub(subs, update, context):
    name = update.effective_chat.username
    if name is None:
        name = await context.bot.get_chat(sub).first_name
        
    log_msg = f"New subscriber: {name} ({update.effective_chat.id})"
    logging.info(log_msg)
    await context.bot.send_message(chat_id=OWN_CHAT_ID, text=log_msg)
    
    subs.add(update.effective_chat.id)
    with open(WORKDIR + "subscribers", 'wb') as file:
        pickle.dump(subs, file)
        
    message ="""Hi there!

I scrape real estate websites for new rental homes in and around Amsterdam. For more info on which websites I scrape with which parameters, say /websites.

Please note that some real estate websites provide paid members with early access, so some of the homes I send you will be unavailable.

You are now recieving updates when I find something new! If you want me to stop, just say /stop.

If you have any issues or questions, let @WTFloris know!"""
    await context.bot.send_message(update.effective_chat.id, message)

async def start(update, context):
    subs = await load_subs(update, context)

    if subs is None:
        return 1

    if update.effective_chat.id in subs:
        message = "You are already a subscriber, I'll let you know if I see any new rental homes online!"
        await context.bot.send_message(update.effective_chat.id, message)
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
        text="Sorry, I can't talk to you, I'm a just a scraper. If you want to see what commands I support, say /help."
    )

async def announce(update, context):
    if not privileged(update, context, "announce"): return

    with open(WORKDIR + "subscribers", 'rb') as subscribers_file:
        subs = pickle.load(subscribers_file)

    for sub in subs:
        try:
            # If a user blocks the bot, this would throw an error and kill the entire broadcast
            await context.bot.send_message(sub, update.message.text[10:])
        except BaseException as e:
            logging.warning(f"Exception while broadcasting announcement to {sub}: {repr(e)}")
            continue
            
async def websites(update, context):
    message = "Here are the websites I scrape, and with which search parameters (these differ per website):\n\n"
    
    for target in targets:
        message += f"Agency: {target['info']['agency']}\n"
        message += f"Website: {target['info']['website']}\n"
        message += f"Search parameters: {target['info']['parameters']}\n"
        message += f"\n"
        
    await context.bot.send_message(update.effective_chat.id, message[:-1])
    sleep(2)
    
    message = "If you want more information, you can also read my source code: https://github.com/wtfloris/hestia"
    await context.bot.send_message(update.effective_chat.id, message)
    
async def get_sub_info(update, context):
    if not privileged(update, context, "get_sub_info"): return
        
    sub = update.message.text.split(' ')[1]
    chat = await context.bot.get_chat(sub)
    
    message = f"Username: {chat.username}\n"
    message += f"Name: {chat.first_name} {chat.last_name}\n"
    message += f"Bio: {chat.bio}"
    
    await context.bot.send_message(update.effective_chat.id, message)

async def help(update, context):
    message = f"I can do the following for you:\n"
    message += "\n"
    message += "/help - Show this message\n"
    message += "/start - Subscribe to updates\n"
    message += "/stop - Stop recieving updates\n"
    message += "/websites - Show info about which websites I scrape"
    
    await context.bot.send_message(update.effective_chat.id, message)

if __name__ == '__main__':
    initialize()

    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("announce", announce))
    application.add_handler(CommandHandler("websites", websites))
    application.add_handler(CommandHandler("getsubinfo", get_sub_info))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), reply))
    
    application.run_polling()
