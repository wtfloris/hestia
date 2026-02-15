// =====================================================================
// Settings overlay
// =====================================================================

function getFiltersDetails() {
    return document.getElementById('filters-collapsible');
}

function openSettings() {
    var details = getFiltersDetails();
    if (details) {
        details.open = true;
    }
}

function closeSettings() {
    var details = getFiltersDetails();
    if (!details) return;
    if (window.matchMedia && window.matchMedia('(max-width: 999px)').matches) {
        details.open = false;
    }
}

function syncFiltersForViewport() {
    var details = getFiltersDetails();
    if (!details || !window.matchMedia) return;
    var wide = window.matchMedia('(min-width: 1000px)').matches;
    details.open = wide ? true : details.open;
    if (wide) {
        details.setAttribute('data-fixed', 'true');
    } else {
        details.removeAttribute('data-fixed');
    }
}

(function() {
    // Auto-open settings for new users (only on desktop)
    var layout = document.querySelector('[data-is-new-user]');
    if (layout && layout.dataset.isNewUser === 'true') {
        if (window.matchMedia && window.matchMedia('(min-width: 1000px)').matches) {
            openSettings();
        }
    }

    function syncToolbarPlacement() {
        var toolbar = document.querySelector('.toolbar-buttons');
        var toolbarSlot = document.getElementById('settings-toolbar-slot');
        var wide = window.matchMedia && window.matchMedia('(min-width: 1000px)').matches;
        if (!toolbar) return;
        if (!wide && toolbarSlot) {
            toolbarSlot.appendChild(toolbar);
            toolbar.classList.add('settings-toolbar');
        } else {
            document.body.appendChild(toolbar);
            toolbar.classList.remove('settings-toolbar');
        }
    }

    function moveFooterIcons() {
        var footerIcons = document.querySelector('.footer-icons');
        var footerSlot = document.getElementById('settings-footer-slot');
        var footer = document.querySelector('footer');
        if (footerIcons && footerSlot) {
            footerSlot.appendChild(footerIcons);
            if (footer) footer.style.display = 'none';
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            syncToolbarPlacement();
            moveFooterIcons();
        });
    } else {
        syncToolbarPlacement();
        moveFooterIcons();
    }

    syncFiltersForViewport();
    window.addEventListener('resize', function() {
        syncFiltersForViewport();
        syncToolbarPlacement();
    });

    var details = getFiltersDetails();
    if (details) {
        var summary = details.querySelector('summary');
        if (summary) {
            summary.addEventListener('click', function(e) {
                if (window.matchMedia && window.matchMedia('(min-width: 1000px)').matches) {
                    e.preventDefault();
                }
            });
        }
    }

    // Link Telegram button (inside settings overlay)
    var linkTelegramBtn = document.querySelector('.btn-open-telegram-modal');
    if (linkTelegramBtn) {
        linkTelegramBtn.addEventListener('click', openTelegramModal);
    }

    // Avatar image (opens contact modal)
    var avatar = document.querySelector('img[data-modal="contact"]');
    if (avatar) {
        avatar.addEventListener('click', openContactModal);
    }

    // Info buttons
    document.querySelectorAll('.info-btn').forEach(function(btn) {
        var bubble = btn.querySelector('.info-bubble');
        var infoKey = btn.dataset.infoKey;
        if (infoKey) {
            bubble.setAttribute('data-i18n-html', infoKey);
        }
        if (!infoKey && btn.dataset.info) {
            bubble.textContent = btn.dataset.info;
        }
        function clearBubblePosition() {
            if (!bubble) return;
            bubble.style.position = '';
            bubble.style.left = '';
            bubble.style.top = '';
            bubble.style.maxWidth = '';
            bubble.style.transform = '';
        }
        function positionBubble() {
            if (!bubble) return;
            var panel = btn.closest('.filters-collapsible');
            if (!panel) return;
            var panelRect = panel.getBoundingClientRect();
            var btnRect = btn.getBoundingClientRect();

            bubble.style.position = 'fixed';
            bubble.style.transform = 'none';

            // Detect containing-block offset: ancestors with transform or
            // contain:layout make position:fixed relative to themselves,
            // not the viewport. Place at 0,0 and measure the real position.
            bubble.style.left = '0px';
            bubble.style.top = '0px';
            var probe = bubble.getBoundingClientRect();
            var offsetX = probe.left;
            var offsetY = probe.top;

            var isLeft = btn.classList.contains('info-left');
            if (isLeft) {
                var availableLeft = btnRect.left - panelRect.left - 8;
                var maxWidthLeft = Math.max(0, Math.floor(Math.min(330, availableLeft)));
                bubble.style.maxWidth = maxWidthLeft + 'px';
                var bubbleRectLeft = bubble.getBoundingClientRect();
                var leftPos = btnRect.left - 6 - bubbleRectLeft.width;
                var minLeft = panelRect.left + 8;
                bubble.style.left = (Math.max(minLeft, leftPos) - offsetX) + 'px';
                bubble.style.top = (btnRect.top + btnRect.height / 2 - bubbleRectLeft.height / 2 - offsetY) + 'px';
            } else {
                var desiredLeft = btnRect.right + 6;
                var availableRight = panelRect.right - desiredLeft - 8;
                var maxWidth = Math.max(0, Math.floor(Math.min(330, availableRight)));
                bubble.style.maxWidth = maxWidth + 'px';
                bubble.style.left = (desiredLeft - offsetX) + 'px';
                var bubbleRect = bubble.getBoundingClientRect();
                bubble.style.top = (btnRect.top + btnRect.height / 2 - bubbleRect.height / 2 - offsetY) + 'px';
            }
        }
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            var wasVisible = bubble.classList.contains('visible');
            document.querySelectorAll('.info-bubble.visible').forEach(function(b) { b.classList.remove('visible'); });
            document.querySelectorAll('.info-bubble').forEach(function(b) {
                b.style.position = '';
                b.style.left = '';
                b.style.top = '';
                b.style.maxWidth = '';
                b.style.transform = '';
            });
            if (!wasVisible) {
                bubble.classList.add('visible');
                positionBubble();
            } else {
                clearBubblePosition();
            }
        });
    });
    document.addEventListener('click', function() {
        document.querySelectorAll('.info-bubble.visible').forEach(function(b) { b.classList.remove('visible'); });
        document.querySelectorAll('.info-bubble').forEach(function(b) {
            b.style.position = '';
            b.style.left = '';
            b.style.top = '';
            b.style.maxWidth = '';
            b.style.transform = '';
        });
    });
    window.addEventListener('resize', function() {
        document.querySelectorAll('.info-bubble.visible').forEach(function(b) {
            var btn = b.closest('.info-btn');
            if (!btn) return;
            var panel = btn.closest('.filters-collapsible');
            if (!panel) return;
            var panelRect = panel.getBoundingClientRect();
            var btnRect = btn.getBoundingClientRect();
            b.style.position = 'fixed';
            b.style.transform = 'none';
            b.style.left = '0px';
            b.style.top = '0px';
            var probe = b.getBoundingClientRect();
            var offsetX = probe.left;
            var offsetY = probe.top;
            var isLeft = btn.classList.contains('info-left');
            if (isLeft) {
                var availableLeft = btnRect.left - panelRect.left - 8;
                var maxWidthLeft = Math.max(0, Math.floor(Math.min(330, availableLeft)));
                b.style.maxWidth = maxWidthLeft + 'px';
                var bubbleRectLeft = b.getBoundingClientRect();
                var leftPos = btnRect.left - 6 - bubbleRectLeft.width;
                var minLeft = panelRect.left + 8;
                b.style.left = (Math.max(minLeft, leftPos) - offsetX) + 'px';
                b.style.top = (btnRect.top + btnRect.height / 2 - bubbleRectLeft.height / 2 - offsetY) + 'px';
            } else {
                var desiredLeft = btnRect.right + 6;
                var availableRight = panelRect.right - desiredLeft - 8;
                var maxWidth = Math.max(0, Math.floor(Math.min(330, availableRight)));
                b.style.maxWidth = maxWidth + 'px';
                b.style.left = (desiredLeft - offsetX) + 'px';
                var bubbleRect = b.getBoundingClientRect();
                b.style.top = (btnRect.top + btnRect.height / 2 - bubbleRect.height / 2 - offsetY) + 'px';
            }
        });
    });

    // Sort toggle lists: checked items first, then alphabetical
    // Then progressively render items for better performance
    document.querySelectorAll('.toggle-list').forEach(function(list) {
        var items = Array.from(list.children);
        items.sort(function(a, b) {
            var aChecked = a.querySelector('input[type=checkbox]').checked ? 0 : 1;
            var bChecked = b.querySelector('input[type=checkbox]').checked ? 0 : 1;
            if (aChecked !== bChecked) return aChecked - bChecked;
            var aText = a.textContent.trim().toLowerCase();
            var bText = b.textContent.trim().toLowerCase();
            return aText.localeCompare(bText);
        });
        items.forEach(function(item) { list.appendChild(item); });

        // Progressive rendering: show items in batches as user scrolls
        var INITIAL_BATCH = 20;
        var LOAD_MORE_BATCH = 20;
        var hiddenItems = items.slice(INITIAL_BATCH);
        var currentIndex = INITIAL_BATCH;

        // Initially hide items beyond the first batch
        hiddenItems.forEach(function(item) {
            item.style.display = 'none';
        });

        // Only set up observer if there are hidden items
        if (hiddenItems.length > 0) {
            var loadMoreTrigger = document.createElement('div');
            loadMoreTrigger.className = 'load-more-trigger';
            loadMoreTrigger.style.height = '1px';
            list.appendChild(loadMoreTrigger);

            var observer = new IntersectionObserver(function(entries) {
                entries.forEach(function(entry) {
                    if (entry.isIntersecting && currentIndex < items.length) {
                        // Load next batch
                        var endIndex = Math.min(currentIndex + LOAD_MORE_BATCH, items.length);
                        for (var i = currentIndex; i < endIndex; i++) {
                            items[i].style.display = '';
                        }
                        currentIndex = endIndex;

                        // Remove observer if all items loaded
                        if (currentIndex >= items.length) {
                            observer.disconnect();
                            loadMoreTrigger.remove();
                        }
                    }
                });
            }, { root: list.closest('.filters-collapsible'), rootMargin: '100px' });

            observer.observe(loadMoreTrigger);

            // Store observer for cleanup if needed
            list._progressiveObserver = observer;
        }
    });

    // Search filtering with debounce and optimized DOM manipulation
    document.querySelectorAll('.toggle-search').forEach(function(input) {
        var list = document.getElementById(input.dataset.list);
        if (!list) return;

        var searchTimer = null;
        var cachedItems = null;

        input.addEventListener('input', function() {
            var query = input.value.toLowerCase();

            // Debounce: wait 100ms after last keystroke before filtering
            if (searchTimer) clearTimeout(searchTimer);

            searchTimer = setTimeout(function() {
                // Cache items on first search
                if (!cachedItems) {
                    cachedItems = Array.from(list.children).filter(function(item) {
                        return item.classList.contains('toggle-item');
                    }).map(function(item) {
                        return {
                            element: item,
                            text: item.textContent.trim().toLowerCase()
                        };
                    });
                }

                // Use requestAnimationFrame for smoother rendering
                requestAnimationFrame(function() {
                    // When searching, show all matching items (override progressive rendering)
                    cachedItems.forEach(function(item) {
                        if (query === '' || item.text.includes(query)) {
                            item.element.classList.remove('search-hidden');
                            // Clear inline display style from progressive rendering
                            item.element.style.display = '';
                        } else {
                            item.element.classList.add('search-hidden');
                        }
                    });
                });
            }, 100);
        });
    });

    // Price range validation (0–99999, integers only)
    var minInput = document.querySelector('input[name="min_price"]');
    var maxInput = document.querySelector('input[name="max_price"]');
    var priceWarning = document.querySelector('.price-warning');
    if (minInput && maxInput && priceWarning) {
        function clampPrice(input) {
            var v = input.value.replace(/[^0-9]/g, '');
            if (v !== '' && Number(v) > 99999) v = '99999';
            if (input.value !== v) input.value = v;
        }
        function checkPriceRange() {
            clampPrice(minInput);
            clampPrice(maxInput);
            var min = minInput.value;
            var max = maxInput.value;
            if (min !== '' && max !== '' && Number(max) < Number(min)) {
                priceWarning.style.display = '';
                var lang = hestiaGetLang();
                var dict = HESTIA_I18N[lang] || {};
                priceWarning.textContent = dict['price_warning'] || 'Minimum is higher than maximum';
            } else {
                priceWarning.style.display = 'none';
            }
        }
        minInput.addEventListener('input', checkPriceRange);
        maxInput.addEventListener('input', checkPriceRange);
        checkPriceRange();
    }

    // City chips autocomplete
    var cityInput = document.getElementById('add-city-input');
    var cityDropdown = document.getElementById('city-dropdown');
    var cityChipsContainer = document.getElementById('city-chips');
    var cityHiddenInputsContainer = document.getElementById('city-hidden-inputs');
    var availableCitiesScript = document.getElementById('available-cities-data');

    if (cityInput && cityDropdown && cityChipsContainer && cityHiddenInputsContainer && availableCitiesScript) {
        var availableCities = [];
        try {
            availableCities = JSON.parse(availableCitiesScript.textContent);
        } catch (e) {
            console.error('Failed to parse available cities:', e);
        }

        function getSelectedCities() {
            var hiddenInputs = cityHiddenInputsContainer.querySelectorAll('input[name="filter_cities"]');
            return Array.from(hiddenInputs).map(function(input) {
                return input.value;
            });
        }

        function addCity(city) {
            var selectedCities = getSelectedCities();
            if (selectedCities.indexOf(city) !== -1) {
                return; // Already added
            }

            // Add chip
            var chip = document.createElement('div');
            chip.className = 'chip';
            chip.setAttribute('data-value', city);
            chip.innerHTML = '<span class="chip-label">' + city.charAt(0).toUpperCase() + city.slice(1) + '</span>' +
                           '<button type="button" class="chip-remove" aria-label="Remove ' + city + '">\u00d7</button>';
            cityChipsContainer.appendChild(chip);

            // Add hidden input
            var hiddenInput = document.createElement('input');
            hiddenInput.type = 'hidden';
            hiddenInput.name = 'filter_cities';
            hiddenInput.value = city;
            cityHiddenInputsContainer.appendChild(hiddenInput);

            // Clear input and hide dropdown
            cityInput.value = '';
            cityDropdown.style.display = 'none';

            // Trigger save
            if (typeof window.hestiaDebouncedSave === 'function') {
                window.hestiaDebouncedSave();
            }
        }

        function removeCity(city) {
            // Remove chip
            var chip = cityChipsContainer.querySelector('.chip[data-value="' + city + '"]');
            if (chip) {
                chip.remove();
            }

            // Remove hidden input
            var hiddenInputs = cityHiddenInputsContainer.querySelectorAll('input[name="filter_cities"]');
            hiddenInputs.forEach(function(input) {
                if (input.value === city) {
                    input.remove();
                }
            });

            // Trigger save
            if (typeof window.hestiaDebouncedSave === 'function') {
                window.hestiaDebouncedSave();
            }
        }

        var hintTimer = null;

        function updateDropdown(query) {
            // Clear any pending hint timer
            if (hintTimer) {
                clearTimeout(hintTimer);
                hintTimer = null;
            }

            if (query.length === 0) {
                cityDropdown.style.display = 'none';
                return;
            }

            if (query.length === 1) {
                // Set timer to show hint after 1 second
                hintTimer = setTimeout(function() {
                    if (cityInput.value.length === 1) {
                        cityDropdown.innerHTML = '<div class="add-item-dropdown-empty" style="font-style:italic;text-align:left">Type at least 2 characters\u2026</div>';
                        cityDropdown.style.display = 'block';
                    }
                }, 1000);
                cityDropdown.style.display = 'none';
                return;
            }

            if (query.length < 2) {
                cityDropdown.style.display = 'none';
                return;
            }

            var selectedCities = getSelectedCities();
            var selectedCitiesLower = selectedCities.map(function(c) { return c.toLowerCase(); });
            var filteredCities = availableCities.filter(function(city) {
                return city.toLowerCase().includes(query.toLowerCase()) &&
                       selectedCitiesLower.indexOf(city.toLowerCase()) === -1;
            });

            if (filteredCities.length === 0) {
                cityDropdown.innerHTML = '<div class="add-item-dropdown-empty">No cities found</div>';
                cityDropdown.style.display = 'block';
                return;
            }

            cityDropdown.innerHTML = '';
            filteredCities.forEach(function(city) {
                var item = document.createElement('div');
                item.className = 'add-item-dropdown-item';
                item.textContent = city.charAt(0).toUpperCase() + city.slice(1);
                item.addEventListener('click', function() {
                    addCity(city);
                });
                cityDropdown.appendChild(item);
            });
            cityDropdown.style.display = 'block';
        }

        // Input event listener
        cityInput.addEventListener('input', function() {
            updateDropdown(cityInput.value);
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', function(e) {
            if (!cityInput.contains(e.target) && !cityDropdown.contains(e.target)) {
                cityDropdown.style.display = 'none';
            }
        });

        // Handle chip removal (event delegation)
        cityChipsContainer.addEventListener('click', function(e) {
            if (e.target.classList.contains('chip-remove')) {
                var chip = e.target.closest('.chip');
                if (chip) {
                    var city = chip.getAttribute('data-value');
                    removeCity(city);
                }
            }
        });

        // Allow Enter key to add first result
        cityInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                var firstItem = cityDropdown.querySelector('.add-item-dropdown-item');
                if (firstItem) {
                    firstItem.click();
                }
            }
        });
    }
})();

