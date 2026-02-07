import re
import logging
import telegram
from time import sleep
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

import hestia_utils.db as db
import hestia_utils.meta as meta
import hestia_utils.secrets as secrets
import hestia_utils.strings as strings


def initialize():
    logging.warning("Initializing application...")

    if db.get_scraper_halted():
        logging.warning("Scraper is halted")
        
    if db.get_dev_mode():
        logging.warning("Dev mode is enabled")


def privileged(chat: telegram.Chat, msg: str, command: str, check_only: bool = True) -> bool:
    admins = db.fetch_all("SELECT * FROM hestia.subscribers WHERE user_level = 9")
    admin_chat_ids = [int(admin["telegram_id"]) for admin in admins]
    
    if chat and chat.id in admin_chat_ids:
        if not check_only:
            logging.warning(f"Command {command} by ID {chat.id}: {msg}")
        return True
    else:
        if not check_only:
            logging.warning(f"Unauthorized {command} attempted by ID {chat.id}.")
        return False


def parse_argument(text: str, key: str) -> dict:
    arg = re.search(rf"{key}=(.*?)(?:\s|$)", text)
    
    if not arg:
        return dict()
    
    start, end = arg.span()
    stripped_text = text[:start] + text[end:]
    
    value = arg.group(1)
    
    return {"text": stripped_text, "key": key, "value": value}


