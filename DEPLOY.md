# Deploying PropulsionLab

The app is a single FastAPI service that serves both the API and the static
console. It is containerised and ready for Fly.io. Everything below is run by
**you** with your own accounts — these steps need credentials and a domain that
only you should hold.

> The hosted image excludes Cantera to stay small; the equilibrium combustor and
> real-gas hot-section toggle simply fall back to the constant-cp model in
> production. To enable them, add `cantera>=3.0` to `requirements-prod.txt`
> (expect a much larger image and longer build).

---

## 0. Prerequisites

- [Fly.io](https://fly.io) account + `flyctl` installed (`fly auth login`)
- Docker (only if you want to test the image locally first)
- *(optional)* a domain you control, Cloudflare account, Sentry project, Plausible site

## 1. Test the image locally (optional)

```bash
docker build -t propulsionlab .
docker run --rm -p 8080:8080 propulsionlab
# open http://localhost:8080/lab/
```

## 2. First deploy to Fly

```bash
fly launch --no-deploy        # detects the Dockerfile + fly.toml; pick an app name + region
fly deploy
fly open                      # opens https://<your-app>.fly.dev/lab/
```

`fly.toml` already sets `force_https = true`, a `/` health check, and
scale-to-zero (`min_machines_running = 0`) for a free-tier-friendly footprint.

## 3. Error monitoring (Sentry) — optional

The app reads `SENTRY_DSN` at runtime and no-ops if it is unset.

```bash
fly secrets set SENTRY_DSN="https://<key>@<org>.ingest.sentry.io/<project>"
# optional tuning:
fly secrets set SENTRY_TRACES_SAMPLE_RATE="0.1" SENTRY_ENVIRONMENT="production"
```

## 4. Analytics (Plausible) — optional

Privacy-friendly, cookieless. In `app/static/index.html`, uncomment the
Plausible `<script>` in `<head>` and set `data-domain` to your production
domain, then redeploy. It loads no third-party script until you do this.

## 5. Custom domain + HTTPS

```bash
fly certs add propulsionlab.com
fly certs add www.propulsionlab.com
fly certs show propulsionlab.com      # shows the DNS records to create
```

Create the DNS records Fly prints. If using **Cloudflare**: add the `A`/`AAAA`
(or `CNAME`) records, and set them to **DNS-only (grey cloud)** initially so
Fly can issue the certificate; you can enable proxying afterwards. Fly issues
and renews the TLS certificate automatically.

## 6. Launch surfaces (already in the app)

- **Star-on-GitHub link** — footer "Open source" card in
  `app/static/index.html`, pointing at the public repo.
- **`/pro/` stub** — live at `/pro/` (teaser only; no payments/accounts).

## 7. Updating

```bash
fly deploy        # rebuilds + ships; static asset cache-busting is via ?v= query strings
```

## Notes

- Bump the `?v=` query strings on `styles.css` / `app.js` / `casestudies.js`
  links in `index.html` when you change those files, so browsers fetch the new
  versions.
- The server binds `0.0.0.0:$PORT` (Fly sets `PORT`); Gunicorn runs 2 Uvicorn
  workers — raise `-w` in the `Dockerfile` on larger machines.