// =====================================================================
// Autosave settings
// =====================================================================

(function() {
    var form = document.getElementById('settings-form');
    if (!form) return;

    var statusTop = document.getElementById('settings-status');
    var statusBottom = document.getElementById('settings-status-bottom');
    var statusEls = [statusTop, statusBottom].filter(Boolean);
    var spinnerTop = document.getElementById('settings-save-spinner');
    var checkTop = document.getElementById('settings-save-check');
    var errorTop = document.getElementById('settings-status-error');
    var errorBottom = document.getElementById('settings-status-error-bottom');
    var saveInFlight = false;
    var pendingSave = false;
    var saveTimer = null;
    var retryTimer = null;
    var debounceTimer = null;
    var retryDelays = [1000, 5000];
    var successTimer = null;
    var lastHomesSignature = null;

    function updateErrorCopy() {
        var isMobile = window.matchMedia && window.matchMedia('(max-width: 999px)').matches;
        var key = isMobile ? 'saving_error_tap' : 'saving_error';
        [errorTop, errorBottom].filter(Boolean).forEach(function(el) {
            el.setAttribute('data-i18n', key);
        });
        if (typeof hestiaApplyLang === 'function') {
            hestiaApplyLang(hestiaGetLang());
        }
    }

    updateErrorCopy();
    window.addEventListener('resize', updateErrorCopy);

    function isPriceInvalid() {
        var warning = document.querySelector('.price-warning');
        return warning && warning.style.display !== 'none';
    }

    function showSaving(show) {
        if (!statusEls.length) return;
        statusEls.forEach(function(status) {
            if (show) {
                status.classList.remove('is-error');
            }
        });
        if (spinnerTop) spinnerTop.style.display = show ? '' : 'none';
        if (show && checkTop) checkTop.style.display = 'none';
    }

    function showError(show) {
        if (!statusEls.length) return;
        statusEls.forEach(function(status) {
            if (show) {
                status.classList.add('is-error');
            } else {
                status.classList.remove('is-error');
            }
        });
        if (errorTop) errorTop.style.display = show ? '' : 'none';
        if (errorBottom) errorBottom.style.display = show ? '' : 'none';
        if (show) {
            showSaving(false);
            if (checkTop) checkTop.style.display = 'none';
        }
    }

    function showSuccess() {
        if (!checkTop) return;
        if (successTimer) clearTimeout(successTimer);
        checkTop.style.display = '';
        successTimer = setTimeout(function() {
            checkTop.style.display = 'none';
        }, 1500);
    }

    function scheduleRetry(attempt) {
        if (attempt > retryDelays.length) return false;
        var delay = retryDelays[attempt - 1];
        if (retryTimer) clearTimeout(retryTimer);
        retryTimer = setTimeout(function() {
            attemptSave(attempt + 1);
        }, delay);
        return true;
    }

    function buildHomesSignature(formData) {
        var min = formData.get('min_price') || '';
        var max = formData.get('max_price') || '';
        var minsqm = formData.get('min_sqm') || '';
        var cities = formData.getAll('filter_cities').slice().sort().join(',');
        var agencies = formData.getAll('filter_agencies').slice().sort().join(',');
        return [min, max, minsqm, cities, agencies].join('|');
    }

    // Initialize signature so the first save doesn't trigger a refresh
    lastHomesSignature = buildHomesSignature(new FormData(form));

    function attemptSave(attempt) {
        if (isPriceInvalid()) return;

        if (saveTimer) clearTimeout(saveTimer);
        saveTimer = setTimeout(function() {
            showSaving(true);
        }, 1000);

        var formData = new FormData(form);
        if (!formData.get('min_price')) formData.set('min_price', '0');
        if (!formData.get('max_price')) formData.set('max_price', '99999');
        if (!formData.get('min_sqm')) formData.set('min_sqm', '0');
        var newSignature = buildHomesSignature(formData);
        var refreshHomes = lastHomesSignature !== null && newSignature !== lastHomesSignature;
        fetch('/dashboard/filters', {
            method: 'POST',
            headers: { 'Accept': 'application/json' },
            body: formData,
        }).then(function(r) { return r.json(); }).then(function(data) {
            if (!data.ok) throw new Error('save failed');
            lastHomesSignature = newSignature;
            if (refreshHomes) {
                // Cancel any in-flight background refresh
                if (_autoRefreshController) {
                    _autoRefreshController.abort();
                    _autoRefreshController = null;
                }
                // Reset auto-refresh timer
                if (typeof resetAutoRefresh === 'function') {
                    resetAutoRefresh();
                }
                // Clear known URLs and reload list
                _knownHomeUrls = {};
                fetchHomes(1, true);
            }
            showError(false);
            showSuccess();
        }).catch(function() {
            var willRetry = scheduleRetry(attempt);
            if (!willRetry) {
                showError(true);
            } else {
                if (saveTimer) {
                    clearTimeout(saveTimer);
                    saveTimer = null;
                }
                showSaving(true);
            }
        }).finally(function() {
            if (saveTimer) {
                clearTimeout(saveTimer);
                saveTimer = null;
            }
            if (!retryTimer) {
                showSaving(false);
            }
            saveInFlight = false;
            if (pendingSave && !retryTimer) {
                pendingSave = false;
                performSave();
            }
        });
    }

    function performSave() {
        if (saveInFlight) {
            pendingSave = true;
            return;
        }
        if (isPriceInvalid()) return;

        saveInFlight = true;
        pendingSave = false;
        showError(false);
        if (retryTimer) {
            clearTimeout(retryTimer);
            retryTimer = null;
        }
        attemptSave(1);
    }

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        if (debounceTimer) {
            clearTimeout(debounceTimer);
            debounceTimer = null;
        }
        performSave();
    });

    function debouncedSave() {
        // If a save is already in progress, mark that we need to save again
        if (saveInFlight) {
            pendingSave = true;
            // Clear any pending debounce since we'll save when current save completes
            if (debounceTimer) {
                clearTimeout(debounceTimer);
                debounceTimer = null;
            }
            return;
        }

        // Clear any pending debounce
        if (debounceTimer) {
            clearTimeout(debounceTimer);
        }
        // Wait 300ms after last change before saving
        debounceTimer = setTimeout(function() {
            debounceTimer = null;
            performSave();
        }, 300);
    }

    // Make debouncedSave available globally for city chips
    window.hestiaDebouncedSave = debouncedSave;

    form.querySelectorAll('input[type="checkbox"]').forEach(function(input) {
        if (input.id === 'browser-notif-checkbox') return;
        input.addEventListener('change', debouncedSave);
    });

    var minInput = form.querySelector('input[name="min_price"]');
    var maxInput = form.querySelector('input[name="max_price"]');
    if (minInput) minInput.addEventListener('input', debouncedSave);
    if (maxInput) maxInput.addEventListener('input', debouncedSave);
    var minSqmInput = form.querySelector('input[name="min_sqm"]');
    if (minSqmInput) minSqmInput.addEventListener('input', debouncedSave);

    if (errorTop) errorTop.addEventListener('click', performSave);
    if (errorBottom) errorBottom.addEventListener('click', performSave);
})();

