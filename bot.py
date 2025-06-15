import hestia
import logging
import secrets
import re
import telegram
from datetime import datetime
from telegram.error import BadRequest
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from time import sleep


def initialize():
    logging.warning("Initializing application...")

    if hestia.check_scraper_halted():
        logging.warning("Scraper is halted.")
        
    if hestia.check_dev_mode():
        logging.warning("Dev mode is enabled.")


def privileged(update: telegram.Update, command: str, check_only: bool = True) -> bool:
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


def parse_argument(text: str, key: str) -> dict:
    arg = re.search(f"{key}=(.*?)(?:\s|$)", text)
    
    if not arg:
        return dict()
    
    start, end = arg.span()
    stripped_text = text[:start] + text[end:]
    
    value = arg.group(1)
    
    return {"text": stripped_text, "key": key, "value": value}


async def get_sub_name(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    name = update.effective_chat.username
    if name is None:
        chat = await context.bot.get_chat(update.effective_chat.id)
        name = chat.first_name
    return name


async def new_sub(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE, reenable: bool = False) -> None:
    name = await get_sub_name(update, context)
    log_msg = f"New subscriber: {name} ({update.effective_chat.id})"
    logging.warning(log_msg)
    
    # If the user existed before, then re-enable the telegram updates
    if reenable:
        hestia.query_db("UPDATE hestia.subscribers SET telegram_enabled = true WHERE telegram_id = %s", params=[str(update.effective_chat.id)])
    else:
        hestia.query_db("INSERT INTO hestia.subscribers VALUES (DEFAULT, '2099-01-01T00:00:00', DEFAULT, DEFAULT, DEFAULT, DEFAULT, true, %s)", params=[str(update.effective_chat.id)])
        
    message ="""Hi there!

I check real estate websites for new rental homes in The Netherlands. For more info on which websites I check, say /websites.

To see and modify your personal filters (like city and maximum price), say /filter.

You will receive a message when I find a new home that matches your filters! If you want me to stop, just say /stop.

If you have any questions, please read the /faq!"""
    await context.bot.send_message(update.effective_chat.id, message)


async def start(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    checksub = hestia.query_db("SELECT * FROM hestia.subscribers WHERE telegram_id = %s", params=[str(update.effective_chat.id)], fetchOne=True)
    
    if checksub is not None:
        if checksub["telegram_enabled"]:
            message = "You are already a subscriber, I'll let you know if I see any new rental homes online!"
            await context.bot.send_message(update.effective_chat.id, message)
        else:
            await new_sub(update, context, reenable=True)
    else:
        await new_sub(update, context)


async def stop(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    checksub = hestia.query_db("SELECT * FROM hestia.subscribers WHERE telegram_id = %s", params=[str(update.effective_chat.id)], fetchOne=True)

    if checksub is not None:
        if checksub["telegram_enabled"]:
            # Disabling is setting telegram_enabled to false in the db
            hestia.query_db("UPDATE hestia.subscribers SET telegram_enabled = false WHERE telegram_id = %s", params=[str(update.effective_chat.id)])
            
            name = await get_sub_name(update, context)
            log_msg = f"Removed subscriber: {name} ({update.effective_chat.id})"
            logging.warning(log_msg)

    donation_link = hestia.query_db("SELECT donation_link FROM hestia.meta", fetchOne=True)["donation_link"]

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"""You will no longer recieve updates for new listings\. I hope this is because you've found a new home\!
        
Consider [buying me a beer]({donation_link}) if Hestia has helped you in your search {hestia.LOVE_EMOJI}""",
        parse_mode="MarkdownV2",
        disable_web_page_preview=True
    )


async def announce(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not privileged(update, "announce", check_only=False): return
        
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


async def get_sub_info(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not privileged(update, "get_sub_info", check_only=False): return
        
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


async def halt(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not privileged(update, "halt", check_only=False): return
    
    hestia.query_db("UPDATE hestia.meta SET scraper_halted = true WHERE id = %s", params=[hestia.SETTINGS_ID])
    
    message = "Halting scraper."
    await context.bot.send_message(update.effective_chat.id, message)


async def resume(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not privileged(update, "resume", check_only=False): return
    
    settings = hestia.query_db("SELECT scraper_halted FROM hestia.meta WHERE id = %s", params=[hestia.SETTINGS_ID], fetchOne=True)
    
    if settings["scraper_halted"]:
        hestia.query_db("UPDATE hestia.meta SET scraper_halted = false WHERE id = %s", params=[hestia.SETTINGS_ID])
        message = "Resuming scraper. Note that this may create a massive update within the next 5 minutes. Consider enabling /dev mode."
    else:
        message = "Scraper is not halted."
        
    await context.bot.send_message(update.effective_chat.id, message)


async def enable_dev(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not privileged(update, "dev", check_only=False): return
    
    hestia.query_db("UPDATE hestia.meta SET devmode_enabled = true WHERE id = %s", params=[hestia.SETTINGS_ID])
    
    message = "Dev mode enabled."
    await context.bot.send_message(update.effective_chat.id, message)


async def disable_dev(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not privileged(update, "nodev", check_only=False): return
    
    hestia.query_db("UPDATE hestia.meta SET devmode_enabled = false WHERE id = %s", params=[hestia.SETTINGS_ID])
    
    message = "Dev mode disabled."
    await context.bot.send_message(update.effective_chat.id, message)


async def get_all_subs(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not privileged(update, "get_all_subs", check_only=False): return
    
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


async def status(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not privileged(update, "status", check_only=False): return

    settings = hestia.query_db("SELECT * FROM hestia.meta WHERE id = %s", params=[hestia.SETTINGS_ID], fetchOne=True)
    
    message = f"Running version: {hestia.APP_VERSION}\n\n"
    
    if settings["devmode_enabled"]:
        message += f"{hestia.CROSS_EMOJI} Dev mode: enabled\n"
    else:
        message += f"{hestia.CHECK_EMOJI} Dev mode: disabled\n"
        
    if settings["scraper_halted"]:
        message += f"{hestia.CROSS_EMOJI} Scraper: halted\n"
    else:
        message += f"{hestia.CHECK_EMOJI} Scraper: active\n"

    active_sub_count = hestia.query_db("SELECT COUNT(*) FROM hestia.subscribers WHERE telegram_enabled = true", fetchOne=True)
    sub_count = hestia.query_db("SELECT COUNT(*) FROM hestia.subscribers", fetchOne=True)
    message += "\n"
    message += f"Active subscriber count: {active_sub_count['count']}\n"
    message += f"Total subscriber count: {sub_count['count']}\n"
    
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


async def set_donation_link(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not privileged(update, "setdonationlink", check_only=False): return
    
    link = update.message.text.split(' ')[1]
    
    hestia.query_db("UPDATE hestia.meta SET donation_link = %s, donation_link_updated = %s WHERE id = %s", params=[link, datetime.now().isoformat(), hestia.SETTINGS_ID])
    
    message = "Donation link updated."
    await context.bot.send_message(update.effective_chat.id, message)
    

# TODO check if user is in db (and enabled)
# TODO some restrictions on numeric filters: min, max etc
async def filter(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        cmd = [token.lower() for token in update.message.text.split(' ')]
    except AttributeError:
        # This means the user edited a message, do nothing
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
            if len(message) > 4000:
                await context.bot.send_message(update.effective_chat.id, message, parse_mode="Markdown")
                message = ""
            
        message += "\nThis list is based on the cities I've seen so far while scraping, so it might not be fully complete."

    # Modify agency filter
    elif len(cmd) == 2 and cmd[1] in ["agency", "agencies", "website", "websites"]:
        included, reply_keyboard = [], []
        enabled_agencies = hestia.query_db("SELECT filter_agencies FROM subscribers WHERE telegram_id = %s", params=[str(update.effective_chat.id)], fetchOne=True)["filter_agencies"]
        for row in hestia.query_db("SELECT agency, user_info FROM hestia.targets WHERE enabled = true"):
            if row["agency"] not in included:
                included.append(row["agency"])
                if row["agency"] in enabled_agencies:
                    reply_keyboard.append([telegram.InlineKeyboardButton(hestia.CHECK_EMOJI + " " + row["user_info"]["agency"], callback_data=f"hfa.d.{row['agency']}")])
                else:
                    reply_keyboard.append([telegram.InlineKeyboardButton(hestia.CROSS_EMOJI + " " + row["user_info"]["agency"], callback_data=f"hfa.e.{row['agency']}")])

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


async def settemplate(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /settemplate command to save user's response template"""
    try:
        # Get full message text after command
        template_text = ' '.join(context.args).strip()
        
        if not template_text:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Please provide a template text! Example:\n/settemplate Hi, I'm interested in [[address]]"
            )
            return

        # Save to database
        hestia.query_db(
            "UPDATE hestia.subscribers SET response_template = %s WHERE telegram_id = %s",
            (template_text, str(update.effective_chat.id))
        )
        
        # Show preview with sample address
        preview = template_text.replace("[[address]]", "SampleStraat 123")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Template saved! Preview:\n\n{preview}"
        )
        
    except Exception as e:
        logging.error(f"Error in settemplate: {str(e)}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Failed to save template. Please try again later."
        )


async def donate(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    donation_link = hestia.get_donation_link()

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"""Moving is expensive enough and similar services start at like €20/month\. Hopefully Hestia has helped you save some money\!
        
You could use some of those savings to [buy me a beer]({donation_link}) {hestia.LOVE_EMOJI}

Good luck in your search\!""",
        parse_mode="MarkdownV2",
        disable_web_page_preview=True
    )


async def faq(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    donation_link = hestia.get_donation_link()
    message = f"""*Why is Hestia free?*
    I built Hestia for myself and once we found a home, I thought it would be nice to share it with others\!

*What websites does Hestia check?*
    Use the command /websites to see the full list\.

*How often does Hestia check the websites?*
    Every 5 minutes\.

*Can you add website \.\.\.?*
    Probably, please check [this issue](https://github.com/wtfloris/hestia/issues/53) on GitHub to see if it's already on the list\.

*Can you add a filter for: amount of rooms/square m2/postal code, etc\.?*
    In short: no, because it makes Hestia more less reliable\. Please see [this issue](https://github.com/wtfloris/hestia/issues/55#issuecomment-2453400778) for the full explanation \(and feel free to discuss if you don\'t agree\)\!

*Does this work if I want to buy a home?*
    Not yet, but who knows what I might build when I\'m looking to buy something myself\!

*I saw this listing on Pararius and I didn\'t get a message from Hestia\. Why?*
    Pararius does not list a house number for all homes, so Hestia can\'t check if it\'s already seen the listing on another website\. To avoid duplicates, we skip these listings altogether\.

*Can I use this without Telegram?*
    No\. Telegram provides an easy interface for programming, this is much harder on WhatsApp\.

*Can I thank you for building and sharing Hestia for free?*
    Yes of course, you can buy me a beer [here]({donation_link})\! {hestia.LOVE_EMOJI}

*Can I contact you?*
    Yes, I'm @WTFloris on Telegram or e\-mail me at hestia@wtflor\.is\!"""
    
    await context.bot.send_message(update.effective_chat.id, message, parse_mode="MarkdownV2", disable_web_page_preview=True)


async def callback_query_handler(update: telegram.Update, _) -> None:
    query = update.callback_query
    cbid, action, agency = query.data.split(".")

    # Agency filter callback
    if cbid == "hfa":
        included, reply_keyboard = [], []

        # Update list of enabled agencies for the user
        enabled_agencies = set(hestia.query_db("SELECT filter_agencies FROM subscribers WHERE telegram_id = %s", params=[str(query.message.chat.id)], fetchOne=True)["filter_agencies"])
        if action == "d":
            try:
                enabled_agencies.remove(agency)
            except KeyError:
                pass
        elif action == "e":
            enabled_agencies.add(agency)
        hestia.query_db("UPDATE hestia.subscribers SET filter_agencies = %s WHERE telegram_id = %s", params=(str(list(enabled_agencies)).replace("'", '"'), str(query.message.chat.id)))

        # Build inline keyboard
        for row in hestia.query_db("SELECT agency, user_info FROM hestia.targets WHERE enabled = true"):
            if row["agency"] not in included:
                included.append(row["agency"])
                if row["agency"] in enabled_agencies:
                    reply_keyboard.append([telegram.InlineKeyboardButton(hestia.CHECK_EMOJI + " " + row["user_info"]["agency"], callback_data=f"hfa.d.{row['agency']}")])
                else:
                    reply_keyboard.append([telegram.InlineKeyboardButton(hestia.CROSS_EMOJI + " " + row["user_info"]["agency"], callback_data=f"hfa.e.{row['agency']}")])
        await query.answer()
        await query.edit_message_reply_markup(telegram.InlineKeyboardMarkup(reply_keyboard))


async def help(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    message = "*I can do the following for you:*\n"
    message += "/help - Show this message\n"
    message += "/settemplate - Set auto-response template (use [[address]] placeholder)\n"
    message += "/faq - Show the frequently asked questions (and answers!)\n"
    message += "/start - Subscribe to updates\n"
    message += "/stop - Stop recieving updates\n\n"
    message += "/filter - Show and modify your personal filters\n"
    message += "/websites - Show info about the websites I scrape\n"
    message += "/donate - Get an open Tikkie link to show your appreciation for Hestia\n"
    
    if privileged(update, "help", check_only=True):
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
    application.add_handler(CommandHandler("donate", donate))
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
    application.add_handler(CommandHandler("settemplate", settemplate))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("faq", faq))
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), help))
    application.run_polling()
