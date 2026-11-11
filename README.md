# Turbo Cab

Ride-booking system with three kinds of users: **riders**, **drivers** and **admins**.

| Part | Folder | What it is |
|---|---|---|
| Backend + website | `turbo/`, `account/`, `riderpages/`, `driverpages/`, `adminpages/` | Django site (server-rendered pages) |
| REST API | `api/` | JSON API at `/api/` used by React and the mobile apps |
| Web app | `frontend/` | React (Vite) single-page app for all three roles |
| Mobile apps | `mobile/` | Flutter: `turbo_rider`, `turbo_driver`, `turbo_admin` + shared `turbo_core` |

Business rules live in one place, the `services.py` module in each app, so the website, the API, React and Flutter all behave the same.

### Live on Render

**https://turbo-u967.onrender.com** (free plan: the first visit after 15 idle minutes takes about a minute to wake up)

| Page | Link |
|---|---|
| Choose rider / driver / admin | https://turbo-u967.onrender.com/ |
| Rider website | https://turbo-u967.onrender.com/riderpages/ |
| React web app | https://turbo-u967.onrender.com/app/ |
| REST API | https://turbo-u967.onrender.com/api/meta/ |
| Django admin | https://turbo-u967.onrender.com/admin/ |

How it is hosted and how to redeploy: see [5. Hosting on Render](#5-hosting-on-render).

---

## 1. Backend (Django)

```powershell
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000     # 0.0.0.0 so phones on your Wi-Fi can reach it
python manage.py test                        # 106 tests
```

* Website: http://localhost:8000/
* API: http://localhost:8000/api/meta/
* Django admin: http://localhost:8000/admin/

**First admin:** open `/adminsignup/` once. After the first admin exists, only admins can add admins (website *Settings* or the API/app *Account* page).

### Settings (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | dev key | **Set in production** |
| `DJANGO_DEBUG` | `True` | `False` in production |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,10.0.2.2` | Add your LAN IP / domain |
| `DJANGO_CORS_ORIGINS` | `http://localhost:5173,…` | Browser origins allowed to call the API |
| `DATABASE_URL` | — | Postgres URL; when set, SQLite is not used |
| `DJANGO_DB_PATH` | `db.sqlite3` | SQLite file location |
| `DJANGO_MEDIA_ROOT` | `media/` | Where uploaded photos are stored |
| `TURBO_ADMIN_EMAIL` / `TURBO_ADMIN_PASSWORD` | — | First admin, created on deploy by `manage.py ensure_admin` |
| `TURBO_ROUTING_URL` | `https://router.project-osrm.org` | OSRM server for road distances; `''` = straight-line estimate only |
| `TURBO_UPI_ID` | `joeljustine@ybl` | UPI ID riders pay to |
| `GOOGLE_MAPS_API_KEY` | — | Use Google Maps for the live tracking maps (OpenStreetMap when empty) |
| `GOOGLE_MAPS_MAP_ID` | `DEMO_MAP_ID` | Map ID for Google Advanced Markers |
| `TURBO_OTP_TTL_MINUTES` | `10` | How long a pickup OTP stays valid |
| `TURBO_OTP_LOCK_MINUTES` | `10` | Lock after 5 wrong OTP attempts |
| `TURBO_TRACK_RETENTION_DAYS` | `30` | How long trip GPS breadcrumbs are kept |
| `TURBO_GEOFENCE_RADIUS_M` | `50` | Driver must be this close to the pickup/drop for "Arrived"/"Complete" |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | — | Gmail address + app password for verification codes |
| `DEFAULT_FROM_EMAIL` | `Turbo Cab <EMAIL_HOST_USER>` | Sender shown in the emails |
| `TURBO_EMAIL_OTP` | `auto` | `on` / `off` / `auto` (on when email is configured) |
| `GOOGLE_SITE_VERIFICATION` | — | Google Search Console ownership token (meta tag on the homepage) |
| `GOOGLE_SITE_VERIFICATION_FILES` | `google696da265b08989c0.html` | Search Console HTML verification file names served at `/` (comma-separated) |

### How fares work
The client sends pickup/drop **coordinates**; the server works out the distance (OSRM road route, or straight line × 1.3 if OSRM is unreachable, with a 5-minute back-off) and the fare: `₹50 + km × rate` (Sedan 15, SUV 20, Bike 8, Auto 12, set in `riderpages/models.py`). Clients cannot set the price.

---

## 2. REST API

Auth is JWT: `POST /api/auth/login/` returns `access` (30 min) and `refresh` (14 days) tokens. Send `Authorization: Bearer <access>`, and call `/api/auth/refresh/` when you get a 401. Every error response has a readable `detail` string. Lists are paginated: `{count, next, previous, results}` with `?page=N`.

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/api/meta/` | anyone | vehicle types + rates, statuses, UPI ID |
| POST | `/api/contact/` | anyone | `{name, email, message}` |
| POST | `/api/auth/register/` | anyone | `{role: rider\|driver, full_name, username, email, phone, password}` → `{otp_required, challenge}` |
| POST | `/api/auth/login/` | anyone | `{email, password, role}` → `{otp_required, challenge, email}` (code emailed) |
| POST | `/api/auth/verify-email/` | anyone | `{challenge, code}` → `{access, refresh, user}` |
| POST | `/api/auth/resend-code/` | anyone | `{challenge}` → new code (once a minute) |
| POST | `/api/auth/refresh/` | anyone | `{refresh}` |
| POST | `/api/auth/logout/` | user | `{refresh}`, revokes it |
| GET / PATCH | `/api/auth/me/` | user | `full_name`, `email`, `phone` |
| POST | `/api/auth/change-password/` | user | `{old_password, new_password}` |
| POST | `/api/rider/quote/` | rider | `{pickup_lat, pickup_lng, drop_lat, drop_lng}` → distance, route line, fare per vehicle |
| GET / POST | `/api/rider/rides/` | rider | list (`?state=active\|past`) / book `{pickup, drop, car_type, …coords}` |
| GET | `/api/rider/rides/{id}/` | rider | |
| POST | `/api/rider/rides/{id}/pay/` | rider | after the ride: `{payment_method: cash\|upi, transaction_id}` |
| GET | `/api/driver/rides/unpaid/` | driver | completed rides still waiting for payment |
| POST | `/api/driver/rides/{id}/cash-collected/` | driver | confirm the rider paid in cash |
| POST | `/api/rider/rides/{id}/cancel/` | rider | while pending/confirmed |
| POST | `/api/rider/rides/{id}/rate/` | rider | `{rating: 1-5, review_text}` once, after completion |
| GET / PATCH | `/api/driver/profile/` | driver | JSON or multipart (`profile_photo`) |
| GET | `/api/driver/rides/available/` · `ongoing/` · `history/` | driver | declined rides are hidden for that driver only |
| POST | `/api/driver/rides/{id}/accept/` · `decline/` · `complete/` | driver | |
| GET | `/api/driver/earnings/` | driver | totals, 30-day chart, recent earnings, rating |
| POST | `/api/driver/location/update/` | driver | `{latitude, longitude, accuracy, speed, heading}` every 3 s while online → status + trip tracking |
| GET | `/api/driver/location/current/` | driver | latest saved position |
| GET | `/api/driver/active-ride/` | driver | current trip, rider contact, route, distance, ETA |
| POST | `/api/driver/ride/status/` | driver | `{ride_id, status: ARRIVED\|COMPLETED}` (only valid transitions) |
| POST | `/api/driver/ride/verify-otp/` | driver | `{ride_id, otp}` → starts the ride |
| GET | `/api/rider/ride/active/` | rider | latest active ride + driver card |
| GET | `/api/rider/ride/tracking/` | rider | driver position, pickup/drop, routes, distances, ETA (`?ride_id=`) |
| GET | `/api/rider/ride/driver-location/` | rider | assigned driver's latest position (trip only) |
| GET | `/api/rider/ride/otp/` | rider | the pickup code (before the ride starts) |
| POST | `/api/rider/ride/otp/regenerate/` | rider | new code; the old one stops working |
| GET | `/api/admin/stats/` · `reports/` | admin | |
| GET | `/api/admin/rides/` · `rides/payments/` | admin | `?status=&search=` |
| GET / PATCH / DELETE | `/api/admin/riders/{id}/` | admin | `is_active` to (de)activate |
| GET / PATCH / DELETE | `/api/admin/drivers/{user_id}/` | admin | `availability_status`, `is_active` |
| GET / DELETE | `/api/admin/messages/{id}/` | admin | contact messages |
| POST | `/api/admin/admins/` | admin | create another admin |

---

## 3. React web app (`frontend/`)

Needs Node 18+.

```powershell
cd frontend
npm install
npm run dev        # http://localhost:5173/app/ (calls Django on :8000 through the Vite proxy)
npm run build      # production files in frontend/dist/app — Django serves them at /app/
```

In production Django serves the built app at `/app/` (same origin as the API, so no CORS needed). Only if you host it on a different domain: set `VITE_API_URL` (see `.env.example`) and add that origin to `DJANGO_CORS_ORIGINS`.

---

## 4. Flutter mobile apps (`mobile/`)

Needs the Flutter SDK (3.22 or newer).

```powershell
cd mobile
powershell -ExecutionPolicy Bypass -File .\setup.ps1   # once: creates android/ios folders + permissions
cd turbo_rider      # or turbo_driver / turbo_admin
flutter run
```

* **Android emulator:** works as-is (the apps call `http://10.0.2.2:8000`, which is your PC).
* **Real phone on the same Wi-Fi:** run Django with `0.0.0.0:8000`, add your PC's IP to `DJANGO_ALLOWED_HOSTS`, then
  `flutter run --dart-define=API_URL=http://192.168.x.x:8000`
* **Release APK:** `flutter build apk --dart-define=API_URL=https://your-server`

| App | Features |
|---|---|
| Turbo Rider | map booking with GPS + place search, live fare per vehicle, UPI (opens UPI app) or cash, live ride status, call driver, cancel, rate |
| Turbo Driver | availability switch, live ride requests (auto-refresh), accept/decline/complete, call rider, earnings with chart, history, profile + photo |
| Turbo Admin | dashboard stats, rides/payments with filters, manage riders and drivers, daily reports, contact messages, add admins |

The apps refresh every 10–20 seconds; there is no push/WebSocket channel yet.

---

## 5. Hosting on Render

Everything runs as **one Docker web service** (website + API + React app at `/app/`) plus a **Render Postgres** database, described in [`render.yaml`](render.yaml).

1. Push this repository to GitHub.
2. In the Render dashboard: **New → Blueprint** → choose the repo → Render reads `render.yaml`.
3. Enter the requested `TURBO_ADMIN_EMAIL` and `TURBO_ADMIN_PASSWORD` (your first admin account) → **Apply**.
4. The first deploy takes ~5–10 minutes. Your site is then at `https://<service-name>.onrender.com`:

| URL | What |
|---|---|
| `/` | Original Django website |
| `/app/` | React app (riders, drivers, admins) |
| `/api/` | REST API (mobile apps) |
| `/admin/` | Django admin (log in with the TURBO_ADMIN account) |

Each `git push` to `main` redeploys automatically. Migrations run on every start.

### The live deployment

| | |
|---|---|
| Site | https://turbo-u967.onrender.com |
| Web service | `turbo` (Docker, free plan), health check `/api/meta/` |
| Database | `turbo-db` (Render Postgres, free plan) |
| Deploys | automatic on every push to `main` of the GitHub repo |

**What happens on each deploy** (see [`Dockerfile`](Dockerfile)):
1. Node builds the React app into `frontend/dist/app`.
2. Python installs `requirements.txt` and runs `collectstatic` (WhiteNoise serves the files).
3. On start: `migrate` → `ensure_admin` (creates the `TURBO_ADMIN_*` admin if it doesn't exist) → `purge_location_history` → `gunicorn`.

**Environment variables** (Render → **turbo → Environment**; change one, then **Save, rebuild and deploy**):

| Variable | Set by | Notes |
|---|---|---|
| `DATABASE_URL` | Blueprint | Linked to `turbo-db` |
| `DJANGO_SECRET_KEY` | Blueprint | Generated once; don't change it (logins and ride OTPs depend on it) |
| `DJANGO_DEBUG` | Blueprint | `False` |
| `WEB_CONCURRENCY` | Blueprint | gunicorn workers (`2`) |
| `TURBO_ADMIN_EMAIL` / `TURBO_ADMIN_PASSWORD` | you | First admin. Add `TURBO_ADMIN_RESET=1` once to reset that admin's password to this value |
| `TURBO_UPI_ID` | Blueprint | UPI ID riders pay to |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | optional | Gmail for login/sign-up codes (needs a paid instance, see section 7) |
| `GOOGLE_MAPS_API_KEY` | optional | Google Maps instead of OpenStreetMap (section 6) |
| `GOOGLE_SITE_VERIFICATION` | optional | Search Console meta-tag token (section 10) |

`RENDER_EXTERNAL_HOSTNAME` is provided by Render and added to `ALLOWED_HOSTS` automatically, so no host setting is needed for the `onrender.com` address. A custom domain must be added to `DJANGO_ALLOWED_HOSTS`.

**Admin login on Render:** `python manage.py createsuperuser` on your PC only changes your **local** database. The live admin is the `TURBO_ADMIN_EMAIL` account; to fix its password, set `TURBO_ADMIN_PASSWORD` plus `TURBO_ADMIN_RESET=1`, deploy, then remove `TURBO_ADMIN_RESET`.

**Logs and problems:** Render → **turbo → Logs** shows the deploy and request logs. If a deploy fails, the build log shows the failing step; the previous version keeps running until a new one is healthy.

**Mobile apps against Render:** `flutter build apk --dart-define=API_URL=https://turbo-u967.onrender.com` (or `flutter run --dart-define=…`).

**Free plan limits**
* The web service sleeps after 15 min without traffic; the next request takes about a minute to wake it.
* Free Postgres databases expire after 30 days, so upgrade the database plan to keep your data.
* Uploaded driver photos are stored on the container disk and **disappear on each deploy/restart**. To keep them, use a paid plan with the disk shown (commented) in `render.yaml` and set `DJANGO_MEDIA_ROOT=/srv/media`.

**Moving existing data from SQLite (optional):**
```powershell
python manage.py dumpdata --natural-foreign --exclude contenttypes --exclude auth.permission --exclude token_blacklist -o data.json
# then, with DATABASE_URL set to the Render database's *External* URL:
python manage.py migrate
python manage.py loaddata data.json
```

---

## 6. Live tracking and pickup OTP

### Ride steps
`CONFIRMED` (paid, finding a driver) → `ACCEPTED` (driver assigned, on the way, OTP issued) → `ARRIVED` (driver at pickup, fresh OTP issued) → `IN_PROGRESS` (OTP verified, ride started) → `COMPLETED`.
The server only allows these moves: a ride can't start without the rider's OTP and can't be completed before it starts.

### Where to find it
| Who | Website | React app | Mobile app |
|---|---|---|---|
| Driver | **Live map** in the driver menu (`/driverpages/live/`) | Dashboard | Turbo Driver → Rides |
| Rider | **Track** in My rides (`/riderpages/track/<id>/`), opened automatically after paying | Ride details | Turbo Rider → ride details |

### How it works
* While online, the driver's device sends its GPS position every 3 s. Requests never overlap, and tracking resumes when the connection returns. Only one row per driver is kept up to date, plus a sparse breadcrumb trail (at most one point every 15 s) that is deleted after `TURBO_TRACK_RETENTION_DAYS`.
* The rider's page asks for the trip every 3 s and moves the car smoothly. A rider only ever gets the location of the driver assigned to **their** ride, and only during the trip. Sharing stops when the ride completes or the driver goes offline.
* Routes, distances and ETAs are calculated on the server (OSRM road routing, cached and only recalculated when the driver leaves the route), so every screen shows the same numbers.
* **OTP:** 6 random digits, generated when the driver accepts and again when they tap "I've arrived". Valid for 10 minutes. 5 wrong tries lock it for 10 minutes, and the rider can get a new code at any time. No plain code is stored (only a random seed and a keyed hash), drivers never receive it, and every attempt is logged (`OTPAttempt`).
* **Background tracking:** browsers pause GPS when the screen locks. The website keeps the screen awake and warns the driver. The **Turbo Driver app** shares location from an Android foreground service (iOS: background location), so it keeps working with the screen off.

### Google Maps (optional)
Without a key the maps use OpenStreetMap and work immediately. To switch to Google Maps:
1. In [Google Cloud Console](https://console.cloud.google.com/), create a project and enable billing.
2. Enable **Maps JavaScript API**.
3. Under *APIs & Services → Credentials*, create an API key. Restrict it to *Websites* `https://turbo-u967.onrender.com/*` (plus `http://localhost:8000/*` for development) and to the Maps JavaScript API.
4. Optional: under *Google Maps Platform → Map management*, create a JavaScript **Map ID** (vector) for Advanced Markers. Otherwise `DEMO_MAP_ID` is used.
5. In Render, open **turbo → Environment**, add `GOOGLE_MAPS_API_KEY` (and `GOOGLE_MAPS_MAP_ID`), then **Save, rebuild and deploy**.

If Google ever rejects the key, the pages switch back to OpenStreetMap by themselves.

---

## 7. Email verification codes (register + login)

* **Register:** a 6-digit code is emailed. The account works only after the code is entered.
* **Login:** email + password first, then a code emailed to the account's address (for riders, drivers and admins).
* Codes expire after 10 minutes and are single-use. 5 wrong tries burn the code. "Resend" works once a minute (max 6 per hour). Only a keyed hash is stored.
* Accounts that existed before this feature count as verified. Changing your email means confirming the new address at the next login.
* The Django admin site (`/admin/`) still uses password only.

### Gmail setup
1. Turn on **2-Step Verification** for the Gmail account at [myaccount.google.com/security](https://myaccount.google.com/security).
2. Open [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords), create an app password called "Turbo", and copy the 16-character password.
3. In Render, open **turbo → Environment** and add:
   * `EMAIL_HOST_USER` = your Gmail address
   * `EMAIL_HOST_PASSWORD` = the app password (spaces are fine)
4. **Render's free plan blocks outgoing SMTP** (ports 25/465/587). Gmail only works after upgrading the **turbo** web service to a paid instance (Starter). On the free plan the emails can't be sent.
5. Save and deploy. With `TURBO_EMAIL_OTP=auto` (the default), codes switch on as soon as email is configured. Before that, login works without codes, so nobody gets locked out.

Locally (`DEBUG=True`, no email settings) the codes are printed in the `runserver` console.

## 8. Ride rules

* **Payment after the ride:** booking sends the ride straight to drivers. When it's completed, the rider chooses UPI (QR + transaction ID → **Paid**) or cash (**Cash due** → the driver taps **Cash collected** → **Paid**).
* **50 m rule:** "I've arrived" unlocks only when the driver's live GPS is within 50 m of the pickup, and "Complete ride" only within 50 m of the destination. The fix must be at most 30 s old and accurate to ±75 m. The server enforces this, so the buttons can't be bypassed. The rider's OTP can be entered only after "Arrived".
* **Precision:**
  * GPS is requested at the highest accuracy, and rough fixes worse than ±150 m are ignored while a good recent one exists.
  * Distance left is measured along the route line, and the route is recalculated when the driver strays 100 m.
  * ETAs come from the route's real driving times.
  * The trip trail is recorded every 5 s or 10 m.

---

## 9. Sign in with Google (removed from the pages)

The login and sign-up pages (website and React) offer **email + password** with the emailed code only. The "Continue with Google" button was taken off every page; a test (`test_no_google_button_on_any_auth_page`) keeps it that way. The server-side endpoints (`/google-login/`, `/api/auth/google/`) still exist but no page uses them.

---

## 10. If Chrome shows "Dangerous site"

That's a Google Safe Browsing flag on the address, not an error in the app. New sites on shared hosts like `onrender.com` are often flagged, especially pages with password forms. Only the site owner can ask Google to review it:

1. Go to [search.google.com/search-console](https://search.google.com/search-console), click **Add property → URL prefix**, and enter `https://turbo-u967.onrender.com/`.
2. Choose the **HTML file** method and click **Verify**. The file is already served: https://turbo-u967.onrender.com/google696da265b08989c0.html. (If Google gives you a different file name, add it to `GOOGLE_SITE_VERIFICATION_FILES` in Render. Or use the **HTML tag** method: put the `content="…"` value in `GOOGLE_SITE_VERIFICATION`.)
3. Keep the verification file in place; Google re-checks it from time to time.
4. Open **Security & Manual Actions → Security issues**, read which pages are listed, then click **Request review**. Explain: *"Turbo Cab is a ride-booking project. The login pages are our own (rider/driver/admin) and don't imitate any other service. We removed a Google-logo login button and a template's example email (test@saberali.co), and added our branding, privacy policy and terms."*
5. Reviews usually take from a day to a few days. Afterwards the warning disappears for everyone.

A custom domain (for example `turbocab.in`, added under Render → turbo → Settings → Custom Domains) avoids sharing reputation with other `onrender.com` sites.