// =====================================================================
// Homes list fetching and rendering
// =====================================================================

var _currentPage = 1;
var _totalPages = 1;
var _isLoading = false;
var _lastLoadAt = 0;
var _pendingFetch = null;
var _knownHomeUrls = {};
var _maxPages = 5; // 50 results at 10 per page
var _autoRefreshController = null; // AbortController for background refresh

function fetchHomes(page, resetList) {
    var list = document.getElementById('homes-list');
    var empty = document.getElementById('homes-empty');
    if (!list) return;

    if (_isLoading) {
        _pendingFetch = { page: page, resetList: resetList };
        return;
    }
    var now = Date.now();
    // Rate limit scroll-triggered loads, but not filter changes (resetList = true)
    if (!resetList && now - _lastLoadAt < 1000) {
        return;
    }
    _isLoading = true;
    _lastLoadAt = now;

    if (resetList) {
        list.innerHTML = '<div class="homes-loading"><span class="spinner"></span></div>';
        var limitMsg = document.getElementById('homes-limit-msg');
        if (limitMsg) limitMsg.style.display = 'none';
        var endMsg = document.getElementById('homes-end-msg');
        if (endMsg) endMsg.style.display = 'none';
    } else {
        var loading = document.createElement('div');
        loading.className = 'homes-loading';
        loading.innerHTML = '<span class="spinner"></span>';
        list.appendChild(loading);
    }
    empty.style.display = 'none';

    fetch('/api/homes?page=' + page + '&per_page=10')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            _currentPage = data.page;
            _totalPages = Math.ceil(data.total / data.per_page);

            if (resetList) {
                list.innerHTML = '';
            } else {
                var loaders = list.querySelectorAll('.homes-loading');
                loaders.forEach(function(el) { el.remove(); });
            }

            if (data.homes.length === 0) {
                empty.style.display = '';
                var endMsg = document.getElementById('homes-end-msg');
                if (endMsg) endMsg.style.display = 'none';
                // Re-init lucide for the empty state icon
                if (typeof lucide !== 'undefined') lucide.createIcons();
                _isLoading = false;
                if (_pendingFetch) {
                    var pending = _pendingFetch;
                    _pendingFetch = null;
                    fetchHomes(pending.page, pending.resetList);
                }
                return;
            }

            data.homes.forEach(function(home) {
                if (home.url) _knownHomeUrls[home.url] = true;
                list.appendChild(renderHomeCard(home));
            });

            if (typeof lucide !== 'undefined') {
                lucide.createIcons();
            }
            var endMsg = document.getElementById('homes-end-msg');
            if (endMsg) {
                endMsg.style.display = (_currentPage >= _totalPages && _totalPages > 0) ? '' : 'none';
            }
            _isLoading = false;
            if (_pendingFetch) {
                var pending = _pendingFetch;
                _pendingFetch = null;
                fetchHomes(pending.page, pending.resetList);
            }
        })
        .catch(function() {
            var loaders = list.querySelectorAll('.homes-loading');
            loaders.forEach(function(el) { el.remove(); });
            if (resetList) {
                list.innerHTML = '<p style="color:var(--danger);text-align:center;padding:2rem">Failed to load homes. Please try again.</p>';
            }
            _isLoading = false;
            if (_pendingFetch) {
                var pending = _pendingFetch;
                _pendingFetch = null;
                fetchHomes(pending.page, pending.resetList);
            }
        });
}

