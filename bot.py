import hestia
import logging
import asyncio
import pickle
import os
import secrets
import re
from datetime import datetime
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, ContextTypes
from time import sleep

def initialize():
    logging.warning("Initializing application...")

    if hestia.check_scraper_halted():
        logging.warning("Scraper is halted.")
        
    if hestia.check_dev_mode():
        logging.warning("Dev mode is enabled.")
    
def privileged(update, context, command, check_only=True):
    admins = hestia.query_db("SELECT * FROM hestia.subscribers WHERE user_level = 9")
    admin_chat_ids = [int(admin["telegram_id"]) for admin in admins]
    
    if update.effective_chat.id in admin_chat_ids:
        if not check_only:
            logging.warning(f"Command {command} by ID {update.effective_chat.id}: {update.message.text}")
        return True
    else:
        if not check_only:
            logging.warning(f"Unauthorized {command} attempted by ID {update.effective_chat.id}.")
        return False
        
def parse_argument(text, key) -> dict:
    arg = re.search(f"{key}=(.*?)(?:\s|$)", text)
    
    if not arg:
        return dict()
    
    start, end = arg.span()
    stripped_text = text[:start] + text[end:]
    
    value = arg.group(1)
    
    return {"text": stripped_text, "key": key, "value": value}
        
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
    await context.bot.send_message(chat_id=secrets.OWN_CHAT_ID, text=log_msg)
    
    # If the user existed before, then re-enable the telegram updates
    if reenable:
        hestia.query_db("UPDATE hestia.subscribers SET telegram_enabled = true WHERE telegram_id = %s", params=[str(update.effective_chat.id)])
    else:
        hestia.query_db("INSERT INTO hestia.subscribers VALUES (DEFAULT, '2099-01-01T00:00:00', DEFAULT, DEFAULT, DEFAULT, DEFAULT, true, %s)", params=[str(update.effective_chat.id)])
        
    message ="""Hi there!

I scrape real estate websites for new rental homes in The Netherlands. For more info on which websites I scrape, say /websites. To see and modify your personal filters, say /filter.

Please note that some real estate websites provide their paid members with early access, so some of the homes I send you will be unavailable.

You will receive a message when I find a new home that matches your filters! If you want me to stop, just say /stop.

If you have any issues or questions, let @WTFloris know!"""
    await context.bot.send_message(update.effective_chat.id, message)

async def start(update, context):
    checksub = hestia.query_db("SELECT * FROM hestia.subscribers WHERE telegram_id = %s", params=[str(update.effective_chat.id)], fetchOne=True)
    
    if checksub is not None:
        if checksub["telegram_enabled"]:
            message = "You are already a subscriber, I'll let you know if I see any new rental homes online!"
            await context.bot.send_message(update.effective_chat.id, message)
        else:
            await new_sub(update, context, reenable=True)
    else:
        await new_sub(update, context)

async def stop(update, context):
    checksub = hestia.query_db("SELECT * FROM hestia.subscribers WHERE telegram_id = %s", params=[str(update.effective_chat.id)], fetchOne=True)

    if checksub is not None:
        if checksub["telegram_enabled"]:
            # Disabling is setting telegram_enabled to false in the db
            hestia.query_db("UPDATE hestia.subscribers SET telegram_enabled = false WHERE telegram_id = %s", params=[str(update.effective_chat.id)])
            
            name = await get_sub_name(update, context)
            log_msg = f"Removed subscriber: {name} ({update.effective_chat.id})"
            logging.warning(log_msg)
            await context.bot.send_message(chat_id=secrets.OWN_CHAT_ID, text=log_msg)

    donation_link = hestia.query_db("SELECT donation_link FROM hestia.meta", fetchOne=True)["donation_link"]

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"""You will no longer recieve updates for new listings\. I hope this is because you've found a new home\!
        
Consider [buying me a beer]({donation_link}) if this bot has helped you in your search {hestia.LOVE_EMOJI}""",
        parse_mode="MarkdownV2",
        disable_web_page_preview=True
    )

async def reply(update, context):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Sorry, I can't talk to you, I'm just a scraper. If you want to see what commands I support, say /help. If you are lonely and want to chat, try ChatGPT."
    )

