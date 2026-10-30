# Notely

Notely is a private, view-only portal for image and PDF notes. Administrators manage accounts and uploads through Django admin. Approved viewers sign in with a username and generated access code. Pages are rendered, watermarked with `copyright @Notely`, and delivered only through authenticated Django views.

## Requirements

- Python 3.11 or later
- Pillow and PyMuPDF, installed by pip without system PDF dependencies
- SQLite by default; PostgreSQL through `DATABASE_URL`

## Local setup

From the project directory:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set a unique `SECRET_KEY` in `.env`. The project loads `.env` automatically, and shell environment values take precedence. The example has `DEBUG=1` for local use. Then run:

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

Open **http://127.0.0.1:8000/** for viewer sign-in and **http://127.0.0.1:8000/admin/** for Django admin. The built-in development server speaks HTTP. Settings keep `runserver` on HTTP; production WSGI/ASGI deployments retain HTTPS redirects and secure cookies when `DEBUG=0`.

For compatibility with embedded local browser contexts that send `Origin: null`, only admin POSTs on the development server normalize that origin after the normal CSRF cookie and form-token checks pass. Production and all other endpoints use Django's normal origin validation.

`PRIVATE_STORAGE_DIR` defaults to `../notely-private-storage`, resolved relative to the project. Keep it outside `static`, `media`, and `staticfiles`. Source uploads and processed pages have no public URL route. For a local filesystem backend, use `PRIVATE_STORAGE_BACKEND=local`. The optional S3 backend stores private originals and processed pages in a private S3-compatible bucket; Django still proxies and watermarks each viewer request.

## Create viewer accounts

Viewers cannot register or reset passwords. In Django admin open **Users → Add user**. Notely generates a 12-character code and shows it once in an admin message. Share it securely with the viewer. Alternatively:

```powershell
python manage.py create_notely_user alice
```

The command prints the username and code once. Access codes are stored as Django password hashes. The Users actions deactivate accounts or regenerate codes, with regenerated codes shown once.

## Upload notes

In admin open **Notes → Add note**, enter a title and slug, optionally add a description, and upload PNG/JPG/JPEG/PDF. The file is validated by its content. Images are re-encoded as WebP and resized to at most 1600 pixels on the longest edge. PDFs are rasterized at up to 130 DPI. Defaults are 15 MB per upload and 60 PDF pages; configure `MAX_UPLOAD_MB` and `MAX_PDF_PAGES`.

Publish a note after processing. Only published, ready notes are visible. Original uploads remain in private storage for administrator-only retry. Large conversions may exceed a web request timeout; retry from the console with:

```powershell
python manage.py process_note NOTE_ID
```

Cache/session cleanup commands:

```powershell
python manage.py clean_watermarked_cache
python manage.py clean_sessions
```

## Configuration

| Setting | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | Local fallback | Set a unique secret outside local development |
| `DEBUG` | `0` if unset | Keep off in production |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated allowed hosts |
| `DATABASE_URL` | SQLite | A PostgreSQL URL selects PostgreSQL |
| `ADMIN_URL` | `admin/` | Configurable admin route |
| `PRIVATE_STORAGE_DIR` | `../notely-private-storage` | Private originals, rendered pages, watermark cache |
| `PRIVATE_STORAGE_BACKEND` | `local` | `local` filesystem or `s3` object storage for private originals and pages |
| `PRIVATE_S3_ENDPOINT_URL` | Unset | S3-compatible private storage endpoint |
| `PRIVATE_S3_REGION` | Unset | S3-compatible storage region |
| `PRIVATE_S3_BUCKET` | Unset | Private object bucket name |
| `PRIVATE_S3_ACCESS_KEY_ID` | Unset | Server-only object storage key ID |
| `PRIVATE_S3_SECRET_ACCESS_KEY` | Unset | Server-only object storage secret |
| `SINGLE_SESSION_POLICY` | `replace` | `replace` signs out the prior device; `block` rejects another login |
| `MAX_UPLOAD_MB` | `15` | Upload size limit |
| `MAX_PDF_PAGES` | `60` | PDF page limit |
| `REDIS_URL` | Unset | Optional shared rate-limit cache and cached DB sessions |
| `DB_CONN_MAX_AGE` | `60` | Persistent database connection age in seconds |

## PythonAnywhere deployment

1. Create a Python 3.11+ web app and virtualenv, upload this project, and install `requirements.txt`.
2. Create a writable directory such as `/home/yourname/notely-private`, outside every static mapping.
3. Set environment values in the PythonAnywhere WSGI file before importing the app: `SECRET_KEY`, `DEBUG=0`, `ALLOWED_HOSTS=yourname.pythonanywhere.com`, `PRIVATE_STORAGE_DIR=/home/yourname/notely-private`, and optionally `DATABASE_URL` or `ADMIN_URL`. Do not deploy a local `.env`.
4. Set the working directory to the project root and use `config.wsgi.application`.
5. In a console run `python manage.py migrate` and `python manage.py createsuperuser`.
6. Run `python manage.py collectstatic --noinput`; map `/static/` to the project's `staticfiles` directory. Never map private storage.
7. Reload the app, use its HTTPS URL, and run `python manage.py check --deploy` with production environment values.

PythonAnywhere may require `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` in WSGI settings behind its proxy. Set it only as required by the host and verify redirects to avoid loops.

## Free Render deployment