function renderHomeCard(home) {
    var card = document.createElement('div');
    card.className = 'home-card';

    var link = document.createElement('a');
    link.href = home.url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';

    var media = document.createElement('div');
    media.className = 'home-card-media';

    var image = document.createElement('img');
    image.className = 'home-card-image';
    image.alt = home.address ? ('Preview of ' + home.address) : 'Home preview';
    image.loading = 'lazy';
    image.decoding = 'async';
    image.referrerPolicy = 'no-referrer';

    var placeholder = document.createElement('div');
    placeholder.className = 'home-card-placeholder';
    placeholder.innerHTML = '<i data-lucide="home" style="width:28px;height:28px"></i>';

    media.appendChild(image);
    media.appendChild(placeholder);
    link.classList.add('home-card-link');
    link.appendChild(media);

    var body = document.createElement('div');
    body.className = 'home-card-body';

    var address = document.createElement('div');
    address.className = 'home-card-address';
    address.textContent = home.address;
    body.appendChild(address);

    var city = document.createElement('div');
    city.className = 'home-card-city';
    city.textContent = home.city;
    body.appendChild(city);

    var meta = document.createElement('div');
    meta.className = 'home-card-meta';

    var metaLeft = document.createElement('span');
    metaLeft.className = 'home-card-meta-left';

    var price = document.createElement('span');
    price.className = 'home-card-price';
    price.textContent = home.price >= 0 ? '\u20AC' + home.price : '';
    metaLeft.appendChild(price);

    if (typeof home.sqm === 'number' && home.sqm > 0) {
        var sqm = document.createElement('span');
        sqm.className = 'home-card-sqm';
        sqm.textContent = home.sqm + ' m2';
        metaLeft.appendChild(sqm);
    }

    meta.appendChild(metaLeft);

    if (home.agency) {
        var agency = document.createElement('span');
        agency.className = 'home-card-agency';
        agency.textContent = home.agency;
        meta.appendChild(agency);
    }

    body.appendChild(meta);

    if (home.date_added) {
        var dateEl = document.createElement('div');
        dateEl.className = 'home-card-date';
        var d = new Date(home.date_added);
        dateEl.textContent = formatRelativeTime(d);
        dateEl.title = d.toLocaleString();
        body.appendChild(dateEl);
    }

    link.appendChild(body);

    if (home.url) {
        loadPreviewImage(home.url, image, placeholder, media);
    }

    card.appendChild(link);
    return card;
}

