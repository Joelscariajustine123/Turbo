# Turbo Cab

Ride-booking system with three kinds of users: **riders**, **drivers** and **admins**.

| Part | Folder | What it is |
|---|---|---|
| Backend + website | `turbo/`, `account/`, `riderpages/`, `driverpages/`, `adminpages/` | Django site (server-rendered pages) |
| REST API | `api/` | JSON API at `/api/` used by React and the mobile apps |
| Web app | `frontend/` | React (Vite) single-page app for all three roles |
| Mobile apps | `mobile/` | Flutter: `turbo_rider`, `turbo_driver`, `turbo_admin` + shared `turbo_core` |

Business rules live in one place, the `services.py` module in each app, so the website, the API, React and Flutter all behave the same.

---

## 1. Backend (Django)

```powershell
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000     # 0.0.0.0 so phones on your Wi-Fi can reach it
python manage.py test                        # 48 tests
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
| `DJANGO_DB_PATH` | `db.sqlite3` | SQLite file location |
| `TURBO_ROUTING_URL` | `https://router.project-osrm.org` | OSRM server for road distances; `''` = straight-line estimate only |
| `TURBO_UPI_ID` | `joeljustine@ybl` | UPI ID riders pay to |

### How fares work
The client sends pickup/drop **coordinates**; the server works out the distance (OSRM road route, or straight line × 1.3 if OSRM is unreachable, with a 5-minute back-off) and the fare: `₹50 + km × rate` (Sedan 15, SUV 20, Bike 8, Auto 12, set in `riderpages/models.py`). Clients cannot set the price.

---

## 2. REST API

Auth is JWT: `POST /api/auth/login/` returns `access` (30 min) and `refresh` (14 days) tokens. Send `Authorization: Bearer <access>`, and call `/api/auth/refresh/` when you get a 401. Every error response has a readable `detail` string. Lists are paginated: `{count, next, previous, results}` with `?page=N`.

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/api/meta/` | anyone | vehicle types + rates, statuses, UPI ID |
| POST | `/api/contact/` | anyone | `{name, email, message}` |
| POST | `/api/auth/register/` | anyone | `{role: rider\|driver, full_name, username, email, phone, password}` → tokens |
| POST | `/api/auth/login/` | anyone | `{email, password, role}` → `{access, refresh, user}` |
| POST | `/api/auth/refresh/` | anyone | `{refresh}` |
| POST | `/api/auth/logout/` | user | `{refresh}`, revokes it |
| GET / PATCH | `/api/auth/me/` | user | `full_name`, `email`, `phone` |
| POST | `/api/auth/change-password/` | user | `{old_password, new_password}` |
| POST | `/api/rider/quote/` | rider | `{pickup_lat, pickup_lng, drop_lat, drop_lng}` → distance, route line, fare per vehicle |
| GET / POST | `/api/rider/rides/` | rider | list (`?state=active\|past`) / book `{pickup, drop, car_type, …coords}` |
| GET | `/api/rider/rides/{id}/` | rider | |
| POST | `/api/rider/rides/{id}/pay/` | rider | `{payment_method: cash\|upi, transaction_id}` |
| POST | `/api/rider/rides/{id}/cancel/` | rider | while pending/confirmed |
| POST | `/api/rider/rides/{id}/rate/` | rider | `{rating: 1-5, review_text}` once, after completion |
| GET / PATCH | `/api/driver/profile/` | driver | JSON or multipart (`profile_photo`) |
| GET | `/api/driver/rides/available/` · `ongoing/` · `history/` | driver | declined rides are hidden for that driver only |
| POST | `/api/driver/rides/{id}/accept/` · `decline/` · `complete/` | driver | |
| GET | `/api/driver/earnings/` | driver | totals, 30-day chart, recent earnings, rating |
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
npm run dev        # http://localhost:5173 (calls Django on :8000 through the Vite proxy)
npm run build      # production files in frontend/dist
```

For a production build served from a different host than Django, set `VITE_API_URL` (see `.env.example`) and add that site's origin to `DJANGO_CORS_ORIGINS`.

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
