/* ---- Theme and lang initialization (must run before render) ---- */
(function() {
    var t = localStorage.getItem('hestia-theme');
    if (t === 'light' || t === 'dark') {
        document.documentElement.setAttribute('data-theme', t);
        return;
    }
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        document.documentElement.setAttribute('data-theme', 'dark');
        return;
    }
    document.documentElement.setAttribute('data-theme', 'light');
})();
(function() {
    var stored = localStorage.getItem('hestia-lang');
    var preferred = (navigator.languages && navigator.languages.length)
        ? navigator.languages[0]
        : (navigator.language || 'en');
    var resolved = stored || (preferred.toLowerCase().startsWith('nl') ? 'nl' : 'en');
    document.documentElement.setAttribute('lang', resolved);
})();

function toggleTheme() {
    var current = document.documentElement.getAttribute('data-theme');
    var next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('hestia-theme', next);
    updateThemeIcon();
}
function updateThemeIcon() {
    var icon = document.querySelector('.theme-icon');
    if (!icon) return;
    var name = document.documentElement.getAttribute('data-theme') === 'dark' ? 'sun' : 'moon';
    icon.innerHTML = '<i data-lucide="' + name + '" style="width:18px;height:18px"></i>';
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
}

/* ---- HTML escaping utility ---- */
function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/* ---- i18n framework ---- */
var HESTIA_I18N = {
    en: {
        'welcome_title': 'Welcome to Hestia',
        'welcome_subtitle': 'Enter your e-mail address to continue',
        'login_sent_title': "You've got mail",
        'login_sent_subtitle': 'I just sent a login link to',
        'login_sent_help': "Didn't get it? Check your spam folder or try again in a minute.",
        'continue_aria': 'Continue',
        'dashboard_title': 'Your Hestia',
        'homes_empty': 'No homes match your current filters. Try adjusting your settings.',
        'homes_limit_reached': "There may be more results, but Hestia can\u2019t look back this far.",
        'homes_end_reached': 'You\u2019ve seen everything!',
        'logged_in_as': 'Logged in as',
        'logout_confirm': 'Log out of Hestia?',
        'settings_title': 'Settings and filters',
        'restore_btn': 'Restore',
        'save_btn': 'Save',
        'notifications_legend': 'Notifications',
        'telegram_label': 'Telegram',
        'price_range_legend': 'Price range',
        'price_range_info': 'Hestia will only send you homes within this range.',
        'price_min_label': 'Minimum',
        'price_max_label': 'Maximum',
        'price_suffix': '/mo',
        'price_warning': 'Minimum is higher than maximum',
        'agencies_legend': 'Agencies/websites',
        'agencies_info': "Only search for homes from these agencies/websites.<br><br>Something missing? It\'s possible that the integration with a website is broken. The website will be temporarily unavailable until a fix can be deployed.",
        'agencies_search': 'Search agencies\u2026',
        'cities_legend': 'Cities',
        'cities_info': 'Only search for homes in these cities.<br><br>City missing? These are all cities Hestia has found homes in. Newly found cities will be added automatically.',
        'cities_search': 'Search cities\u2026',
        'add_city_placeholder': 'Add city\u2026',
        'saving_label': 'Saving\u2026',
        'saving_error': "Couldn\u2019t save changes. Click to try again.",
        'saving_error_tap': "Couldn\u2019t save changes. Tap to try again.",
        'cost_link': 'Hestia is free, but costs \u20ac68/month to run',
        'cost_modal_title': 'Running costs',
        'cost_hosting': 'Hosting (main + backup)',
        'cost_email': 'E-mail API',
        'cost_domain': 'Domain name (hestia.bot)',
        'cost_claude': 'Claude Pro (yes, the entire web portal is vibe-coded)',
        'cost_coffee': 'Caffeinated beverages (to support a 6-hour coding bender on a random Friday night because I also have a full-time job)',
        'cost_total': 'Total',
        'cost_donate_text': "Hestia is a passion project and will always be free. Similar services will cost you at least \u20ac20/month.<br>If you'd like to help keep Hestia running, consider",
        'cost_donate_link': 'making a donation with this open Tikkie',
        'contact_email': 'E-mail:',
        'contact_email_login_required': 'E-mail: only visible after logging in',
        'contact_telegram': 'Telegram (the guy who made this):',
        'contact_github': 'GitHub (source code):',
        'contact_avatar_credit': 'Hestia artwork courtesy of ',
        'faq_q_what': 'What is Hestia?',
        'faq_a_what': 'Hestia is a home-finding service that monitors websites and notifies you about new matches within your filters.',
        'faq_q_free': 'Hestia is free?',
        'faq_a_free': 'Yes. I built Hestia for myself and once we found a home, I thought it would be nice to share it with others!',
        'faq_q_speed': 'How quick is Hestia?',
        'faq_a_speed': 'Notifications should arrive within 10 minutes.',
        'faq_q_filters': 'Can you add a filter for amount of rooms, square meters, or postal code?',
        'faq_a_filters': 'In short: no, because it makes Hestia less reliable. Please see <a href="https://github.com/wtfloris/hestia/issues/55#issuecomment-2453400778" target="_blank" rel="noopener noreferrer">this comment</a> for the full explanation, and feel free to discuss if you disagree!',
        'faq_q_buy': 'Does this work if I want to buy a home?',
        'faq_a_buy': 'Not yet, but who knows what I might build when I am looking to buy something myself!',
        'faq_q_pararius': 'I saw this listing on Pararius and I did not get a message from Hestia. Why?',
        'faq_a_pararius': 'Pararius does not list a house number for all homes, so Hestia cannot check if it has already seen the listing on another website. To avoid duplicates, those listings are skipped.',
        'faq_q_thanks': 'Can I thank you for building and sharing Hestia for free?',
        'faq_a_thanks': 'Yes! Click the euro icon below the settings panel. Thanks!',
        'link_telegram_modal_title': 'Link your Telegram account',
        'link_telegram_modal_text': 'Be notified of new results without your browser open!',
        'link_open_telegram': 'Open Telegram',
        'link_manual_alt': 'Or send this manually:',
        'link_to': 'to',
        'link_code_expired': 'Code expired',
        'link_code_regenerate': 'Generate new code',
        'link_telegram_btn': 'Connect',
        'stats_modal_title': 'Statistics',
        'stats_loading': 'Loading\u2026',
        'stats_total_homes': 'Homes found',
        'stats_homes_today': 'Homes found today',
        'stats_total_subscribers': 'Users',
        'stats_subscribers_this_month': 'New users this month',
        'stats_top_cities': 'Amount of homes by city',
        'stats_error': "Uh oh, couldn't load statistics",
        'homes_live_updating': 'Searching for new homes\u2026',
        'homes_live_lost': 'Connection lost. Click to refresh.',
        'homes_live_lost_tap': 'Connection lost. Tap to refresh.',
        'browser_notif_label': 'This browser',
        'browser_notif_denied': 'Notifications blocked by browser',
        'browser_notif_new_one': '1 new home has been found',
        'browser_notif_new_many': '{count} new homes have been found',
        'browser_notif_ios_info': "Browser notifications are not available due to iOS restrictions (but I'm working on an iOS app!). For now, you can use a desktop browser to get immediate notifications.",
        'experimental_warning': 'Hestia is still a work in progress \u2014 you may experience some instability here and there!'
    },
    nl: {
        'welcome_title': 'Welkom bij Hestia',
        'welcome_subtitle': 'Voer je e-mailadres in om verder te gaan',
        'login_sent_title': 'Je hebt mail',
        'login_sent_subtitle': 'Ik heb net een inloglink gestuurd naar',
        'login_sent_help': 'Nog niets ontvangen? Check je spam of probeer het over een minuutje opnieuw!',
        'continue_aria': 'Ga door',
        'dashboard_title': 'Jouw Hestia',
        'homes_empty': 'Geen woningen gevonden met deze filters. Pas je instellingen aan.',
        'homes_limit_reached': 'Er zijn mogelijk meer resultaten, maar Hestia kan niet zo ver terug kijken.',
        'homes_end_reached': 'Je hebt alles gezien!',
        'logged_in_as': 'Ingelogd als',
        'logout_confirm': 'Weet je zeker dat je wilt uitloggen?',
        'settings_title': 'Instellingen en filters',
        'restore_btn': 'Herstel',
        'save_btn': 'Opslaan',
        'notifications_legend': 'Meldingen',
        'telegram_label': 'Telegram',
        'price_range_legend': 'Prijsbereik',
        'price_range_info': 'Zoek alleen woningen met een maandhuur binnen dit bereik.',
        'price_min_label': 'Minimum',
        'price_max_label': 'Maximum',
        'price_suffix': '/mnd',
        'price_warning': 'Minimum is hoger dan maximum',
        'agencies_legend': 'Makelaars/websites',
        'agencies_info': 'Zoek alleen woningen van deze makelaars/websites.<br><br>Ontbreekt er eentje? Het kan zijn dat de integratie met een website stuk is. De website is dan tijdelijk niet beschikbaar tot het probleem is opgelost.',
        'agencies_search': 'Zoek makelaars\u2026',
        'cities_legend': 'Plaatsen',
        'cities_info': 'Zoek alleen woningen in deze plaatsen.<br><br>Ontbreekt er eentje? Dit zijn alle plaatsen die Hestia tot nu toe online heeft gezien. Nieuwe plaatsen worden automatisch toegevoegd.',
        'cities_search': 'Zoek plaatsen\u2026',
        'add_city_placeholder': 'Voeg plaats toe\u2026',
        'saving_label': 'Opslaan\u2026',
        'saving_error': 'Opslaan mislukt. Klik om opnieuw te proberen.',
        'saving_error_tap': 'Opslaan mislukt. Tik om opnieuw te proberen.',
        'cost_link': 'Hestia is gratis, maar kost \u20ac68/maand om draaiende te houden',
        'cost_modal_title': 'Kostenoverzicht',
        'cost_hosting': 'Hosting (main + backup)',
        'cost_email': 'E-mail API',
        'cost_domain': 'Domeinnaam (hestia.bot)',
        'cost_claude': 'Claude Pro (ja, bespaart een hoop tijd)',
        'cost_coffee': 'Cafe\u00efnehoudende dranken (om een 6-uur durende programmeersessie op een willekeurige vrijdagavond te faciliteren omdat ik ook gewoon een fulltime baan heb)',
        'cost_total': 'Totaal',
        'cost_donate_text': 'Hestia is een "passieproject" en zal altijd gratis blijven. Vergelijkbare diensten kosten minimaal \u20ac20/maand.<br>Wil je helpen Hestia online te houden, dan kun je',
        'cost_donate_link': 'met dit open Tikkie daaraan bijdragen',
        'contact_email': 'E-mail:',
        'contact_email_login_required': 'E-mail: alleen zichtbaar na inloggen',
        'contact_telegram': 'Telegram (van de chef):',
        'contact_github': 'GitHub (source code):',
        'contact_avatar_credit': 'Hestia artwork met dank aan ',
        'faq_q_what': 'Wat is Hestia?',
        'faq_a_what': 'Hestia is een woningzoeker die advertenties in de gaten houdt en je meldingen stuurt als er nieuwe woningen binnen jouw filters gevonden zijn.',
        'faq_q_free': 'Is Hestia gratis?',
        'faq_a_free': 'Ja! Ik had Hestia voor gebouwd mezelf en toen we een huis hadden gevonden heb ik het online gegooid en is het doorgegroeid.',
        'faq_q_speed': 'Hoe snel is Hestia?',
        'faq_a_speed': 'Meldingen zouden binnen 10 minuten moeten doorkomen.',
        'faq_q_filters': 'Kun je een filter toevoegen voor aantal kamers, vierkante meters of postcode?',
        'faq_a_filters': 'Kort gezegd: nee, omdat dit Hestia minder betrouwbaar maakt. Zie <a href="https://github.com/wtfloris/hestia/issues/55#issuecomment-2453400778" target="_blank" rel="noopener noreferrer">deze uitleg</a> voor de volledige motivatie, en reageer gerust als je het er niet mee eens bent!',
        'faq_q_buy': 'Werkt dit ook als ik een huis wil kopen?',
        'faq_a_buy': 'Nog niet, maar wie weet wat ik bouw wanneer we zelf iets willen kopen!',
        'faq_q_pararius': 'Ik zag een woning op Pararius en kreeg geen melding van Hestia. Waarom?',
        'faq_a_pararius': 'Pararius vermeldt niet bij alle woningen een huisnummer, waardoor Hestia niet kan controleren of de woning al op een andere website is gezien. Om dubbele meldingen te voorkomen slaan we die over.',
        'faq_q_thanks': 'Kan ik je bedanken voor het bouwen en delen van Hestia?',
        'faq_a_thanks': 'Zeker! Klik op het euro-icoon onder het instellingenpaneel. Thanks!',
        'link_telegram_modal_title': 'Koppel je Telegram-account',
        'link_telegram_modal_text': 'Ontvang notificaties zonder deze pagina open te houden!',
        'link_open_telegram': 'Open Telegram',
        'link_manual_alt': 'Of stuur dit handmatig:',
        'link_to': 'naar',
        'link_code_expired': 'Code verlopen',
        'link_code_regenerate': 'Genereer een nieuwe code',
        'link_telegram_btn': 'Koppel',
        'stats_modal_title': 'Statistieken',
        'stats_loading': 'Laden\u2026',
        'stats_total_homes': 'Woningen gevonden',
        'stats_homes_today': 'Nieuwe woningen (vandaag)',
        'stats_total_subscribers': 'Gebruikers',
        'stats_subscribers_this_month': 'Nieuwe gebruikers (deze maand)',
        'stats_top_cities': 'Aantal woningen per plaats',
        'stats_error': 'Oeps, statistieken konden niet worden geladen...',
        'homes_live_updating': 'Op zoek naar nieuwe woningen\u2026',
        'homes_live_lost': 'Verbinding verbroken. Klik om te verversen.',
        'homes_live_lost_tap': 'Verbinding verbroken. Tik om te verversen.',
        'browser_notif_label': 'Deze browser',
        'browser_notif_denied': 'Meldingen geblokkeerd door browser',
        'browser_notif_new_one': '1 nieuwe woning gevonden',
        'browser_notif_new_many': '{count} nieuwe woningen gevonden',
        'browser_notif_ios_info': 'Notificaties in de browser werken niet door beperkingen binnen iOS (maar er wordt aan een iOS app gewerkt!). Gebruik voorlopig een laptop of desktop voor browsernotificaties.',
        'experimental_warning': 'Hestia is nog volop in ontwikkeling \u2014 het kan zijn dat er soms iets stuk gaat!'
    }
};
function hestiaGetLang() {
    return localStorage.getItem('hestia-lang') || document.documentElement.getAttribute('lang') || 'en';
}
function hestiaApplyLang(lang) {
    var dict = HESTIA_I18N[lang] || {};
    localStorage.setItem('hestia-lang', lang);
    document.querySelectorAll('[data-i18n]').forEach(function(el) {
        var key = el.getAttribute('data-i18n');
        if (dict[key] !== undefined) el.textContent = dict[key];
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(function(el) {
        var key = el.getAttribute('data-i18n-placeholder');
        if (dict[key] !== undefined) el.placeholder = dict[key];
    });
    document.querySelectorAll('[data-i18n-html]').forEach(function(el) {
        var key = el.getAttribute('data-i18n-html');
        // Only allow innerHTML for trusted translation strings (not user data)
        if (dict[key] !== undefined) el.innerHTML = dict[key];
    });
    document.querySelectorAll('[data-i18n-title]').forEach(function(el) {
        var key = el.getAttribute('data-i18n-title');
        if (dict[key] !== undefined) el.title = dict[key];
    });
    document.querySelectorAll('[data-i18n-confirm]').forEach(function(el) {
        var key = el.getAttribute('data-i18n-confirm');
        if (dict[key] !== undefined) el.setAttribute('data-confirm', dict[key]);
    });
    // Update aria-label attributes
    document.querySelectorAll('[data-i18n-title]').forEach(function(el) {
        var key = el.getAttribute('data-i18n-title');
        if (dict[key] !== undefined && el.hasAttribute('aria-label')) {
            el.setAttribute('aria-label', dict[key]);
        }
    });
    document.documentElement.setAttribute('lang', lang);
    updateLangLabel();
}
function toggleLang() {
    var current = hestiaGetLang();
    var next = current === 'en' ? 'nl' : 'en';
    localStorage.setItem('hestia-lang', next);
    hestiaApplyLang(next);
}
function updateLangLabel() {
    var label = document.querySelector('.lang-label');
    if (label) label.textContent = hestiaGetLang().toUpperCase();
}
hestiaApplyLang(hestiaGetLang());
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        hestiaApplyLang(hestiaGetLang());
    });
}
document.addEventListener('click', function(event) {
    var el = event.target.closest('[data-confirm]');
    if (!el) return;
    if (el.hasAttribute('data-logout-url')) return;
    var message = el.getAttribute('data-confirm') || '';
    if (message && !window.confirm(message)) {
        event.preventDefault();
        event.stopPropagation();
    }
});
document.addEventListener('click', function(event) {
    var el = event.target.closest('[data-logout-url]');
    if (!el) return;
    var message = el.getAttribute('data-confirm') || '';
    if (message && !window.confirm(message)) {
        event.preventDefault();
        event.stopPropagation();
        return;
    }
    var url = el.getAttribute('data-logout-url');
    if (url) {
        window.location.href = url;
    }
});