function formatRelativeTime(date) {
    if (!(date instanceof Date) || isNaN(date.getTime())) return '';
    var diffMs = Date.now() - date.getTime();
    var diffSec = Math.round(diffMs / 1000);
    if (diffSec < 45) return 'just now';

    var rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });
    var minutes = Math.round(diffSec / 60);
    if (Math.abs(minutes) < 60) return rtf.format(-minutes, 'minute');

    var hours = Math.round(minutes / 60);
    if (Math.abs(hours) < 24) return rtf.format(-hours, 'hour');

    var days = Math.round(hours / 24);
    if (Math.abs(days) < 7) return rtf.format(-days, 'day');

    var weeks = Math.round(days / 7);
    if (Math.abs(weeks) < 5) return rtf.format(-weeks, 'week');

    var months = Math.round(days / 30);
    if (Math.abs(months) < 12) return rtf.format(-months, 'month');

    var years = Math.round(days / 365);
    return rtf.format(-years, 'year');
}

function loadPreviewImage(url, imgEl, placeholderEl, mediaEl) {
    if (!imgEl || !placeholderEl || !mediaEl) return;

    var didLoad = false;
    function showImage(src) {
        if (!src) return;
        imgEl.onload = function() {
            didLoad = true;
            imgEl.classList.add('is-loaded');
            mediaEl.classList.add('has-image');
        };
        imgEl.onerror = function() {
            if (!didLoad) {
                imgEl.classList.remove('is-loaded');
                mediaEl.classList.remove('has-image');
            }
        };
        imgEl.src = '/api/preview-image-raw?url=' + encodeURIComponent(src);
    }

    // home.url is always a listing page URL, never a direct image
    // Step 1: Parse listing page HTML to find image URL
    fetch('/api/preview-image?url=' + encodeURIComponent(url)).then(function(r) {
        if (!r.ok) throw new Error('preview fetch failed');
        return r.json();
    }).then(function(data) {
        if (data.image_url) {
            // Step 2: Proxy the discovered image through our server
            showImage(data.image_url);
        }
    }).catch(function() {
        imgEl.style.display = 'none';
        placeholderEl.style.display = '';
    });
}