async def announce(update, context):
    if not privileged(update, context, "announce", check_only=False): return
        
    if hestia.check_dev_mode():
        subs = hestia.query_db("SELECT * FROM subscribers WHERE subscription_expiry IS NOT NULL AND telegram_enabled = true AND user_level > 1")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Dev mode is enabled, message not broadcasted to all subscribers.")
    else:
        subs = hestia.query_db("SELECT * FROM subscribers WHERE subscription_expiry IS NOT NULL AND telegram_enabled = true")

    # Remove /announce
    msg = update.message.text[10:]
    
    # Parse arguments
    markdown = parse_argument(msg, "Markdown")
    if markdown:
        msg = markdown['text']
    else:
        markdown['value'] = False
        
    disablepreview = parse_argument(msg, "DisableLinkPreview")
    if disablepreview:
        msg = disablepreview['text']
    else:
        disablepreview['value'] = False

    for sub in subs:
        try:
            if markdown['value']:
                await context.bot.send_message(sub["telegram_id"], msg, parse_mode="MarkdownV2", disable_web_page_preview=disablepreview['value'])
            else:
                await context.bot.send_message(sub["telegram_id"], msg, disable_web_page_preview=disablepreview['value'])
        except BaseException as e:
            logging.warning(f"Exception while broadcasting announcement to {sub['telegram_id']}: {repr(e)}")
            continue
            
async def websites(update, context):
    targets = hestia.query_db("SELECT agency, user_info FROM hestia.targets WHERE enabled = true")

    message = "Here are the websites I scrape every five minutes:\n\n"
    
    # Some agencies have multiple targets, but that's duplicate information for the user
    already_included = []
    
    for target in targets:
        if target["agency"] in already_included:
            continue
            
        already_included.append(target["agency"])
        
        message += f"Agency: {target['user_info']['agency']}\n"
        message += f"Website: {target['user_info']['website']}\n"
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
    
async def halt(update, context):
    if not privileged(update, context, "halt", check_only=False): return
    
    hestia.query_db("UPDATE hestia.meta SET scraper_halted = true WHERE id = %s", params=[hestia.SETTINGS_ID])
    
    message = "Halting scraper."
    await context.bot.send_message(update.effective_chat.id, message)
    
async def resume(update, context):
    if not privileged(update, context, "resume", check_only=False): return
    
    settings = hestia.query_db("SELECT scraper_halted FROM hestia.meta WHERE id = %s", params=[hestia.SETTINGS_ID], fetchOne=True)
    
    if settings["scraper_halted"]:
        hestia.query_db("UPDATE hestia.meta SET scraper_halted = false WHERE id = %s", params=[hestia.SETTINGS_ID])
        message = "Resuming scraper. Note that this may create a massive update within the next 5 minutes. Consider enabling /dev mode."
    else:
        message = "Scraper is not halted."
        
    await context.bot.send_message(update.effective_chat.id, message)

async def enable_dev(update, context):
    if not privileged(update, context, "dev", check_only=False): return
    
    hestia.query_db("UPDATE hestia.meta SET devmode_enabled = true WHERE id = %s", params=[hestia.SETTINGS_ID])
    
    message = "Dev mode enabled."
    await context.bot.send_message(update.effective_chat.id, message)
    
async def disable_dev(update, context):
    if not privileged(update, context, "nodev", check_only=False): return
    
    hestia.query_db("UPDATE hestia.meta SET devmode_enabled = false WHERE id = %s", params=[hestia.SETTINGS_ID])
    
    message = "Dev mode disabled."
    await context.bot.send_message(update.effective_chat.id, message)
    
async def get_all_subs(update, context):
    if not privileged(update, context, "get_all_subs", check_only=False): return
    
    subs = hestia.query_db("SELECT * FROM subscribers WHERE subscription_expiry IS NOT NULL AND telegram_enabled = true")
    
    message = "Current active subscribers:\n\n"
    for sub in subs:
        try:
            chat = await context.bot.get_chat(sub["telegram_id"])
        except BadRequest:
            # This means a user in the db has blocked the bot without unsubscribing
            continue
        message += f"{sub['telegram_id']} {chat.username} ({chat.first_name} {chat.last_name})\n"
    
    await context.bot.send_message(update.effective_chat.id, message)
    
