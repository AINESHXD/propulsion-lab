/* ------------------------------------------------------------ *
 *  launch.js                                                     *
 *  Loads analytics (Plausible) and error monitoring (Sentry) at  *
 *  page boot. Both are STRICTLY production-only and read their   *
 *  configuration from the backend /config endpoint, which the    *
 *  server fills from environment variables at deploy time.       *
 *                                                                *
 *  In development /config returns empty strings for the DSN and  *
 *  Plausible domain, so nothing is loaded and no third-party     *
 *  request is made.                                              *
 *                                                                *
 *  Failure here MUST NEVER break the app: every call is wrapped  *
 *  in try/catch and a failed config fetch is silently ignored.   *
 * ------------------------------------------------------------ */

(async function bootLaunchServices() {
  const cfg = await fetch("/config", { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : null))
    .catch(() => null);
  if (!cfg || cfg.environment !== "production") return;

  // Plausible — cookieless privacy-first analytics. The script auto-tracks
  // pageviews; we tag the app version as a custom property if the API offers
  // it. Plausible itself ignores localhost so a double-safety against
  // accidental dev pings is in place.
  if (cfg.plausible_domain) {
    try {
      const s = document.createElement("script");
      s.defer = true;
      s.dataset.domain = cfg.plausible_domain;
      s.src = "https://plausible.io/js/script.js";
      document.head.appendChild(s);
    } catch (_) { /* never break the page */ }
  }

  // Sentry browser SDK from CDN. DSNs are public by Sentry's design (rate-
  // limited at ingest) so they are safe to ship to the browser; the gating
  // here is purely about not pinging Sentry from dev.
  if (cfg.sentry_dsn) {
    try {
      await new Promise((resolve, reject) => {
        const s = document.createElement("script");
        s.src = "https://browser.sentry-cdn.com/8.42.0/bundle.min.js";
        s.integrity = "";   // CDN provides SRI in their snippet; intentionally
                            // omitted here because the user can pin a version
                            // change without us shipping a new hash.
        s.crossOrigin = "anonymous";
        s.onload = resolve;
        s.onerror = reject;
        document.head.appendChild(s);
      });
      if (window.Sentry) {
        window.Sentry.init({
          dsn: cfg.sentry_dsn,
          environment: "production",
          release: cfg.app_version || undefined,
          tracesSampleRate: cfg.sentry_traces_sample_rate || 0.1,
          // The dashboard is a console; we don't want to ship every console
          // warn to Sentry, just real errors.
          ignoreErrors: ["ResizeObserver loop limit exceeded", "Non-Error promise rejection"],
        });
      }
    } catch (_) { /* never break the page */ }
  }
})();
