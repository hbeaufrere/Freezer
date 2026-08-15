/* Resolves the colour theme before first paint, so the page never flashes
   the wrong one. Loaded synchronously in <head>; kept tiny on purpose. */
(function () {
    try {
        var stored = localStorage.getItem('freezer-theme');
        var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        document.documentElement.setAttribute(
            'data-bs-theme', stored || (prefersDark ? 'dark' : 'light')
        );
    } catch (e) {
        document.documentElement.setAttribute('data-bs-theme', 'light');
    }
})();