async def status(update, context):
    if not privileged(update, context, "status", check_only=False): return

    settings = hestia.query_db("SELECT * FROM hestia.meta WHERE id = %s", params=[hestia.SETTINGS_ID], fetchOne=True)
    
    message = "Status:\n\n"
    
    if settings["devmode_enabled"]:
        message += "Dev mode: enabled\n"
    else:
        message += "Dev mode: disabled\n"
        
    if settings["scraper_halted"]:
        message += "Scraper: halted\n"
    else:
        message += "Scraper: active\n"

    sub_count = hestia.query_db("SELECT COUNT(*) FROM hestia.subscribers WHERE telegram_enabled = true", fetchOne=True)
    message += "\n"
    message += f"Active subscriber count: {sub_count['count']}\n"
    
    donation_link = hestia.query_db("SELECT donation_link, donation_link_updated FROM hestia.meta", fetchOne=True)
    message += "\n"
    message += f"Current donation link: {donation_link['donation_link']}\n"
    message += f"Last updated: {donation_link['donation_link_updated']}\n"

    targets = hestia.query_db("SELECT * FROM hestia.targets")
    message += "\n"
    message += "Targets (id): listings in past 7 days\n"
        
    for target in targets:
        agency = target["agency"]
        target_id = target["id"]
        count = hestia.query_db("SELECT COUNT(*) FROM hestia.homes WHERE agency = %s AND date_added > now() - '1 week'::interval", params=[agency], fetchOne=True)
        message += f"{agency} ({target_id}): {count['count']} listings\n"

    await context.bot.send_message(update.effective_chat.id, message, disable_web_page_preview=True)
    
async def set_donation_link(update, context):
    if not privileged(update, context, "setdonationlink", check_only=False): return
    
    link = update.message.text.split(' ')[1]
    
    hestia.query_db("UPDATE hestia.meta SET donation_link = %s, donation_link_updated = %s WHERE id = %s", params=[link, datetime.now().isoformat(), hestia.SETTINGS_ID])
    
    message = "Donation link updated."
    await context.bot.send_message(update.effective_chat.id, message)
    
# TODO check if user is in db (and enabled)
# TODO some restrictions on numeric filters: min, max etc
async def filter(update, context):
    # Not sure why, but sometimes an error occurs here because the message is empty.
    try:
        cmd = [token.lower() for token in update.message.text.split(' ')]
    except AttributeError:
        message = "Something went wrong here, but the creator of the bot can't reproduce it. If you see this message, can you please let @WTFloris know what you were trying to do? Thank you!"
        await context.bot.send_message(update.effective_chat.id, message)
        return
    
    # '/filter' only
    if len(cmd) == 1:
        sub = hestia.query_db("SELECT * FROM hestia.subscribers WHERE telegram_id = %s", params=[str(update.effective_chat.id)], fetchOne=True)
        
        cities_str = ""
        for c in sub["filter_cities"]:
            cities_str += f"{c.title()}, "
        
        message = "*Currently, your filters are:*\n"
        message += f"Min. price: {sub['filter_min_price']}\n"
        message += f"Max. price: {sub['filter_max_price']}\n"
        message += f"Cities: {cities_str[:-2]}\n\n"
        message += "*To change your filters, you can say:*\n"
        message += "`/filter minprice 1200`\n"
        message += "`/filter maxprice 1800`\n"
        message += "`/filter city add Amsterdam`\n"
        message += "`/filter city remove Den Haag`\n\n"
        message += "I will only send you homes in cities that you've included in your filter. Say  `/filter city`  to see the list of possible cities."
        
    # Set minprice filter
    elif len(cmd) == 3 and cmd[1] in ["minprice", "min"]:
        try:
            minprice = int(cmd[2])
        except ValueError:
            message = f"Invalid value: {cmd[2]} is not a number."
            await context.bot.send_message(update.effective_chat.id, message)
            return
            
        hestia.query_db("UPDATE subscribers SET filter_min_price = %s WHERE telegram_id = %s", params=(minprice, str(update.effective_chat.id)))
        
        message = f"Minimum price filter set to {minprice}!"
    
    # Set maxprice filter
    elif len(cmd) == 3 and cmd[1] in ["maxprice", "max"]:
        try:
            maxprice = int(cmd[2])
        except ValueError:
            message = f"Invalid value: {cmd[2]} is not a number."
            await context.bot.send_message(update.effective_chat.id, message)
            return
            
        hestia.query_db("UPDATE subscribers SET filter_max_price = %s WHERE telegram_id = %s", params=(maxprice, str(update.effective_chat.id)))
        
        message = f"Maximum price filter set to {maxprice}!"
            
    # View city possibilities
    elif len(cmd) == 2 and cmd[1] == "city":
        all_filter_cities = [c["city"] for c in hestia.query_db("SELECT DISTINCT city FROM hestia.homes")]
        all_filter_cities.sort()
        
        message = "Supported cities for the city filter are:\n\n"
        for city in all_filter_cities:
            message += f"{city.title()}\n"
            
        message += "\nThis list is based on the cities I've seen so far while scraping, so it might not be fully complete."
            
    # Modify city filter
    elif len(cmd) >= 4 and cmd[1] == "city" and cmd[2] in ["add", "remove", "rm", "delete", "del"]:
        city = ""
        for token in cmd[3:]:
            # SQL injection is not possible here but you can call me paranoid that's absolutely fine
            city += token.replace(';', '').replace('"', '').replace("'", '') + ' '
        city = city[:-1]
        
        # Get cities currently in filter of subscriber
        sub_filter_cities = hestia.query_db("SELECT filter_cities FROM hestia.subscribers WHERE telegram_id = %s", params=[str(update.effective_chat.id)], fetchOne=True)["filter_cities"]
        
        if cmd[2] == "add":
            # Get possible cities from database
            all_filter_cities = [c["city"] for c in hestia.query_db("SELECT DISTINCT city FROM hestia.homes")]
            all_filter_cities.sort()
            
            # Check if the city is valid
            if city not in [c.lower() for c in all_filter_cities]:
                message = f"Invalid city: {city}\n\n"
                message += "To see possible cities, say: `/filter city`"
                await context.bot.send_message(update.effective_chat.id, message, parse_mode="Markdown")
                return
                
            if city not in sub_filter_cities:
                sub_filter_cities.append(city)
            else:
                message = f"{city.title()} is already in your filter, so nothing has been changed."
                await context.bot.send_message(update.effective_chat.id, message)
                return
        
            hestia.query_db("UPDATE hestia.subscribers SET filter_cities = %s WHERE telegram_id = %s", params=(str(sub_filter_cities).replace("'", '"'), str(update.effective_chat.id)))
            message = f"{city.title()} added to your city filter."
        
        else:
            if city in sub_filter_cities:
                sub_filter_cities.remove(city)
            else:
                message = f"{city.title()} is not in your filter, so nothing has been changed."
                await context.bot.send_message(update.effective_chat.id, message)
                return
                
            hestia.query_db("UPDATE hestia.subscribers SET filter_cities = %s WHERE telegram_id = %s", params=(str(sub_filter_cities).replace("'", '"'), str(update.effective_chat.id)))
            message = f"{city.title()} removed from your city filter."
            
            if len(sub_filter_cities) == 0:
                message += "\n\nYour city filter is now empty, you will not receive messages about any homes."
    else:
        message = "Invalid filter command, say /filter to see options."
        
    await context.bot.send_message(update.effective_chat.id, message, parse_mode="Markdown")

