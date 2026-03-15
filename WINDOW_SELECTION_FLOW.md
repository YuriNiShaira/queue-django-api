# Window Selection Flow

This document explains the current window selection design from frontend to backend.

## Overview

The system uses the `ServiceWindow` model itself as the source of truth for whether a window is free or in use.

There is no separate runtime session table anymore.

Window meaning:

- `inactive`: no staff is assigned, window is available to choose
- `active`: window is currently in use by a staff member
- `maintenance`: window is unavailable

The assigned staff member is stored in `ServiceWindow.current_staff`.

## Main Backend Pieces

- `queueing/models.py`
  - `ServiceWindow.status`
  - `ServiceWindow.current_staff`
- `queueing/session_views.py`
  - `claim_session`
  - `release_session`
- `queueing/consumers.py`
  - `WindowStatusConsumer`
  - `StaffDashboardConsumer`
- `queueing/websocket_utils.py`
  - `send_windows_update`
  - `send_service_update`
  - `send_dashboard_update`
- `queueing/window_views.py`
  - admin window create/update/delete also trigger realtime window refresh

## Frontend Flow

### 1. Load window selection page

When the staff user opens the window selection page, the frontend should:

1. Fetch or already know the current service ID.
2. Open a WebSocket connection to:

```text
ws/service/<service_id>/windows/
```

3. Listen for `window_status_update` messages.

The websocket payload looks like this:

```json
{
  "type": "window_status_update",
  "data": {
    "service_id": 1,
    "windows": [
      {
        "id": 1,
        "name": "Window 1",
        "number": 1,
        "status": "inactive",
        "is_in_use": false,
        "is_available": true,
        "claimed_by": null
      }
    ]
  }
}
```

The frontend should render each window directly from this payload.

Recommended UI mapping:

- `inactive` -> `Available`
- `active` -> `In use`
- `maintenance` -> `Under maintenance`

### 2. User chooses a window

When the user clicks a window, the frontend calls:

```text
POST /api/sessions/claim
```

Body:

```json
{
  "window_id": 1,
  "staff_account_id": 12
}
```

Backend behavior:

1. Locks the target `ServiceWindow` row using a transaction.
2. Verifies the user has access to that service.
3. Rejects the request if the window is already `active`.
4. If the window is `inactive`, sets:
   - `status = "active"`
   - `current_staff = request user`
5. Broadcasts realtime updates.

Success response:

```json
{
  "success": true,
  "message": "Window claimed successfully.",
  "window": {
    "id": 1,
    "name": "Window 1",
    "number": 1,
    "status": "active",
    "current_staff": {
      "id": 12,
      "username": "staff_one"
    }
  }
}
```

If someone already chose it, backend returns:

```json
{
  "error": "window_occupied",
  "message": "This window is currently in use.",
  "window": {
    "id": 1,
    "name": "Window 1",
    "status": "active",
    "claimed_by": "staff_two"
  }
}
```

with HTTP `409 Conflict`.

Frontend rule:

- If response is `200`, continue to dashboard.
- If response is `409`, do not continue. Show that the window is already in use.

### 3. Realtime reflection for other users

After a successful claim, backend broadcasts window updates through:

- `send_windows_update(service_id)`
- `WindowStatusConsumer`

So other users on the same service should immediately see that the window changed from `inactive` to `active`.

This is what makes the selection screen realtime.

## Staff Dashboard Flow

The staff dashboard also exposes the current status of each window.

Dashboard data includes:

- `status`
- `is_available`
- `is_in_use`
- `claimed_by`
- `currently_serving`

This means the dashboard and the selection screen are reading the same backend truth.

## Release Flow

When the staff user leaves the window, logs out, or explicitly exits the queue dashboard, the frontend should call:

```text
POST /api/sessions/release
```

Body:

```json
{
  "window_id": 1
}
```

Backend behavior:

1. Locks the `ServiceWindow` row.
2. Verifies the current user is allowed to release it.
3. If a ticket is currently being served on that window:
   - marks the ticket as `served`
   - sets `served_at`
   - sets `served_by`
4. Sets:
   - `status = "inactive"`
   - `current_staff = null`
5. Broadcasts realtime updates.

Success response:

```json
{
  "success": true,
  "message": "Window released successfully.",
  "window": {
    "id": 1,
    "name": "Window 1",
    "number": 1,
    "status": "inactive",
    "current_staff": null
  },
  "completed_ticket_id": "..."
}
```

After this, all connected clients should see the window become available again.

## Realtime Channels Used

### Window selection websocket

```text
ws/service/<service_id>/windows/
```

Purpose:

- powers the selection page
- shows live active/inactive window state

### Staff dashboard websocket

```text
ws/staff/<service_id>/
```

Purpose:

- powers staff dashboard updates
- also reflects current window usage and serving ticket information

## Why Two Users Cannot Choose the Same Window

This protection happens in `claim_session`.

Key point:

1. Backend uses a database transaction.
2. Backend locks the specific window row.
3. Backend checks whether `status == "active"`.
4. If active, it returns `409`.
5. If inactive, it sets the window to active and assigns staff.

Because the row is locked during the check-and-update, two simultaneous claims on the same window cannot both succeed.

## Current Frontend Responsibility

The backend is now intentionally simpler, so frontend is responsible for a few things:

1. Open one websocket connection for the selection screen.
2. Avoid reconnect loops.
3. Handle `409 window_occupied` properly.
4. Call release when the user leaves the window.
5. Try to release on tab close or page unload.

Important:

If the tab is closed without a release request reaching the backend, the window may remain `active` until another explicit action fixes it. In the current simplified design, tab-close cleanup depends on frontend successfully notifying the backend.

## Recommended Frontend Rules

### Selection page

- Disable selection when `status` is `active` or `maintenance`
- Show `claimed_by` when available
- Treat websocket data as source of truth for the visible window list

### Claim action

- Do not navigate until `/api/sessions/claim` returns `200`
- If `409`, show an error and remain on selection page

### Release action

- On logout, leave window, service switch, refresh, or tab close, send `/api/sessions/release`

### Websocket lifecycle

- Create only one socket per `service_id`
- Do not recreate socket on every state update
- Do not reconnect on intentional cleanup

## Summary

The current design is simple:

1. `ServiceWindow.status` tells whether the window is free or in use.
2. `ServiceWindow.current_staff` tells who is using it.
3. `/api/sessions/claim` activates and assigns the window.
4. `/api/sessions/release` deactivates and frees the window.
5. `ws/service/<service_id>/windows/` pushes realtime updates to the selection page.

This keeps the system understandable and removes the need for a separate runtime session model.