// Two-step image loading process (both cached for 30 days):
//   1. /api/preview-image - Parse listing HTML to find og:image URL
//   2. /api/preview-image-raw - Proxy the image to avoid CORS/privacy issues

// Fetch homes on page load
fetchHomes(1, true);

// Infinite scroll
window.addEventListener('scroll', function() {
    if (_isLoading) return;
    if (_currentPage >= _totalPages && _totalPages > 0) {
        var endMsg = document.getElementById('homes-end-msg');
        if (endMsg) endMsg.style.display = '';
        return;
    }
    if (_currentPage >= _maxPages) {
        var limitMsg = document.getElementById('homes-limit-msg');
        if (limitMsg) limitMsg.style.display = '';
        return;
    }
    var scrollBottom = window.innerHeight + window.scrollY;
    var threshold = document.body.offsetHeight - 300;
    if (scrollBottom >= threshold) {
        fetchHomes(_currentPage + 1, false);
    }
});

// =====================================================================
// Browser notifications toggle
// =====================================================================

var _browserNotifEnabled = false;

function sendBrowserNotification(newCount) {
    if (!_browserNotifEnabled) return;
    if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return;
    var lang = typeof hestiaGetLang === 'function' ? hestiaGetLang() : 'en';
    var dict = HESTIA_I18N[lang] || HESTIA_I18N['en'] || {};
    var body;
    if (newCount === 1) {
        body = dict['browser_notif_new_one'] || '1 new home has been found';
    } else {
        body = (dict['browser_notif_new_many'] || '{count} new homes have been found').replace('{count}', newCount);
    }
    new Notification('Hestia', { body: body, icon: '/avatar' });
}

