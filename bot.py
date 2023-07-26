import hestia
import logging
import asyncio
import pickle
import os
from telegram import Update
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, ContextTypes
from secrets import OWN_CHAT_ID, TOKEN, PRIVILEGED_USERS
from time import sleep

def initialize():
    logging.warning("Initializing application...")

    if hestia.check_scraper_halted():
        logging.warning("Scraper is halted.")
        
    if hestia.check_dev_mode():
        logging.warning("Dev mode is enabled.")
    
def privileged(update, context, command, check_only=True):
    if update.effective_chat.id in PRIVILEGED_USERS:
        if not check_only:
            logging.warning(f"Command {command} by ID {update.effective_chat.id}: {update.message.text}")
        return True
    else:
        if not check_only:
            logging.warning(f"Unauthorized {command} attempted by ID {update.effective_chat.id}.")
        return False
        
async def get_sub_name(update, context):
    name = update.effective_chat.username
    if name is None:
        chat = await context.bot.get_chat(update.effective_chat.id)
        name = chat.first_name
    return name

async def new_sub(update, context, reenable=False):
    name = await get_sub_name(update, context)
    log_msg = f"New subscriber: {name} ({update.effective_chat.id})"
    logging.warning(log_msg)
    await context.bot.send_message(chat_id=OWN_CHAT_ID, text=log_msg)
    
    # If the user existed before, then re-enable the telegram updates
    if reenable:
        hestia.query_db(f"UPDATE hestia.subscribers SET telegram_enabled = true WHERE telegram_id = '{update.effective_chat.id}'")
    else:
        hestia.query_db(f"INSERT INTO hestia.subscribers VALUES (DEFAULT, '2099-01-01T00:00:00', DEFAULT, DEFAULT, DEFAULT, NULL, true, '{update.effective_chat.id}')")
        
    message ="""Hi there!

I scrape real estate websites for new rental homes in and around Amsterdam. For more info on which websites I scrape with which parameters, say /websites.

Please note that some real estate websites provide paid members with early access, so some of the homes I send you will be unavailable.

You are now recieving updates when I find something new! If you want me to stop, just say /stop.

If you have any issues or questions, let @WTFloris know!"""
    await context.bot.send_message(update.effective_chat.id, message)

async def start(update, context):
    checksub = hestia.query_db(f"SELECT * FROM hestia.subscribers WHERE telegram_id = '{update.effective_chat.id}'", fetchOne=True)
    
    if checksub is not None:
        if checksub["telegram_enabled"]:
            message = "You are already a subscriber, I'll let you know if I see any new rental homes online!"
            await context.bot.send_message(update.effective_chat.id, message)
        else:
            await new_sub(update, context, reenable=True)
    else:
        await new_sub(update, context)

async def stop(update, context):
    checksub = hestia.query_db(f"SELECT * FROM hestia.subscribers WHERE telegram_id = '{update.effective_chat.id}'", fetchOne=True)

    if checksub is not None:
        if checksub["telegram_enabled"]:
            # Disabling is setting telegram_enabled to false in the db
            hestia.query_db(f"UPDATE hestia.subscribers SET telegram_enabled = false WHERE telegram_id = '{update.effective_chat.id}'")
            
            name = await get_sub_name(update, context)
            log_msg = f"Removed subscriber: {name} ({update.effective_chat.id})"
            logging.warning(log_msg)
            await context.bot.send_message(chat_id=OWN_CHAT_ID, text=log_msg)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="You will no longer recieve updates for new listings."
    )

async def reply(update, context):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Sorry, I can't talk to you, I'm a just a scraper. If you want to see what commands I support, say /help. If you are lonely and want to chat, try ChatGPT."
    )

async def announce(update, context):
    if not privileged(update, context, "announce", check_only=False): return
        
    if hestia.check_dev_mode():
        subs = hestia.query_db("SELECT * FROM subscribers WHERE subscription_expiry IS NOT NULL AND telegram_enabled = true AND user_level > 1")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Dev mode is enabled, message not broadcasted to all subscribers.")
    else:
        subs = hestia.query_db("SELECT * FROM subscribers WHERE subscription_expiry IS NOT NULL AND telegram_enabled = true")

    for sub in subs:
        try:
            # If a user blocks the bot, this would throw an error and kill the entire broadcast
            await context.bot.send_message(sub, update.message.text[10:])
        except BaseException as e:
            logging.warning(f"Exception while broadcasting announcement to {sub['telegram_id']}: {repr(e)}")
            continue
            
