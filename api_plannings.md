# Nirbhor — Next API Batch

## 1. Updated Schemas

## 2. Repositories

## 3. Services

## 4. Routers

## 5. Background Job — Urgent Broadcast Expiry

## 6. Register New Routers in `app/api/v1/router.py`

---

## Priority Order for What's Left

Based on your screen list, here's what remains grouped by priority:

**Next batch (core app flows):**
- `GET /api/v1/providers/{provider_id}/public` — seeker taps provider card to see full profile
- `GET /api/v1/urgent/broadcast/{id}/status` — seeker polls to see if broadcast was claimed (or use FCM)

**After that (admin panel):**
- `GET /api/v1/admin/dashboard` — counts summary
- `GET /api/v1/admin/verifications` — pending verification list
- `PATCH /api/v1/admin/verifications/{provider_id}` — approve/reject
- `GET /api/v1/admin/reports` — flagged profiles
- `PATCH /api/v1/admin/reports/{report_id}` — dismiss/suspend
- `GET /api/v1/admin/users` — user list with filters
- `PATCH /api/v1/admin/users/{user_id}/toggle` — enable/disable account
- `GET /api/v1/admin/analytics` — stats + graphs



why sqlalchemy returns direct objects or tuples when I write the query in service layer
but it returns memory locations <> when I write the query in repository layer?


what will I answer if teacher asks why didn't I use pubsub for notifications? Why used FCM instead? =>  FCM method we are using is direct multicast