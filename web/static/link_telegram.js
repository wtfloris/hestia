(function() {
    var interval = setInterval(function() {
        fetch('/link-telegram/check').then(function(r) { return r.json(); }).then(function(data) {
            if (data.linked) {
                clearInterval(interval);
                var s = document.querySelector('.telegram-status');
                s.className = 'telegram-status';
                s.textContent = '\u2714';
                window.location.href = '/dashboard';
            }
        });
    }, 3000);
})();