async def help(update, context):
    message = "*I can do the following for you:*\n"
    message += "/help - Show this message\n"
    message += "/start - Subscribe to updates\n"
    message += "/stop - Stop recieving updates\n\n"
    message += "/filter - Show and modify your personal filters\n"
    message += "/websites - Show info about the websites I scrape"
    
    if privileged(update, context, "help", check_only=True):
        message += "\n\n"
        message += "*Admin commands:*\n"
        message += "/announce - Broadcast a message to all subscribers\n"
        message += "/getallsubs - Get all subscriber info\n"
        message += "/getsubinfo <id> - Get info by Telegram chat ID\n"
        message += "/status - Get system status\n"
        message += "/halt - Halts the scraper\n"
        message += "/resume - Resumes the scraper\n"
        message += "/dev - Enables dev mode\n"
        message += "/nodev - Disables dev mode\n"
        message += "/setdonate - Sets the goodbye message donation link"

    await context.bot.send_message(update.effective_chat.id, message, parse_mode="Markdown")

if __name__ == '__main__':
    initialize()

    application = ApplicationBuilder().token(secrets.TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("announce", announce))
    application.add_handler(CommandHandler("websites", websites))
    application.add_handler(CommandHandler("filter", filter))
    application.add_handler(CommandHandler("filters", filter))
    application.add_handler(CommandHandler("getsubinfo", get_sub_info))
    application.add_handler(CommandHandler("getallsubs", get_all_subs))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("halt", halt))
    application.add_handler(CommandHandler("resume", resume))
    application.add_handler(CommandHandler("dev", enable_dev))
    application.add_handler(CommandHandler("nodev", disable_dev))
    application.add_handler(CommandHandler("setdonate", set_donation_link))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), reply))
    
    application.run_polling()