(function() {
    var STORAGE_KEY = 'hestia-browser-notif';
    var checkbox = document.getElementById('browser-notif-checkbox');
    var toggle = document.getElementById('browser-notif-toggle');
    var deniedHint = document.getElementById('browser-notif-denied');
    var iosInfo = document.getElementById('browser-notif-ios-info');
    var notifRow = toggle ? toggle.closest('.notification-row') : null;
    if (!checkbox) return;

    // Disable on iOS — notifications aren't supported in regular Safari
    var isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    if (isIOS) {
        checkbox.checked = false;
        checkbox.disabled = true;
        _browserNotifEnabled = false;
        if (toggle) toggle.classList.add('disabled');
        if (iosInfo) iosInfo.style.display = '';
        return;
    }

    function getNotifHelpUrl() {
        var ua = navigator.userAgent;
        if (/Edg\//i.test(ua)) return 'https://support.microsoft.com/en-us/microsoft-edge/manage-website-notifications-in-microsoft-edge-0c555609-5bf2-479d-a59d-fb30a0b80b2b';
        if (/Chrome/i.test(ua) && !/Edg/i.test(ua)) return 'https://support.google.com/chrome/answer/3220216';
        if (/Firefox/i.test(ua)) return 'https://support.mozilla.org/en-US/kb/push-notifications-firefox';
        if (/Safari/i.test(ua) && !/Chrome/i.test(ua)) return 'https://support.apple.com/guide/safari/customize-website-notifications-sfri40734/mac';
        return 'https://support.google.com/chrome/answer/3220216';
    }

    function setDenied() {
        checkbox.checked = false;
        checkbox.disabled = true;
        _browserNotifEnabled = false;
        localStorage.setItem(STORAGE_KEY, 'false');
        if (toggle) toggle.classList.add('disabled');
        if (deniedHint) {
            deniedHint.style.display = '';
            deniedHint.href = getNotifHelpUrl();
        }
    }

    // If browser doesn't support notifications or permission is already denied, lock it
    if (typeof Notification === 'undefined' || Notification.permission === 'denied') {
        setDenied();
        return;
    }

    // Restore saved preference (only enable if permission was already granted)
    var saved = localStorage.getItem(STORAGE_KEY) === 'true';
    if (saved && Notification.permission === 'granted') {
        checkbox.checked = true;
        _browserNotifEnabled = true;
    }

    checkbox.addEventListener('change', function() {
        if (checkbox.checked) {
            if (Notification.permission === 'granted') {
                _browserNotifEnabled = true;
                localStorage.setItem(STORAGE_KEY, 'true');
            } else if (Notification.permission === 'denied') {
                setDenied();
            } else {
                Notification.requestPermission().then(function(result) {
                    if (result === 'granted') {
                        _browserNotifEnabled = true;
                        localStorage.setItem(STORAGE_KEY, 'true');
                    } else {
                        setDenied();
                    }
                });
            }
        } else {
            _browserNotifEnabled = false;
            localStorage.setItem(STORAGE_KEY, 'false');
        }
    });
})();

// =====================================================================
// Live auto-refresh (every 60s with retry on failure)
// =====================================================================

var _autoRefreshTimer = null;

(function() {
    var REFRESH_INTERVAL = 60000;
    var RETRY_DELAYS = [5000, 30000];
    var liveStatus = document.getElementById('homes-live-status');
    var liveError = document.getElementById('homes-live-error');
    var dead = false;

    if (liveError) {
        liveError.addEventListener('click', function() { location.reload(); });
    }

    function showLive() {
        if (liveStatus) liveStatus.style.display = '';
        if (liveError) liveError.style.display = 'none';
    }

    function updateLiveErrorCopy() {
        if (!liveError) return;
        var isMobile = window.matchMedia && window.matchMedia('(max-width: 999px)').matches;
        var span = liveError.querySelector('[data-i18n]');
        if (span) span.setAttribute('data-i18n', isMobile ? 'homes_live_lost_tap' : 'homes_live_lost');
        if (typeof hestiaApplyLang === 'function') hestiaApplyLang(hestiaGetLang());
    }

    function showDead() {
        if (liveStatus) liveStatus.style.display = 'none';
        if (liveError) liveError.style.display = '';
        updateLiveErrorCopy();
        dead = true;
    }

    function getDisplayedHomeUrls() {
        var urls = {};
        var list = document.getElementById('homes-list');
        if (!list) return urls;
        list.querySelectorAll('.home-card a[href]').forEach(function(link) {
            urls[link.href] = true;
        });
        return urls;
    }

    function doRefresh(retryIndex) {
        // Create abort controller for this refresh
        _autoRefreshController = new AbortController();

        fetch('/api/homes?page=1&per_page=10', { signal: _autoRefreshController.signal })
            .then(function(r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(function(data) {
                _autoRefreshController = null;

                var list = document.getElementById('homes-list');
                var empty = document.getElementById('homes-empty');
                if (!list) return;

                // Update total pages but don't reset _currentPage — that
                // tracks how far the user has scrolled via infinite scroll.
                _totalPages = Math.ceil(data.total / data.per_page);

                var newHomes = [];

                // Find homes we haven't seen before
                data.homes.forEach(function(home) {
                    if (home.url && !_knownHomeUrls[home.url]) {
                        newHomes.push(home);
                    }
                    if (home.url) _knownHomeUrls[home.url] = true;
                });

                // Handle empty state
                if (data.homes.length === 0 && list.children.length === 0) {
                    if (empty) empty.style.display = '';
                } else {
                    if (empty) empty.style.display = 'none';
                }

                // Prepend new homes to the top of the list
                if (newHomes.length > 0) {
                    var fragment = document.createDocumentFragment();
                    newHomes.reverse().forEach(function(home) {
                        var card = renderHomeCard(home);
                        card.classList.add('home-card-new');
                        card.addEventListener('click', function() {
                            card.classList.remove('home-card-new');
                        }, { once: true });
                        fragment.appendChild(card);
                    });
                    list.insertBefore(fragment, list.firstChild);

                    if (typeof lucide !== 'undefined') lucide.createIcons();

                    // Send notification for new homes
                    sendBrowserNotification(newHomes.length);
                }

                // Reset to healthy state and schedule next refresh
                showLive();
                scheduleRefresh();
            })
            .catch(function(err) {
                // Ignore aborted requests
                if (err.name === 'AbortError') return;

                _autoRefreshController = null;

                if (retryIndex < RETRY_DELAYS.length) {
                    // Retry after delay
                    _autoRefreshTimer = setTimeout(function() {
                        doRefresh(retryIndex + 1);
                    }, RETRY_DELAYS[retryIndex]);
                } else {
                    // All retries exhausted — show error
                    showDead();
                }
            });
    }

    function scheduleRefresh() {
        if (dead) return;
        if (_autoRefreshTimer) clearTimeout(_autoRefreshTimer);
        _autoRefreshTimer = setTimeout(function() {
            doRefresh(0);
        }, REFRESH_INTERVAL);
    }

    // Export reset function for filter changes
    window.resetAutoRefresh = function() {
        if (_autoRefreshController) {
            _autoRefreshController.abort();
            _autoRefreshController = null;
        }
        scheduleRefresh();
    };

    // Start the cycle
    showLive();
    scheduleRefresh();
})();

// =====================================================================
// Telegram linking modal
// =====================================================================

var _telegramPollInterval = null;
var _telegramExpiresAt = null;

function copyLinkCommand() {
    var commandEl = document.getElementById('telegram-link-command');
    var messageEl = document.getElementById('telegram-copy-message');
    if (!commandEl) return;

    var text = commandEl.textContent;

    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function() {
            if (messageEl) {
                messageEl.style.display = '';
                setTimeout(function() {
                    messageEl.style.display = 'none';
                }, 2000);
            }
        }).catch(function(err) {
            console.error('Failed to copy:', err);
        });
    } else {
        var textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-9999px';
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            if (messageEl) {
                messageEl.style.display = '';
                setTimeout(function() {
                    messageEl.style.display = 'none';
                }, 2000);
            }
        } catch (err) {
            console.error('Failed to copy:', err);
        }
        document.body.removeChild(textArea);
    }
}