/* ---- Modal handlers (contact, cost, stats) ---- */
var contactModal = null;
var costModal = null;
var statsModal = null;
var donateLink = null;
var statsContent = null;

/* ---- Login form submit guard ---- */
(function() {
    var loginForm = document.querySelector('form[action="/login"]');
    if (!loginForm) return;
    var submitBtn = loginForm.querySelector('.btn-arrow');
    if (!submitBtn) return;
    function lockSubmit() {
        if (loginForm.dataset.submitting === 'true') return false;
        loginForm.dataset.submitting = 'true';
        submitBtn.disabled = true;
        submitBtn.classList.add('is-loading');
        submitBtn.setAttribute('aria-busy', 'true');
        var emailInput = loginForm.querySelector('input[type="email"]');
        if (emailInput) emailInput.disabled = true;
        return true;
    }

    submitBtn.addEventListener('click', function(e) {
        if (!lockSubmit()) {
            e.preventDefault();
            e.stopPropagation();
        }
    });

    loginForm.addEventListener('submit', function(e) {
        if (!lockSubmit()) {
            e.preventDefault();
            e.stopPropagation();
        }
    });
})();
function openContactModal() {
    if (!contactModal) return;
    contactModal.classList.add('visible');
}
function closeContactModal() {
    if (!contactModal) return;
    contactModal.classList.remove('visible');
}
function openCostModal() {
    if (!costModal) return;
    costModal.classList.add('visible');
    fetch('/api/donation-link').then(function(r) { return r.json(); }).then(function(data) {
        if (data.url && donateLink) {
            try {
                var parsed = new URL(data.url);
                if (parsed.protocol === 'https:' || parsed.protocol === 'http:') {
                    donateLink.href = data.url;
                }
            } catch (e) {
                // Ignore invalid URLs
            }
        }
    });
}
function closeCostModal() {
    if (!costModal) return;
    costModal.classList.remove('visible');
}
function openStatsModal() {
    if (!statsModal || !statsContent) return;
    var lang = hestiaGetLang();
    var dict = HESTIA_I18N[lang] || {};
    statsModal.classList.add('visible');

    // Show loading state
    statsContent.textContent = '';
    var loadingP = document.createElement('p');
    loadingP.style.textAlign = 'center';
    loadingP.style.color = 'var(--subtitle)';
    loadingP.textContent = dict['stats_loading'] || 'Loading\u2026';
    statsContent.appendChild(loadingP);

    fetch('/api/statistics').then(function(r) { return r.json(); }).then(function(data) {
        if (data.error) {
            statsContent.textContent = '';
            var errorP = document.createElement('p');
            errorP.style.textAlign = 'center';
            errorP.style.color = 'var(--danger)';
            errorP.textContent = dict['stats_error'] || 'Could not load statistics.';
            statsContent.appendChild(errorP);
            return;
        }

        // Clear content and rebuild with DOM methods
        statsContent.textContent = '';

        // Stats grid
        var statsGrid = document.createElement('div');
        statsGrid.className = 'stats-grid';

        // Helper function to create stat boxes
        function createStatBox(value, label) {
            var box = document.createElement('div');
            box.className = 'stat-box';
            var valueSpan = document.createElement('span');
            valueSpan.className = 'stat-value';
            valueSpan.textContent = value.toLocaleString();
            var labelSpan = document.createElement('span');
            labelSpan.className = 'stat-label';
            labelSpan.textContent = label;
            box.appendChild(valueSpan);
            box.appendChild(labelSpan);
            return box;
        }

        statsGrid.appendChild(createStatBox(data.total_homes || 0, dict['stats_total_homes'] || 'Total homes'));
        statsGrid.appendChild(createStatBox(data.homes_today || 0, dict['stats_homes_today'] || 'Added today'));
        statsGrid.appendChild(createStatBox(data.total_subscribers || 0, dict['stats_total_subscribers'] || 'Subscribers'));
        statsGrid.appendChild(createStatBox(data.subscribers_this_month || 0, dict['stats_subscribers_this_month'] || 'New this month'));
        statsContent.appendChild(statsGrid);

        // Top cities list
        if (data.top_cities && data.top_cities.length) {
            var citiesDiv = document.createElement('div');
            citiesDiv.className = 'stats-list';
            var citiesH3 = document.createElement('h3');
            citiesH3.textContent = dict['stats_top_cities'] || 'Top cities';
            citiesDiv.appendChild(citiesH3);
            var citiesOl = document.createElement('ol');
            data.top_cities.forEach(function(c) {
                var li = document.createElement('li');
                var nameSpan = document.createElement('span');
                nameSpan.textContent = c.city; // Safely escaped
                var countSpan = document.createElement('span');
                countSpan.textContent = c.count.toLocaleString();
                li.appendChild(nameSpan);
                li.appendChild(countSpan);
                citiesOl.appendChild(li);
            });
            citiesDiv.appendChild(citiesOl);
            statsContent.appendChild(citiesDiv);
        }

    }).catch(function() {
        statsContent.textContent = '';
        var errorP = document.createElement('p');
        errorP.style.textAlign = 'center';
        errorP.style.color = 'var(--danger)';
        errorP.textContent = dict['stats_error'] || 'Could not load statistics.';
        statsContent.appendChild(errorP);
    });
}
function closeStatsModal() {
    if (!statsModal) return;
    statsModal.classList.remove('visible');
}

