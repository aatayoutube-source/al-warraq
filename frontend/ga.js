/* Google Analytics 4, set up from a file of the site's own (its pages run no inline script: CSP).
   The measurement id comes from this tag's data-id; the server writes both tags (pages.analytics_head).
   A local copy of the site measures nothing. In the European Economic Area, the United Kingdom and
   Switzerland, analytics and ad storage wait for the visitor's consent (as the privacy policy says). */
(() => {
    'use strict';
    const me = document.currentScript;
    const id = me && me.dataset.id;
    if (!id || /^(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\])$/.test(location.hostname)) return;
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); }; // gtag.js wants the arguments object itself
    window.gtag('consent', 'default', {
        ad_storage: 'denied',
        ad_user_data: 'denied',
        ad_personalization: 'denied',
        analytics_storage: 'denied',
        region: ['AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU',
            'MT', 'NL', 'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE', 'IS', 'LI', 'NO', 'GB', 'CH'],
        wait_for_update: 500
    });
    window.gtag('js', new Date());
    window.gtag('config', id);
})();