The Blueprint in `render.yaml` uses Render's free web service and Supabase's free PostgreSQL and Storage tiers. No paid Render disk or Render database is provisioned. This can have a $0 monthly service cost while each provider's free quotas and policies are sufficient. Free tiers do not provide production uptime or backups: Render sleeps after inactivity, and Supabase may pause an inactive project. Render's filesystem is temporary, so Notely stores private source and page files in Supabase Storage instead. The free Supabase limits are currently 500 MB of database and 1 GB of file storage; check provider pages for current limits before deployment.

1. Create a Supabase Free project. Choose Singapore to match the Render Blueprint.
2. In Supabase **Storage**, create a bucket named `notely-private` and leave it **Private**. In Storage settings, enable S3 and create an S3 access key pair. Copy the endpoint and region shown there. Treat the secret key as a server secret: it grants broad storage access and must never be put in browser code or committed to Git.
3. In Supabase **Database → Connect**, copy a **Session pooler** connection string. Use the session pooler because it supports IPv4 connections from Render and works with Django's persistent DB connections. Keep the password URL-encoded if it contains URL-reserved characters.
4. Push the project to a Git repository; do not commit `.env`, `db.sqlite3`, or storage keys. In Render, choose **New + → Blueprint**, connect the repository, and apply `render.yaml`.
5. When Render requests Blueprint environment values, provide `DATABASE_URL`, `PRIVATE_S3_ENDPOINT_URL`, `PRIVATE_S3_REGION`, `PRIVATE_S3_BUCKET` (`notely-private`), `PRIVATE_S3_ACCESS_KEY_ID`, and `PRIVATE_S3_SECRET_ACCESS_KEY`. The Blueprint generates `SECRET_KEY`, runs `collectstatic` and migrations during build, starts one Gunicorn worker, and checks `/healthz/`.
6. After deploy, use the Render Shell to create the first administrator:

   ```sh
   python manage.py createsuperuser
   ```

7. Open `https://<your-service>.onrender.com/admin/`, create viewer users, and upload notes. Note processing and viewer images travel through Django; the S3 bucket is private and has no public image URLs.

This deploy starts with a new Supabase database. It does not copy the local SQLite database or files from `notely-private-storage`; recreate viewer accounts and re-upload the notes after deployment. Keep the local project and private storage as your source copy until you have confirmed the deployed notes.

Render's free web service sleeps after 15 minutes without traffic and can take about a minute to wake. Its local cache is disposable; source files and rendered pages remain in Supabase Storage across Render restarts. Supabase Free projects can pause after a week of low database activity and need to be resumed. Its free database has no backups, and Render's free PostgreSQL expires after 30 days, which is why this Blueprint uses Supabase PostgreSQL instead. Keep your own database and file backups. Free tiers have limited CPU and memory; large PDFs may fail to process, so the Blueprint reduces upload limits to 10 MB and 30 pages.

The free Supabase project is a third-party data store for private notes. Use it only if its privacy terms and free-tier availability suit your use case. See [Render free services](https://render.com/docs/free), [Supabase free plan limits](https://supabase.com/pricing), [Supabase S3 authentication](https://supabase.com/docs/guides/storage/s3/authentication), and [Supabase free project pausing](https://supabase.com/docs/guides/platform/free-project-pausing).

## Performance and scaling

Notely includes GZip middleware, WhiteNoise compressed static assets, database connection reuse, indexes for note ordering and audit lookups, and pre-sized WebP pages. Configure `REDIS_URL` to share login rate limits and cached database sessions across workers. Use PostgreSQL and tune Gunicorn workers for available CPU and memory. On a VPS, nginx can use an authenticated `X-Accel-Redirect` internal location for private files after Django authorization and watermarking. PythonAnywhere free accounts have limited CPU and disk and no persistent background workers; large conversions may exceed practical request limits. Free Render is configured for one worker and low traffic, not the original 1000-concurrent-user target.

## Security and limitations

User and note management actions are restricted to superusers. Viewer pages and image delivery require login and an active account. Production uses HTTP-only, SameSite=Lax, secure cookies, HSTS, SSL redirect, CSRF protection, and nosniff headers. There is no public registration, password reset, export, download, raw-file, or note API route.

Browser controls are deterrents and cannot guarantee prevention of copying. Screenshots, phone-camera capture, and screen recording cannot be technically prevented. The watermark identifies Notely, not an individual viewer. `ViewLog` records note opens, but a copied image cannot be attributed to a specific viewer from its watermark. Browser headers and shortcut blocking are best effort and can be bypassed.

## Manual verification checklist

- [ ] Open `http://127.0.0.1:8000/` and `http://127.0.0.1:8000/admin/` directly in a regular browser tab.
- [ ] Create a superuser, sign in, add a viewer, and record its one-time access code.
- [ ] Confirm a non-staff viewer cannot enter admin or manage accounts/notes.
- [ ] Verify login required on the notes list, viewer, and page-image URLs.
- [ ] Exercise both session policies and deactivation on the next request.
- [ ] Submit five bad codes for the same IP/username; confirm the sixth is rate limited generically.
- [ ] Upload valid PNG/JPG/PDF and a text file renamed `.jpg`; confirm page counts and content rejection.
- [ ] Confirm originals have no URL and page responses contain the Notely watermark and no-store headers.
- [ ] Open a note and confirm the read-only `ViewLog` entry.
- [ ] Check mobile layout, lazy loading, robots, print behavior, security headers, and production deploy checks.