/* ---- Attach event listeners for toolbar buttons and footer icons ---- */
document.addEventListener('DOMContentLoaded', function() {
    /* Initialize Lucide icons */
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }

    contactModal = document.getElementById('contact-modal');
    costModal = document.getElementById('cost-modal');
    statsModal = document.getElementById('stats-modal');
    donateLink = document.getElementById('donate-link');
    statsContent = document.getElementById('stats-content');

    if (contactModal) {
        contactModal.addEventListener('click', function(e) {
            if (e.target === this) closeContactModal();
        });
    }
    if (costModal) {
        costModal.addEventListener('click', function(e) {
            if (e.target === this) closeCostModal();
        });
    }
    if (statsModal) {
        statsModal.addEventListener('click', function(e) {
            if (e.target === this) closeStatsModal();
        });
    }

    var langToggle = document.querySelector('.lang-toggle');
    var themeToggle = document.querySelector('.theme-toggle');

    updateThemeIcon();
    updateLangLabel();

    if (langToggle) {
        langToggle.addEventListener('click', toggleLang);
    }

    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }

    // Attach footer icon and avatar modal triggers
    document.querySelectorAll('.footer-icon[data-modal], img[data-modal]').forEach(function(icon) {
        icon.addEventListener('click', function() {
            var modal = this.getAttribute('data-modal');
            if (modal === 'contact') openContactModal();
            else if (modal === 'cost') openCostModal();
            else if (modal === 'stats') openStatsModal();
        });
    });

    // Attach modal close buttons
    document.querySelectorAll('[data-close-modal]').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var modal = this.getAttribute('data-close-modal');
            if (modal === 'contact') closeContactModal();
            else if (modal === 'cost') closeCostModal();
            else if (modal === 'stats') closeStatsModal();
        });
    });

    // Close modals on Escape
    document.addEventListener('keydown', function(e) {
        if (e.key !== 'Escape') return;
        if (contactModal && contactModal.classList.contains('visible')) closeContactModal();
        if (costModal && costModal.classList.contains('visible')) closeCostModal();
        if (statsModal && statsModal.classList.contains('visible')) closeStatsModal();
    });
});