function initializeLinkCode() {
    var csrfInput = document.querySelector('input[name="csrf_token"]');
    var csrfToken = csrfInput ? csrfInput.value : '';
    var body = new URLSearchParams();
    body.append('csrf_token', csrfToken);

    document.getElementById('telegram-code-active').style.display = '';
    document.getElementById('telegram-code-expired').style.display = 'none';

    fetch('/api/link-code', { method: 'POST', body: body }).then(function(r) { return r.json(); }).then(function(data) {
        if (data.code) {
            document.getElementById('telegram-link-command').textContent = '/link ' + data.code;
            var openBtn = document.getElementById('telegram-open-btn');
            if (openBtn) openBtn.href = 'https://t.me/hestia_homes_bot?start=hestia-web-link-' + data.code;

            _telegramExpiresAt = Date.now() + (data.expires_in * 1000);
        }
    });

    if (_telegramPollInterval) clearInterval(_telegramPollInterval);
    _telegramPollInterval = setInterval(function() {
        // Check if code has expired
        if (_telegramExpiresAt && Date.now() > _telegramExpiresAt) {
            clearInterval(_telegramPollInterval);
            _telegramPollInterval = null;
            document.getElementById('telegram-code-active').style.display = 'none';
            document.getElementById('telegram-code-expired').style.display = '';
            return;
        }
        fetch('/link-telegram/check').then(function(r) { return r.json(); }).then(function(data) {
            if (data.linked) {
                clearInterval(_telegramPollInterval);
                _telegramPollInterval = null;
                setTimeout(function() { window.location.reload(); }, 1000);
            }
        });
    }, 3000);
}

function openTelegramModal() {
    var modal = document.getElementById('telegram-modal');
    if (!modal) return;
    modal.classList.add('visible');
    initializeLinkCode();
}

function regenerateLinkCode() {
    initializeLinkCode();
}

function closeTelegramModal() {
    var modal = document.getElementById('telegram-modal');
    if (modal) modal.classList.remove('visible');
    if (_telegramPollInterval) { clearInterval(_telegramPollInterval); _telegramPollInterval = null; }
    _telegramExpiresAt = null;
}

var telegramModal = document.getElementById('telegram-modal');
if (telegramModal) {
    telegramModal.addEventListener('click', function(e) {
        if (e.target === this) closeTelegramModal();
    });

    var closeBtn = telegramModal.querySelector('[data-close-modal="telegram"]');
    if (closeBtn) {
        closeBtn.addEventListener('click', closeTelegramModal);
    }

    var linkCommand = document.getElementById('telegram-link-command');
    if (linkCommand) {
        linkCommand.addEventListener('click', copyLinkCommand);
    }

    var regenerateBtn = telegramModal.querySelector('.btn-regenerate-code');
    if (regenerateBtn) {
        regenerateBtn.addEventListener('click', regenerateLinkCode);
    }
}
