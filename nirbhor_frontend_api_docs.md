# Nirbhor — Frontend API Integration Documentation

> **For the frontend team (Flutter + React Web)**
> Base URL: `https://your-api.onrender.com/api/v1`
> Auth: Bearer token in `Authorization` header for all protected routes
> Language: Set `Accept-Language: bn` for Bangla, `Accept-Language: en` for English

---

## Table of Contents
1. [Authentication Flow](#1-authentication-flow)
2. [Provider Screens](#2-provider-screens)
3. [Seeker Screens](#3-seeker-screens)
4. [Admin Panel](#4-admin-panel)
5. [Background Jobs — What They Do Automatically](#5-background-jobs)
6. [FCM Notification Workflow](#6-fcm-notification-workflow)
7. [API Gaps & Notes](#7-api-gaps--notes)

---

## 1. Authentication Flow

### SCREEN_16 — Welcome Screen
No API call needed. Static screen with two buttons: "Find Help" (→ seeker register) and "Provide Service" (→ provider register).

---

### SCREEN_28 — Register Seeker
**API:** `POST /auth/register/seeker`
```json
Request:
{
  "name_en": "Rahim",
  "name_bn": "রহিম",
  "phone": "01712345678",
  "password": "secret123"
}

Response 201:
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "role": "seeker",
  "user_id": "uuid"
}
```
On success → store tokens → navigate to Seeker Home (SCREEN_2).

---

### SCREEN_28 / SCREEN_32 — Register Provider (Mobile + Web)
Two steps in the UI, one API call:

**Step 1 (SCREEN_28):** Collect name, phone, password
**Step 2 (SCREEN_22 / SCREEN_27):** Collect skills, location, work radius

**API:** `POST /auth/register/provider`
```json
Request:
{
  "name_en": "Karim",
  "name_bn": "করিম",
  "phone": "01812345678",
  "password": "secret123",
  "skill_ids": [1, 4],
  "latitude": 23.7510,
  "longitude": 90.3930,
  "working_radius_km": 5,
  "has_smartphone": true
}

Response 201:
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "role": "provider",
  "user_id": "uuid"
}
```
On success → store tokens → navigate to Provider Dashboard (SCREEN_14).

> **Note for skill/category dropdowns on SCREEN_22:**
> - `GET /category/list` → populate category dropdown
> - `GET /skill/{category_id}/skills` → populate skill dropdown after category selected

---

### SCREEN_17 — Login
**API:** `POST /auth/login` (form-encoded, not JSON)
```
username=01712345678&password=secret123
```
```json
Response 200:
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "role": "seeker" | "provider" | "admin",
  "user_id": "uuid"
}
```
On success → check `role` → navigate to correct home screen.

> **After any login/register:** Immediately call `POST /fcm/token` with the device's FCM token so the backend can send push notifications to this device.
```dart
// Flutter — call this after every login/register
// AND register onTokenRefresh to catch Firebase-initiated rotations

final token = await FirebaseMessaging.instance.getToken();
await api.post('/fcm/token', {
  "token": token,
  "device_type": "ANDROID"   // or "IOS", "WEB"
});

// Handle Firebase rotating the token automatically
FirebaseMessaging.instance.onTokenRefresh.listen((newToken) async {
  await api.post('/fcm/token', {
    "token": newToken,
    "device_type": "ANDROID"
  });
});
```

---

### Token Refresh (Silent — no screen)
When access token expires (1 hour), silently refresh:
**API:** `POST /auth/refresh`
```json
Request: { "refresh_token": "eyJ..." }
Response: { "access_token": "eyJ...", "refresh_token": "eyJ..." }
```
If refresh also fails → force logout → redirect to SCREEN_17.

---

## 2. Provider Screens

### SCREEN_14 — Provider Dashboard
Called on every dashboard open.

**APIs:**
1. `GET /provider/dashboard` — main dashboard data
```json
Response:
{
  "user_id": "uuid",
  "name": "করিম",
  "phone": "01812345678",
  "photo_url": "https://...",
  "verification_level": "basic" | "verified" | "trusted",
  "verification_status": "pending" | "approved" | "rejected",
  "average_rating": 4.5,
  "working_radius_km": 5,
  "has_smartphone": true,
  "is_available": true,
  "skills": [{ "id": 1, "name": "Electrician" }],
  "warning_status": false
}
```

**Toggle availability (from dashboard):**
`PATCH /provider/me/update_profile`
```json
Request: { "is_available": false }
```

**Update work radius (from dashboard):**
`PATCH /provider/me/update_profile`
```json
Request: { "working_radius_km": 10 }
```

---

### SCREEN_5 — Edit Provider Profile
**Get current data:** `GET /users/me`

**Update profile:**
`PATCH /provider/me/update_profile`
```json
Request (all fields optional — send only what changed):
{
  "photo_url": "https://cloudinary.com/...",
  "photo_public_id": "nirbhor/providers/abc123",
  "latitude": 23.7510,
  "longitude": 90.3930,
  "working_radius_km": 5,
  "has_smartphone": true,
  "is_available": true
}
```
> **Image upload flow:** Upload image to Cloudinary directly from frontend first → get back `url` and `public_id` → then call this endpoint with those values. Never send the image file to the backend.

**Add skills:** `POST /provider/me/add_skill`
```json
Request: { "skill_ids": [4, 5] }
```

**Remove skill:** `DELETE /provider/me/remove_skill?skill_id=4`

---

### SCREEN_19 / SCREEN_10 / SCREEN_29 — Verification Status & NID Upload
These three screens all represent the same verification state with different UI treatments. Use the same API.

**Check verification status:** `GET /users/me`
→ Check `verification_status` field:
- `"pending"` → show "Under Review" state
- `"rejected"` → show rejection screen (SCREEN_19/10/29) with `verification_rejection_reason`
- `"approved"` → show blue tick on dashboard

**Upload NID documents (first submission or after rejection):**
`PATCH /provider/me/update_profile`
```json
Request:
{
  "nid_url_front": "https://cloudinary.com/...",
  "nid_front_public_id": "nirbhor/nid/front_abc",
  "nid_url_back": "https://cloudinary.com/...",
  "nid_back_public_id": "nirbhor/nid/back_abc"
}
```
After upload → verification_status becomes `"pending"` → admin reviews → FCM sent on decision.

---

### SCREEN_25 — Incoming Bookings (Provider)
**API:** `GET /bookings/provider/me`
```json
Response: [
  {
    "booking_id": "uuid",
    "status": "in_progress",
    "skill_id": 4,
    "skill_name": "Electrician",
    "created_at": "2026-06-27T10:00:00Z",
    "work_schedule": "2026-06-28T09:00:00Z",
    "other_party_name": "Rahim",
    "other_party_phone": "01712345678"
  }
]
```
> Only shows `IN_PROGRESS` bookings. `INITIATED` bookings are hidden from the provider — provider doesn't know about them until the seeker confirms.

**Also show completed bookings (separate tab if needed):**
`GET /bookings/provider/me/completed`

---

### SCREEN_26 — Booking Detail (Provider)
**API:** `GET /bookings/{booking_id}`
```json
Response:
{
  "booking_id": "uuid",
  "status": "in_progress",
  "skill_id": 4,
  "created_at": "...",
  "call_unlocked_at": "...",
  "confirmed_at": "...",
  "work_schedule": "2026-06-28T09:00:00Z",
  "completed_at": null,
  "other_party_name": "Rahim",
  "other_party_phone": "01712345678",
  "job_latitude": 23.7510,
  "job_longitude": 90.3930
}
```
> Show the map with job location. "Get Directions" button → open `https://www.google.com/maps/dir/?api=1&destination={job_latitude},{job_longitude}` in native maps app. This costs nothing (no Google Maps SDK).

---

### SCREEN_30 — Urgent Alert (Provider)
This screen is shown when the provider taps the FCM notification for an urgent broadcast.

**Step 1 — FCM notification arrives:**
The notification `data` payload contains:
```json
{
  "type": "URGENT_BROADCAST",
  "broadcast_id": "uuid",
  "skill_name": "Plumber"
}
```
The app receives this even when backgrounded. Show the full-screen alert.

**Step 2 — Fetch details before showing "Accept" button:**
`GET /urgentBroadcast/broadcast/{broadcast_id}`
```json
Response:
{
  "broadcast_id": "uuid",
  "status": "broadcasting",
  "skill_id": 5,
  "skill_name": "Plumber",
  "expires_at": "2026-06-27T10:05:00Z",
  "seeker_latitude": 23.7510,
  "seeker_longitude": 90.3930
}
```

**Step 3 — Provider taps Accept:**
`POST /urgentBroadcast/broadcast/{broadcast_id}/claim`
```json
Response 200 (first provider wins):
{
  "broadcast_id": "uuid",
  "status": "CLAIMED",
  "seeker_name": "Rahim",
  "seeker_phone": "01712345678"
}

Response 409 (another provider already claimed):
{
  "detail": "Sorry, another provider has already claimed this."
}
```
On 409 → show "Already Taken" message and dismiss the alert screen.

---

## 3. Seeker Screens

### SCREEN_2 — Home / Search (with map and category dropdown)

**On screen load — check for active booking:**
`GET /bookings/seeker/last_active_initiated`
```json
Response (has open booking):
{
  "has_active_booking": true,
  "booking": {
    "booking_id": "uuid",
    "provider_name": "Karim",
    "provider_phone": "01812345678",
    "created_at": "...",
    "status": "initiated"
  }
}

Response (no open booking):
{
  "has_active_booking": false,
  "booking": null
}
```
If `has_active_booking: true` → show the blocking modal (SCREEN_9) forcing seeker to Confirm or Cancel before searching. If `false` → show normal search UI.

**Load category dropdown:**
`GET /category/list`
```json
Response: [
  { "id": 1, "name": "Manual Labor" },
  { "id": 2, "name": "Home Repairs" }
]
```

**After category selected — load skill dropdown:**
`GET /skill/{category_id}/skills`
```json
Response: [
  { "id": 4, "name": "Electrician", "category_id": 2 },
  { "id": 5, "name": "Plumber", "category_id": 2 }
]
```

---

### SCREEN_24 / SCREEN_23 — Search Results

**After skill selected + GPS acquired:**
`GET /search/providers?skill_id=4&seeker_lat=23.7510&seeker_lng=90.3930&search_radius_km=1`
```json
Response:
{
  "providers": [
    {
      "user_id": "uuid",
      "name": "Karim",
      "skill_names": ["Electrician"],
      "verification_level": "verified",
      "average_rating": 4.5,
      "distance_km": 0.39,
      "working_radius_km": 5,
      "has_smartphone": true,
      "is_available": true,
      "last_active_at": "2026-06-27T09:00:00Z"
    }
  ],
  "expanded_radius": false,
  "warning": null
}
```
If `expanded_radius: true` → show banner: "Showing results within 2km. Providers may be farther away."
If `providers` is empty → show "No providers found in your area."

**SCREEN_23 — Active Booking Card at top:**
Show this card above the results when `GET /bookings/seeker/last_active_initiated` returns `has_active_booking: true`. The card shows provider name, status, and Confirm/Cancel buttons.

---

### SCREEN_35 — Provider Public Profile
Triggered when seeker taps a provider card from search results.

**API:** `GET /provider/{provider_id}/public`
```json
Response:
{
  "user_id": "uuid",
  "name": "Karim",
  "photo_url": "https://...",
  "verification_level": "verified",
  "average_rating": 4.5,
  "working_radius_km": 5,
  "has_smartphone": true,
  "is_available": true,
  "ai_review_summary": "Users frequently praise Karim for being punctual.",
  "skills": [{ "id": 4, "name": "Electrician" }],
  "last_active_at": "..."
}
```
> Phone number is NOT here. Only revealed after "Request to Call."

**"Request to Call" button on this screen:**
`POST /bookings/initiate`
```json
Request:
{
  "provider_id": "uuid",
  "skill_id": 4,
  "latitude": 23.7510,
  "longitude": 90.3930
}

Response 201:
{
  "booking_id": "uuid",
  "provider_phone": "01812345678",
  "provider_name": "Karim",
  "status": "initiated"
}
```
On success → show the phone number → trigger native phone dialer with `tel:01812345678`.

---

### SCREEN_4 — Booking Detail (Seeker)

**API:** `GET /bookings/{booking_id}`
```json
Response:
{
  "booking_id": "uuid",
  "status": "initiated" | "in_progress" | "completed" | "cancelled" | "auto_expired",
  "skill_id": 4,
  "created_at": "...",
  "call_unlocked_at": "...",
  "confirmed_at": null,
  "work_schedule": null,
  "completed_at": null,
  "other_party_name": "Karim",
  "other_party_phone": "01812345678",
  "job_latitude": 23.7510,
  "job_longitude": 90.3930
}
```

**UI based on status:**
- `initiated` → Show "Did you hire them?" with Confirm (hired=true) and Cancel (hired=false) buttons
- `in_progress` → Show work schedule, "Mark as Completed" button
- `completed` → Show "Leave a Review" button (if not yet reviewed)
- `cancelled` / `auto_expired` → Show status label only

**Confirm/Cancel (from this screen OR from FCM notification):**
`PATCH /bookings/{booking_id}/respond`
```json
Request (hired):
{ "hired": true, "work_schedule": "2026-06-28T09:00:00Z" }

Request (cancelled):
{ "hired": false, "work_schedule": null }

Response: { "booking_id": "uuid", "status": "in_progress" | "cancelled" }
```

**Mark as Completed:**
`PATCH /bookings/{booking_id}/complete`
```json
Response: { "booking_id": "uuid", "status": "completed" }
```

---

### SCREEN_13 — Post-Job Review
Shown after seeker marks booking completed, or from My Bookings on a completed booking.

**API:** `POST /reviews`
```json
Request:
{
  "booking_id": "uuid",
  "rating": 5,
  "comment": "Very punctual and professional.",
  "is_anonymous": false
}

Response 201:
{
  "review_id": "uuid",
  "booking_id": "uuid",
  "rating": 5,
  "comment": "Very punctual and professional.",
  "is_anonymous": false
}
```
> One review per booking per party. Calling twice returns 409.

---

### SCREEN_21 — My Bookings (Seeker)
**API:** `GET /bookings/seeker/me`
```json
Response: [
  {
    "booking_id": "uuid",
    "status": "initiated",
    "skill_id": 4,
    "skill_name": "Electrician",
    "created_at": "...",
    "work_schedule": null,
    "other_party_name": "Karim",
    "other_party_phone": "01812345678"
  }
]
```
Shows all bookings (all statuses) newest first. Tapping a booking → SCREEN_4.

---

### SCREEN_15 — Urgent Request Flow (Multi-state)

**State 1: Select skill and send:**
- Use `GET /category/list` and `GET /skill/{category_id}/skills` to populate skill selection
- `POST /urgentBroadcast/broadcast`
```json
Request:
{
  "skill_id": 5,
  "latitude": 23.7510,
  "longitude": 90.3930
}

Response 201:
{
  "broadcast_id": "uuid",
  "status": "broadcasting",
  "expires_at": "2026-06-27T10:05:00Z",
  "message": "Urgent broadcast sent."
}
```

**State 2: Waiting (countdown timer):**
Start polling every 5 seconds:
`GET /urgentBroadcast/broadcast/{broadcast_id}/status`
```json
Response:
{
  "broadcast_id": "uuid",
  "status": "broadcasting",
  "expires_at": "...",
  "seconds_remaining": 240,
  "claimed_by_name": null
}
```
Drive the countdown timer from `seconds_remaining`. Stop polling when `status != "broadcasting"`.

**State 3: Claimed:**
When poll returns `status: "claimed"` OR FCM `BROADCAST_CLAIMED` arrives:
```json
{
  "status": "claimed",
  "seconds_remaining": 0,
  "claimed_by_name": "Rahim Ahmed"
}
```
Show provider name and "Call Now" button. The provider will call the seeker — their number was given to the provider when they claimed.

**State 4: Expired:**
When poll returns `status: "expired"` OR FCM `BROADCAST_EXPIRED` arrives:
Show "No one responded. Try manual search." with a "Retry" button.

---

### Seeker Profile Screen
**API:** `GET /users/me`
```json
Response:
{
  "user_id": "uuid",
  "role": "seeker",
  "phone": "01712345678",
  "name": "Rahim",
  "is_active": true,
  "created_at": "..."
}
```

---

## 4. Admin Panel

> All admin routes require `role: "admin"` in the JWT. Non-admins receive 403.

### SCREEN_7 — Admin Overview / Dashboard

**API:** `GET /admin/dashboard`
```json
Response:
{
  "total_users": 1250,
  "total_providers": 430,
  "total_seekers": 820,
  "total_bookings": 3400,
  "pending_verifications": 12,
  "pending_reports": 5,
  "active_providers_today": 87
}
```

**Recent verification requests (for dashboard preview):**
`GET /admin/verifications`
→ Show first 5 items as a preview table. Link to full list → SCREEN_18.

**Recent reports (for dashboard preview):**
`GET /admin/reports?status=PENDING`
→ Show first 5. Link to full list → SCREEN_11.

---

### SCREEN_18 — Verification Queue

**API:** `GET /admin/verifications`
```json
Response: [
  {
    "user_id": "uuid",
    "name": "Karim Ahmed",
    "phone": "01812345678",
    "photo_url": "https://...",
    "nid_front_url": "https://...",
    "nid_back_url": "https://...",
    "verification_level": "basic",
    "verification_status": "pending",
    "submitted_at": "2026-06-25T10:00:00Z"
  }
]
```
Each row has a "Review Documents" button → SCREEN_34.

---

### SCREEN_34 — Document Review Detail

**Load provider data:**
`GET /admin/verifications` → find by `user_id`
Or `GET /provider/{provider_id}/public` for profile info + the verification data from the verifications list.

**Approve:**
`PATCH /admin/verifications/{provider_id}`
```json
Request: { "action": "approve" }
Response: {
  "user_id": "uuid",
  "verification_status": "approved",
  "verification_level": "verified",
  "message": "Verification status updated."
}
```

**Reject:**
`PATCH /admin/verifications/{provider_id}`
```json
Request: {
  "action": "reject",
  "rejection_reason": "NID photo is blurry. Please re-upload."
}
Response: {
  "user_id": "uuid",
  "verification_status": "rejected",
  "verification_level": "basic",
  "message": "Verification status updated."
}
```

---

### SCREEN_11 — Reports & Moderation

**List reports with filter:**
`GET /admin/reports` → all reports
`GET /admin/reports?status=PENDING` → pending only
`GET /admin/reports?status=REVIEWED` → reviewed only
`GET /admin/reports?status=ACTION_TAKEN` → actioned only

```json
Response: [
  {
    "report_id": "uuid",
    "reporter_name": "Rahim",
    "reported_user_name": "Selim",
    "reported_user_role": "provider",
    "reason": "Fraud",
    "status": "pending",
    "booking_id": "uuid",
    "created_at": "..."
  }
]
```

**Dismiss report:**
`PATCH /admin/reports/{report_id}`
```json
Request: { "action": "dismiss" }
```

**Suspend reported user:**
`PATCH /admin/reports/{report_id}`
```json
Request: { "action": "suspend" }
Response: {
  "report_id": "uuid",
  "status": "suspend",
  "affected_user_id": "uuid"
}
```

**View associated booking:**
`GET /bookings/{booking_id}` (use `booking_id` from report)

---

### SCREEN_36 — User Management

**List all users:**
`GET /admin/users`

**Filter by role:**
`GET /admin/users?role=PROVIDER`
`GET /admin/users?role=SEEKER`

**Filter by active status:**
`GET /admin/users?is_active=false` → suspended accounts

```json
Response: [
  {
    "user_id": "uuid",
    "name": "Karim",
    "phone": "01812345678",
    "role": "provider",
    "is_active": true,
    "last_active_at": "...",
    "created_at": "..."
  }
]
```

**View user detail:**
`GET /admin/users/{user_id}`
```json
Response:
{
  "user_id": "uuid",
  "name": "Karim",
  "phone": "01812345678",
  "role": "provider",
  "is_active": true,
  "last_active_at": "...",
  "created_at": "...",
  "total_bookings": 24,
  "average_rating": 4.2,
  "verification_level": "verified",
  "verification_status": "approved"
}
```

**Enable / Disable account (toggle):**
`PATCH /admin/users/{user_id}/toggle`
```json
Response: {
  "user_id": "uuid",
  "is_active": false,
  "message": "User status updated."
}
```

---

### SCREEN_12 — Platform Analytics

**API:** `GET /admin/analytics`
```json
Response:
{
  "total_users": 1250,
  "total_bookings": 3400,
  "average_provider_rating": 4.1,
  "active_providers_count": 210,
  "seeker_count": 820,
  "provider_count": 430,
  "seeker_to_provider_ratio": 1.91,
  "bookings_per_week": [
    { "week_start": "2026-05-05T00:00:00Z", "count": 48 },
    { "week_start": "2026-05-12T00:00:00Z", "count": 63 },
    { "week_start": "2026-05-19T00:00:00Z", "count": 71 },
    { "week_start": "2026-05-26T00:00:00Z", "count": 89 },
    { "week_start": "2026-06-02T00:00:00Z", "count": 102 },
    { "week_start": "2026-06-09T00:00:00Z", "count": 97 },
    { "week_start": "2026-06-16T00:00:00Z", "count": 115 },
    { "week_start": "2026-06-23T00:00:00Z", "count": 78 }
  ]
}
```
Use `bookings_per_week` for the bar/line chart. `seeker_to_provider_ratio` for the ratio display.

---

## 5. Background Jobs

These run automatically on the server. Frontend receives their effects via FCM or sees updated data on next API call. **No frontend action needed** — just handle the resulting FCM types.

| Job | Runs | What It Does | Frontend Effect |
|-----|------|-------------|-----------------|
| `send_booking_followup_notifications` | Every 5 min | Sends FCM to seeker at 2hr and 24hr after booking initiation | Seeker receives `BOOKING_FOLLOWUP` notification |
| `expire_stale_broadcasts` | Every 1 min | Marks expired urgent broadcasts as `EXPIRED` | Seeker receives `BROADCAST_EXPIRED` notification |
| `send_completion_prompts` | Every 1 hr | Sends FCM to seeker after work_schedule passes | Seeker receives `COMPLETION_PROMPT` notification |
| `nightly_booking_cleanup` | Midnight | Sets INITIATED bookings older than 48hr to `AUTO_EXPIRED` | Next API call shows `auto_expired` status |
| `auto_complete_stale_bookings` | 1 AM | Sets IN_PROGRESS bookings 72hr past work_schedule to `COMPLETED` | Next API call shows `completed` status, review becomes available |

---

## 6. FCM Notification Workflow

### Setup (after login on every device)
```dart
// Flutter
final token = await FirebaseMessaging.instance.getToken();
await api.post('/fcm/token', { "token": token, "device_type": "ANDROID" });
```

### All notification types and what to do on each

| `type` in data payload | Recipient | What to show | Action |
|------------------------|-----------|-------------|--------|
| `URGENT_BROADCAST` | Provider | Full-screen alert (SCREEN_30) | Open broadcast detail, show Accept button |
| `BOOKING_FOLLOWUP` | Seeker | "Did you hire [name]?" | Open SCREEN_4 with that `booking_id` |
| `COMPLETION_PROMPT` | Seeker | "Your job should be done. Tap to review." | Open SCREEN_4 → show Mark Completed button |
| `BROADCAST_CLAIMED` | Seeker | "[Provider] accepted your request." | Stop polling, show provider name on SCREEN_15 |
| `BROADCAST_EXPIRED` | Seeker | "No one responded." | Stop polling, show expired state on SCREEN_15 |
| `VERIFICATION_APPROVED` | Provider | "Your account is now verified!" | Refresh dashboard, show blue tick |

### FCM data payload structure (all notifications)
```json
{
  "type": "BOOKING_FOLLOWUP",
  "booking_id": "uuid",
  "attempt": "1"
}
```
Always read the `type` field first to determine which screen to navigate to.

### Handling notifications when app is backgrounded (Flutter)
```dart
FirebaseMessaging.onBackgroundMessage(_backgroundHandler);
FirebaseMessaging.onMessageOpenedApp.listen((message) {
  final type = message.data['type'];
  if (type == 'BOOKING_FOLLOWUP') {
    navigateTo(BookingDetailScreen(bookingId: message.data['booking_id']));
  }
  if (type == 'URGENT_BROADCAST') {
    navigateTo(UrgentAlertScreen(broadcastId: message.data['broadcast_id']));
  }
  // ... handle other types
});
```

---

## 7. API Gaps & Notes

### APIs in your Swagger that are NOT needed / redundant
- None found. All APIs in your current Swagger are used by at least one screen.

### APIs needed that are NOT yet built (backend TODO)
| Missing API | Needed For | Priority |
|-------------|-----------|----------|
| `POST /fcm/token` | Register device FCM token after login | **High** — FCM won't work without this |
| `GET /admin/verifications/{provider_id}` | Single provider detail for SCREEN_34 | Medium — can use `/admin/verifications` list for now |
| `GET /admin/verifications/counts` | Pending/approved counts for SCREEN_18 header | Low — can derive from list |
| `POST /auth/logout` | Invalidate refresh token on logout | Medium — good practice |
| `POST /reports` (seeker/provider creates a report) | Any user reporting another | Medium — you have admin moderation but no creation endpoint |

### Frontend notes

**GPS permission:** Always request location permission before any search or urgent request. If denied, show a message — the app cannot function without location.

**Cloudinary upload order:** Always upload images to Cloudinary first, get the URL and public_id, then call the backend API. Never send image files to the FastAPI backend.

**Polling stop conditions for urgent broadcast:**
```
status == "broadcasting"  → keep polling every 5 seconds
status == "claimed"       → stop, show claimed state
status == "expired"       → stop, show expired state
```

**Active booking modal trigger:**
Call `GET /bookings/seeker/last_active_initiated` on:
1. App cold start
2. App foreground (coming back from minimized)
3. After any booking initiation

**Admin panel** is web-only (React). The Flutter app does not need admin routes.

**Language header:** Every API call should include:
```
Accept-Language: bn   (for Bangla)
Accept-Language: en   (for English, or omit — default is English)
```
All error messages and category/skill names will be returned in the selected language.