async def get_sub_name(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    if not update.effective_chat: return ""
    if update.effective_chat.username: return update.effective_chat.username
    return str((await context.bot.get_chat(update.effective_chat.id)).first_name)


async def new_sub(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE, reenable: bool = False) -> None:
    if not update.effective_chat: return
    name = await get_sub_name(update, context)
    logging.warning(f"New subscriber: {name} ({update.effective_chat.id})")
    
    # If the user existed before, then re-enable the telegram updates
    if reenable:
        db.enable_user(update.effective_chat.id)
    else:
        db.add_user(update.effective_chat.id)
        
    await context.bot.send_message(update.effective_chat.id, strings.get("start"))


async def start(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat: return
    checksub = db.fetch_one("SELECT * FROM hestia.subscribers WHERE telegram_id = %s", [str(update.effective_chat.id)])
    
    if checksub:
        if "telegram_enabled" in checksub and checksub["telegram_enabled"]:
            await context.bot.send_message(update.effective_chat.id, strings.get("already_subscribed", update.effective_chat.id))
        else:
            await new_sub(update, context, reenable=True)
    else:
        await new_sub(update, context)


async def stop(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat: return
    checksub = db.fetch_one("SELECT * FROM hestia.subscribers WHERE telegram_id = %s", [str(update.effective_chat.id)])

    if checksub:
        if checksub["telegram_enabled"]:
            # Disabling is setting telegram_enabled to false in the db
            db.disable_user(update.effective_chat.id)
            
            name = await get_sub_name(update, context)
            logging.warning(f"Removed subscriber: {name} ({update.effective_chat.id})")

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=strings.get("stop", update.effective_chat.id, [db.get_donation_link()]),
        parse_mode="MarkdownV2",
        disable_web_page_preview=True
    )


async def announce(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.message or not update.message.text: return
    if not privileged(update.effective_chat, update.message.text, "announce", check_only=False): return
        
    if db.get_dev_mode():
        subs = db.fetch_all("SELECT * FROM subscribers WHERE subscription_expiry IS NOT NULL AND telegram_enabled = true AND user_level > 1")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Dev mode is enabled, message not broadcasted to all subscribers")
    else:
        subs = db.fetch_all("SELECT * FROM subscribers WHERE subscription_expiry IS NOT NULL AND telegram_enabled = true")

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
        sleep(1/29)  # avoid rate limit (broadcasting to max 30 users per second)
        try:
            if markdown['value']:
                await context.bot.send_message(sub["telegram_id"], msg, parse_mode="MarkdownV2", disable_web_page_preview=bool(disablepreview['value']))
            else:
                await context.bot.send_message(sub["telegram_id"], msg, disable_web_page_preview=bool(disablepreview['value']))
        except BaseException as e:
            logging.warning(f"Exception while broadcasting announcement to {sub['telegram_id']}: {repr(e)}")
            continue


async def websites(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat: return
    targets = db.fetch_all("SELECT agency, user_info FROM hestia.targets WHERE enabled = true")

    message = strings.get("websites", update.effective_chat.id)
    
    # Some agencies have multiple targets, but that's duplicate information for the user
    already_included = []
    
    for target in targets:
        if target["agency"] in already_included:
            continue
            
        already_included.append(target["agency"])
        message += strings.get("website_info", update.effective_chat.id, [target['user_info']['agency'], target['user_info']['website']])
        
    await context.bot.send_message(update.effective_chat.id, message[:-1])
    await context.bot.send_message(update.effective_chat.id, strings.get("source_code", update.effective_chat.id))


async def halt(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.message or not update.message.text: return
    if not privileged(update.effective_chat, update.message.text, "halt", check_only=False): return
    db.halt_scraper()
    await context.bot.send_message(update.effective_chat.id, "Scraper halted")


async def resume(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.message or not update.message.text: return
    if not privileged(update.effective_chat, update.message.text, "resume", check_only=False): return
    
    if db.get_scraper_halted():
        db.resume_scraper()
        await context.bot.send_message(update.effective_chat.id, "Resuming scraper. Note that this may create a massive update within the next 5 minutes. Consider enabling /dev mode.")
    else:
        await context.bot.send_message(update.effective_chat.id, "Scraper is not halted")


async def enable_dev(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.message or not update.message.text: return
    if not privileged(update.effective_chat, update.message.text, "dev", check_only=False): return
    db.enable_dev_mode()
    await context.bot.send_message(update.effective_chat.id, "Dev mode enabled")


async def disable_dev(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.message or not update.message.text: return
    if not privileged(update.effective_chat, update.message.text, "nodev", check_only=False): return
    db.disable_dev_mode()
    await context.bot.send_message(update.effective_chat.id, "Dev mode disabled")


async def status(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.message or not update.message.text: return
    if not privileged(update.effective_chat, update.message.text, "status", check_only=False): return
    
    message = f"Running version: {meta.APP_VERSION}\n\n"
    
    if db.get_dev_mode():
        message += f"{meta.CROSS_EMOJI} Dev mode: enabled\n"
    else:
        message += f"{meta.CHECK_EMOJI} Dev mode: disabled\n"
        
    if db.get_scraper_halted():
        message += f"{meta.CROSS_EMOJI} Scraper: halted\n"
    else:
        message += f"{meta.CHECK_EMOJI} Scraper: active\n"

    active_sub_count = db.fetch_one("SELECT COUNT(*) FROM hestia.subscribers WHERE telegram_enabled = true")
    sub_count = db.fetch_one("SELECT COUNT(*) FROM hestia.subscribers")
    message += "\n"
    message += f"Active subscriber count: {active_sub_count['count']}\n"
    message += f"Total subscriber count: {sub_count['count']}\n"
    
    donation_link = db.fetch_one("SELECT donation_link, donation_link_updated FROM hestia.meta")
    message += "\n"
    message += f"Current donation link: {donation_link['donation_link']}\n"
    message += f"Last updated: {donation_link['donation_link_updated']}\n"

    targets = db.fetch_all("SELECT * FROM hestia.targets")
    message += "\n"
    message += "Targets (id): listings in past 7 days\n"
        
    for target in targets:
        agency = target["agency"]
        target_id = target["id"]
        count = db.fetch_one("SELECT COUNT(*) FROM hestia.homes WHERE agency = %s AND date_added > now() - '1 week'::interval", [agency])
        message += f"{agency} ({target_id}): {count['count']} listings\n"

    await context.bot.send_message(update.effective_chat.id, message, disable_web_page_preview=True)


async def set_donation_link(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.message or not update.message.text: return
    if not privileged(update.effective_chat, update.message.text, "setdonationlink", check_only=False): return
    
    db.update_donation_link(update.message.text.split(' ')[1])
    await context.bot.send_message(update.effective_chat.id, "Donation link updated")
    

async def filter(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.message or not update.message.text: return
    try:
        cmd = [token.lower() for token in update.message.text.split(' ')]
    except AttributeError:
        # This means the user edited a message, do nothing
        return
    
    # Fetch subscriber from database
    sub = db.fetch_one("SELECT * FROM hestia.subscribers WHERE telegram_id = %s", [str(update.effective_chat.id)])
    if not sub:
        logging.error(f"Subscriber {update.effective_chat.id} used /filter but is not in database. Msg: {update.message.text}")
        await context.bot.send_message(update.effective_chat.id, "Couldn't fetch your filter settings, please let @WTFloris know because this is unexpected")
        return
    
    # '/filter' only
    if len(cmd) == 1:

        cities_str = ""
        for c in sub["filter_cities"]:
            cities_str += f"{c.title()}, "
        
        message = strings.get("filter", update.effective_chat.id, [sub['filter_min_price'], sub['filter_max_price'], cities_str[:-2]])
        
    # Set minprice filter
    elif len(cmd) == 3 and cmd[1] in ["minprice", "min"]:
        try:
            minprice = int(cmd[2])
        except ValueError:
            await context.bot.send_message(update.effective_chat.id, strings.get("filter_invalid_number", update.effective_chat.id, [cmd[2]]))
            return
            
        db.set_filter_minprice(update.effective_chat, minprice)
        message = strings.get("filter_minprice", update.effective_chat.id, [str(minprice)])
    
    # Set maxprice filter
    elif len(cmd) == 3 and cmd[1] in ["maxprice", "max"]:
        try:
            maxprice = int(cmd[2])
        except ValueError:
            await context.bot.send_message(update.effective_chat.id, strings.get("filter_invalid_number", update.effective_chat.id, [cmd[2]]))
            return
            
        db.set_filter_maxprice(update.effective_chat, maxprice)
        message = strings.get("filter_maxprice", update.effective_chat.id, [str(maxprice)])
            
    # View city possibilities
    elif len(cmd) == 2 and cmd[1] == "city":
        all_filter_cities = [c["city"] for c in db.fetch_all("SELECT DISTINCT city FROM hestia.homes")]
        all_filter_cities.sort()
        
        message = strings.get("filter_city_header", update.effective_chat.id)
        for city in all_filter_cities:
            message += city.title() + "\n"
            if len(message) > 4000:
                await context.bot.send_message(update.effective_chat.id, message, parse_mode="Markdown")
                message = ""
            
        message += strings.get("filter_city_trailer", update.effective_chat.id)

    # Modify agency filter
    elif len(cmd) == 2 and cmd[1] in ["agency", "agencies", "website", "websites"]:
        included, reply_keyboard = [], []
        enabled_agencies = db.fetch_one("SELECT filter_agencies FROM subscribers WHERE telegram_id = %s", [str(update.effective_chat.id)])["filter_agencies"]
        for row in db.fetch_all("SELECT agency, user_info FROM hestia.targets WHERE enabled = true"):
            if row["agency"] not in included:
                included.append(row["agency"])
                if row["agency"] in enabled_agencies:
                    reply_keyboard.append([telegram.InlineKeyboardButton(meta.CHECK_EMOJI + " " + row["user_info"]["agency"], callback_data=f"hfa.d.{row['agency']}")])
                else:
                    reply_keyboard.append([telegram.InlineKeyboardButton(meta.CROSS_EMOJI + " " + row["user_info"]["agency"], callback_data=f"hfa.e.{row['agency']}")])

        await update.message.reply_text(strings.get("filter_agency", update.effective_chat.id), reply_markup=telegram.InlineKeyboardMarkup(reply_keyboard))
        return
            
    # Modify city filter
    elif len(cmd) >= 4 and cmd[1] == "city" and cmd[2] in ["add", "remove", "rm", "delete", "del"]:
        city = ""
        for token in cmd[3:]:
            # SQL injection is not possible here but you can call me paranoid that's absolutely fine
            city += token.replace(';', '').replace('"', '').replace("'", '') + ' '
        city = city[:-1]
        
        # Get cities currently in filter of subscriber
        sub_filter_cities = db.fetch_one("SELECT filter_cities FROM hestia.subscribers WHERE telegram_id = %s", [str(update.effective_chat.id)])["filter_cities"]
        
        if cmd[2] == "add":
            # Get possible cities from database
            all_filter_cities = [c["city"] for c in db.fetch_all("SELECT DISTINCT city FROM hestia.homes")]
            all_filter_cities.sort()
            
            # Check if the city is valid
            if city not in [c.lower() for c in all_filter_cities]:
                message = strings.get("filter_city_invalid", update.effective_chat.id, [city.title()])
                await context.bot.send_message(update.effective_chat.id, message, parse_mode="Markdown")
                return
                
            if city not in sub_filter_cities:
                sub_filter_cities.append(city)
            else:
                message = strings.get("filter_city_already_in", update.effective_chat.id, [city.title()])
                await context.bot.send_message(update.effective_chat.id, message)
                return

            db.set_filter_cities(update.effective_chat, sub_filter_cities)
            message = strings.get("filter_city_added", update.effective_chat.id, [city.title()])
        else:
            if city in sub_filter_cities:
                sub_filter_cities.remove(city)
            else:
                message = strings.get("filter_city_not_in", update.effective_chat.id, [city.title()])
                await context.bot.send_message(update.effective_chat.id, message)
                return

            db.set_filter_cities(update.effective_chat, sub_filter_cities)
            message = strings.get("filter_city_removed", update.effective_chat.id, [city.title()])

            if len(sub_filter_cities) == 0:
                message += strings.get("filter_city_empty", update.effective_chat.id)
    else:
        message = strings.get("filter_invalid_command", update.effective_chat.id)
        
    await context.bot.send_message(update.effective_chat.id, message, parse_mode="Markdown")


async def donate(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat: return
    donation_link = db.get_donation_link()

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=strings.get("donate", update.effective_chat.id, [donation_link]),
        parse_mode="MarkdownV2",
        disable_web_page_preview=True
    )


async def faq(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat: return
    donation_link = db.get_donation_link()
    await context.bot.send_message(update.effective_chat.id, strings.get("faq", update.effective_chat.id, [donation_link]), parse_mode="MarkdownV2", disable_web_page_preview=True)


async def set_lang_nl(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat: return
    db.set_user_lang(update.effective_chat, "nl")
    await context.bot.send_message(update.effective_chat.id, "Ik spreek vanaf nu Nederlands")


async def set_lang_en(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat: return
    db.set_user_lang(update.effective_chat, "en")
    await context.bot.send_message(update.effective_chat.id, "I'll speak English")


async def callback_query_handler(update: telegram.Update, _) -> None:
    query = update.callback_query
    if not query or not query.data or not query.message: return
    cbid, action, agency = query.data.split(".")

    # Agency filter callback
    if cbid == "hfa":
        included, reply_keyboard = [], []

        # Update list of enabled agencies for the user
        enabled_agencies: set[str] = set(db.fetch_one("SELECT filter_agencies FROM subscribers WHERE telegram_id = %s", [str(query.message.chat.id)])["filter_agencies"])
        if action == "d":
            try:
                enabled_agencies.remove(agency)
            except KeyError:
                pass
        elif action == "e":
            enabled_agencies.add(agency)
        db.set_filter_agencies(query.message.chat, enabled_agencies)

        # Build inline keyboard
        for row in db.fetch_all("SELECT agency, user_info FROM hestia.targets WHERE enabled = true"):
            if row["agency"] not in included:
                included.append(row["agency"])
                if row["agency"] in enabled_agencies:
                    reply_keyboard.append([telegram.InlineKeyboardButton(meta.CHECK_EMOJI + " " + row["user_info"]["agency"], callback_data=f"hfa.d.{row['agency']}")])
                else:
                    reply_keyboard.append([telegram.InlineKeyboardButton(meta.CROSS_EMOJI + " " + row["user_info"]["agency"], callback_data=f"hfa.e.{row['agency']}")])
        await query.answer()
        await query.edit_message_reply_markup(telegram.InlineKeyboardMarkup(reply_keyboard))


async def link(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.message or not update.message.text: return

    parts = update.message.text.split()
    if len(parts) < 2:
        await context.bot.send_message(update.effective_chat.id, strings.get("link_usage", update.effective_chat.id))
        return

    code = parts[1].strip()
    result = db.link_account(update.effective_chat.id, code)

    if result == "success":
        await context.bot.send_message(update.effective_chat.id, strings.get("link_success", update.effective_chat.id))
    elif result == "already_linked":
        await context.bot.send_message(update.effective_chat.id, strings.get("link_already_linked", update.effective_chat.id))
    else:
        await context.bot.send_message(update.effective_chat.id, strings.get("link_invalid_code", update.effective_chat.id))


async def help(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.message or not update.message.text: return
    message = strings.get("help", update.effective_chat.id)
    
    if privileged(update.effective_chat, update.message.text, "help", check_only=True):
        message += "\n\n"
        message += "*Admin commands:*\n"
        message += "/announce - Broadcast a message to all subscribers\n"
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
    application.add_handler(CommandHandler("donate", donate))
    application.add_handler(CommandHandler("filter", filter))
    application.add_handler(CommandHandler("filters", filter))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("halt", halt))
    application.add_handler(CommandHandler("resume", resume))
    application.add_handler(CommandHandler("dev", enable_dev))
    application.add_handler(CommandHandler("nodev", disable_dev))
    application.add_handler(CommandHandler("setdonate", set_donation_link))
    application.add_handler(CommandHandler("link", link))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("faq", faq))
    application.add_handler(CommandHandler("nl", set_lang_nl))
    application.add_handler(CommandHandler("en", set_lang_en))
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), help))
    application.run_polling()
