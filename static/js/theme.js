(function () {
    function preferredTheme() {
        try {
            var storedTheme = localStorage.getItem('theme');
            if (storedTheme === 'dark' || storedTheme === 'light') {
                return storedTheme;
            }
        } catch (error) {
            return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
        }

        return 'dark';
    }

    function applyTheme(theme) {
        if (theme === 'dark') {
            document.documentElement.dataset.theme = 'dark';
        } else {
            document.documentElement.removeAttribute('data-theme');
        }

        document.querySelectorAll('[data-theme-toggle]').forEach(function (button) {
            var isDark = theme === 'dark';
            button.setAttribute('aria-pressed', isDark ? 'true' : 'false');
            button.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
            button.setAttribute('title', isDark ? 'Switch to light mode' : 'Switch to dark mode');
        });
    }

    function saveTheme(theme) {
        try {
            localStorage.setItem('theme', theme);
        } catch (error) {
            return;
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        applyTheme(preferredTheme());

        document.querySelectorAll('[data-theme-toggle]').forEach(function (button) {
            button.addEventListener('click', function () {
                var nextTheme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
                saveTheme(nextTheme);
                applyTheme(nextTheme);
            });
        });

        // Mobile nav: close hamburger menu when a nav link is clicked.
        var navToggle = document.getElementById('nav-toggle');
        if (navToggle) {
            document.querySelectorAll('.header-inner .nav a').forEach(function (link) {
                link.addEventListener('click', function () {
                    navToggle.checked = false;
                });
            });
        }
    });
})();
