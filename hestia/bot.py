import re
import logging
import telegram
from time import sleep
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

import hestia_utils.db as db
import hestia_utils.meta as meta
import hestia_utils.secrets as secrets


def initialize():
    logging.warning("Initializing application...")

    if db.get_scraper_halted():
        logging.warning("Scraper is halted.")
        
    if db.get_dev_mode():
        logging.warning("Dev mode is enabled.")


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
        
    message ="""Hi there!

I check real estate websites for new rental homes in The Netherlands. For more info on which websites I check, say /websites.

To see and modify your personal filters (like city and maximum price), say /filter.

You will receive a message when I find a new home that matches your filters! If you want me to stop, just say /stop.

If you have any questions, please read the /faq!"""
    await context.bot.send_message(update.effective_chat.id, message)


async def start(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat: return
    checksub = db.fetch_one("SELECT * FROM hestia.subscribers WHERE telegram_id = %s", params=[str(update.effective_chat.id)])
    
    if checksub is not None:
        if checksub["telegram_enabled"]:
            message = "You are already a subscriber, I'll let you know if I see any new rental homes online!"
            await context.bot.send_message(update.effective_chat.id, message)
        else:
            await new_sub(update, context, reenable=True)
    else:
        await new_sub(update, context)


async def stop(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat: return
    checksub = db.fetch_one("SELECT * FROM hestia.subscribers WHERE telegram_id = %s", params=[str(update.effective_chat.id)])

    if checksub is not None:
        if checksub["telegram_enabled"]:
            # Disabling is setting telegram_enabled to false in the db
            db.disable_user(update.effective_chat.id)
            
            name = await get_sub_name(update, context)
            logging.warning(f"Removed subscriber: {name} ({update.effective_chat.id})")

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=rf"""You will no longer recieve updates for new listings\. I hope this is because you've found a new home\!
        
Consider [buying me a beer]({db.get_donation_link()}) if Hestia has helped you in your search {meta.LOVE_EMOJI}""",
        parse_mode="MarkdownV2",
        disable_web_page_preview=True
    )


async def announce(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.message or not update.message.text: return
    if not privileged(update.effective_chat, update.message.text, "announce", check_only=False): return
        
    if db.get_dev_mode():
        subs = db.fetch_all("SELECT * FROM subscribers WHERE subscription_expiry IS NOT NULL AND telegram_enabled = true AND user_level > 1")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Dev mode is enabled, message not broadcasted to all subscribers.")
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
        await context.bot.send_message(update.effective_chat.id, "Scraper is not halted.")


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
    sub = db.fetch_one("SELECT * FROM hestia.subscribers WHERE telegram_id = %s", params=[str(update.effective_chat.id)])
    if not sub:
        logging.error(f"Subscriber {update.effective_chat.id} used /filter but is not in database. Msg: {update.message.text}")
        await context.bot.send_message(update.effective_chat.id, "Couldn't fetch your filter settings, please let @WTFloris know because this is unexpected")
        return
    
    # '/filter' only
    if len(cmd) == 1:

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
        message += "`/filter city remove Den Haag`\n"
        message += "I will only send you homes in cities that you've included in your filter. Say  `/filter city`  to see the list of possible cities.\n\n"
        message += "Additionally, you can disable updates from certain agencies/websites. Say  `/filter agency`  to select your preference."
        
    # Set minprice filter
    elif len(cmd) == 3 and cmd[1] in ["minprice", "min"]:
        try:
            minprice = int(cmd[2])
        except ValueError:
            message = f"Invalid value: {cmd[2]} is not a number."
            await context.bot.send_message(update.effective_chat.id, message)
            return
            
        db.set_filter_minprice(minprice, update.effective_chat.id)
        message = f"Minimum price filter set to {minprice}!"
    
    # Set maxprice filter
    elif len(cmd) == 3 and cmd[1] in ["maxprice", "max"]:
        try:
            maxprice = int(cmd[2])
        except ValueError:
            message = f"Invalid value: {cmd[2]} is not a number."
            await context.bot.send_message(update.effective_chat.id, message)
            return
            
        db.set_filter_maxprice(maxprice, update.effective_chat.id)
        message = f"Maximum price filter set to {maxprice}!"
            
    # View city possibilities
    elif len(cmd) == 2 and cmd[1] == "city":
        all_filter_cities = [c["city"] for c in db.fetch_all("SELECT DISTINCT city FROM hestia.homes")]
        all_filter_cities.sort()
        
        message = "Supported cities for the city filter are:\n\n"
        for city in all_filter_cities:
            message += f"{city.title()}\n"
            if len(message) > 4000:
                await context.bot.send_message(update.effective_chat.id, message, parse_mode="Markdown")
                message = ""
            
        message += "\nThis list is based on the cities I've seen so far while scraping, so it might not be fully complete."

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

        await update.message.reply_text("Select the agencies you want to receive updates from", reply_markup=telegram.InlineKeyboardMarkup(reply_keyboard))
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
        
            db.set_filter_cities(update.effective_chat.id, sub_filter_cities)
            message = f"{city.title()} added to your city filter."
        
        else:
            if city in sub_filter_cities:
                sub_filter_cities.remove(city)
            else:
                message = f"{city.title()} is not in your filter, so nothing has been changed."
                await context.bot.send_message(update.effective_chat.id, message)
                return
                
            db.set_filter_cities(update.effective_chat.id, sub_filter_cities)
            message = f"{city.title()} removed from your city filter."
            
            if len(sub_filter_cities) == 0:
                message += "\n\nYour city filter is now empty, you will not receive messages about any homes."
    else:
        message = "Invalid filter command, say /filter to see options."
        
    await context.bot.send_message(update.effective_chat.id, message, parse_mode="Markdown")


async def donate(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat: return
    donation_link = db.get_donation_link()

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=rf"""Moving is expensive enough and similar services start at like €20/month\. Hopefully Hestia has helped you save some money\!
        
You could use some of those savings to [buy me a beer]({donation_link}) {meta.LOVE_EMOJI}

Good luck in your search\!""",
        parse_mode="MarkdownV2",
        disable_web_page_preview=True
    )


async def faq(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat: return
    donation_link = db.get_donation_link()
    message = rf"""*Why is Hestia free?*
    I built Hestia for myself and once we found a home, I thought it would be nice to share it with others\!

*What websites does Hestia check?*
    Use the command /websites to see the full list\.

*How often does Hestia check the websites?*
    Every 5 minutes\.

*Can you add website \.\.\.?*
    Probably, please check [this issue](https://github.com/wtfloris/hestia/issues/53) on GitHub to see if it's already on the list\.

*Can you add a filter for: amount of rooms/square m2/postal code, etc\.?*
    In short: no, because it makes Hestia less reliable\. Please see [this comment](https://github.com/wtfloris/hestia/issues/55#issuecomment-2453400778) for the full explanation \(and feel free to discuss if you don\'t agree\)\!

*Does this work if I want to buy a home?*
    Not yet, but who knows what I might build when I\'m looking to buy something myself\!

*I saw this listing on Pararius and I didn\'t get a message from Hestia\. Why?*
    Pararius does not list a house number for all homes, so Hestia can\'t check if it\'s already seen the listing on another website\. To avoid duplicates, we skip these listings altogether\.

*Can I use this without Telegram?*
    No\. Telegram provides an easy interface for programming, this is much harder on WhatsApp\.

*Can I thank you for building and sharing Hestia for free?*
    Yes of course, you can buy me a beer [here]({donation_link})\! {meta.LOVE_EMOJI}

*Can I contact you?*
    Yes, I'm @WTFloris on Telegram or e\-mail me at hestia@wtflor\.is\!"""
    
    await context.bot.send_message(update.effective_chat.id, message, parse_mode="MarkdownV2", disable_web_page_preview=True)


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
        db.set_filter_agencies(query.message.chat.id, enabled_agencies)

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


async def help(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.message or not update.message.text: return
    message = "*I can do the following for you:*\n"
    message += "/help - Show this message\n"
    message += "/faq - Show the frequently asked questions (and answers!)\n"
    message += "/start - Subscribe to updates\n"
    message += "/stop - Stop recieving updates\n\n"
    message += "/filter - Show and modify your personal filters\n"
    message += "/websites - Show info about the websites I scrape\n"
    message += "/donate - Get an open Tikkie link to show your appreciation for Hestia\n"
    
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
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("faq", faq))
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), help))
    application.run_polling()