async def websites(update, context):
    targets = hestia.query_db("SELECT user_info FROM hestia.targets WHERE enabled = true")

    message = "Here are the websites I scrape, and with which search parameters (these differ per website):\n\n"
    
    for target in targets:
        message += f"Agency: {target['user_info']['agency']}\n"
        message += f"Website: {target['user_info']['website']}\n"
        message += f"Search parameters: {target['user_info']['parameters']}\n"
        message += f"\n"
        
    await context.bot.send_message(update.effective_chat.id, message[:-1])
    sleep(1)
    
    message = "If you want more information, you can also read my source code: https://github.com/wtfloris/hestia"
    await context.bot.send_message(update.effective_chat.id, message)
    
async def get_sub_info(update, context):
    if not privileged(update, context, "get_sub_info", check_only=False): return
        
    sub = update.message.text.split(' ')[1]
    try:
        chat = await context.bot.get_chat(sub)
        message = f"Username: {chat.username}\n"
        message += f"Name: {chat.first_name} {chat.last_name}\n"
        message += f"Bio: {chat.bio}"
    except:
        logging.error(f"/getsubinfo for unknown chat id: {sub}")
        message = f"Unknown chat id."
    
    await context.bot.send_message(update.effective_chat.id, message)
    
# This writes a HALT file to stop the scraper, in case some API has changed
# and all results for a website are ending up in the bot
async def halt(update, context):
    if not privileged(update, context, "halt", check_only=False): return
    
    hestia.query_db(f"UPDATE hestia.meta SET scraper_halted = true WHERE id = '{hestia.SETTINGS_ID}'")
    
    message = "Halting scraper."
    await context.bot.send_message(update.effective_chat.id, message)
    
# Resumes the scraper by removing the HALT file. Note that this may create
# a massive update broadcast. Consider putting Hestia on dev mode first.
async def resume(update, context):
    if not privileged(update, context, "resume", check_only=False): return
    
    settings = hestia.query_db(f"SELECT scraper_halted FROM hestia.meta WHERE id = '{hestia.SETTINGS_ID}'", fetchOne=True)
    
    if settings["scraper_halted"]:
        hestia.query_db(f"UPDATE hestia.meta SET scraper_halted = false WHERE id = '{hestia.SETTINGS_ID}'")
        message = "Resuming scraper. Note that this may create a massive update within the next 5 minutes. Consider enabling /dev mode."
    else:
        message = "Scraper is not halted."
        
    await context.bot.send_message(update.effective_chat.id, message)

async def enable_dev(update, context):
    if not privileged(update, context, "dev", check_only=False): return
    
    hestia.query_db(f"UPDATE hestia.meta SET devmode_enabled = true WHERE id = '{hestia.SETTINGS_ID}'")
    
    message = "Dev mode enabled."
    await context.bot.send_message(update.effective_chat.id, message)
    
async def disable_dev(update, context):
    if not privileged(update, context, "nodev", check_only=False): return
    
    hestia.query_db(f"UPDATE hestia.meta SET devmode_enabled = false WHERE id = '{hestia.SETTINGS_ID}'")
    
    message = "Dev mode disabled."
    await context.bot.send_message(update.effective_chat.id, message)
    
# TODO implement status command with halt/dev status and amount of subscribers + homes broadcasted per agency in the last week/24h
# TODO implement /getallsubs looping over /getsubinfo

async def help(update, context):
    message = f"I can do the following for you:\n"
    message += "\n"
    message += "/help - Show this message\n"
    message += "/start - Subscribe to updates\n"
    message += "/stop - Stop recieving updates\n"
    message += "/websites - Show info about the websites I scrape"
    
    if privileged(update, context, "help", check_only=True):
        message += "\n\n"
        message += "Admin commands:\n"
        message += "/announce - Broadcast a message to all subscribers\n"
        message += "/getsubinfo <sub_id> - Get info by subscriber ID\n"
        message += "/halt - Halts the scraper\n"
        message += "/resume - Resumes the scraper\n"
        message += "/dev - Enables dev mode\n"
        message += "/nodev - Disables dev mode"

    await context.bot.send_message(update.effective_chat.id, message)

if __name__ == '__main__':
    initialize()

    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("announce", announce))
    application.add_handler(CommandHandler("websites", websites))
    application.add_handler(CommandHandler("getsubinfo", get_sub_info))
    application.add_handler(CommandHandler("halt", halt))
    application.add_handler(CommandHandler("resume", resume))
    application.add_handler(CommandHandler("dev", enable_dev))
    application.add_handler(CommandHandler("nodev", disable_dev))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), reply))
    
    application.run_polling()

