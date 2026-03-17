# Window Selection Flow

This document explains the current window selection design from frontend to backend.

## Overview

The system uses `ServiceWindow` as the source of truth for both window usability and current ownership.

There is no separate runtime session table.

Window meaning:

- `status` = usability state
  - `active`: window is usable for queue operations
  - `inactive`: window is disabled/unavailable
  - `maintenance`: window is unavailable
- `current_staff` = who currently owns the window claim
- `is_in_use` = whether the window is currently claimed (`current_staff` is set)
- `is_available` = whether the window can be claimed now (`status == active` and unclaimed)

Important behavior:

- Claiming a window sets `current_staff` only.
- Releasing a window clears `current_staff` only.
- Claim/release no longer changes `status`.
- Service ticket availability is controlled by `service.is_active`, not by window occupancy.

## Main Backend Pieces

- `queueing/models.py`
  - `Service.is_active`
  - `ServiceWindow.status`
  - `ServiceWindow.current_staff`
  - `ServiceWindow.is_available`
  - `ServiceWindow.is_in_use`
- `queueing/session_views.py`
  - `claim_session`
  - `release_session`
- `queueing/staff_views.py`
  - staff serving endpoints require the user to have claimed the selected window
- `queueing/consumers.py`
  - `WindowStatusConsumer`
  - `StaffDashboardConsumer`
- `queueing/websocket_utils.py`
  - `send_windows_update`
  - `send_service_update`
  - `send_dashboard_update`

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
        "status": "active",
        "is_in_use": false,
        "is_available": true,
        "claimed_by": null
      }
    ]
  }
}
```

Recommended UI mapping:

- `status == active && is_in_use == false` -> `Available`
- `status == active && is_in_use == true` -> `Occupied`
- `status == inactive` -> `Unavailable`
- `status == maintenance` -> `Under maintenance`

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
3. Rejects the request when the window is not usable (`status != active`).
4. Rejects with `window_occupied` only when another staff user already claimed it.
5. If the same staff user already claimed it, returns success (idempotent claim).
6. Otherwise sets `current_staff = request.user`.
7. Broadcasts realtime updates.

Success response example:

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

Conflict example:

```json
{
  "error": "window_occupied",
  "message": "This window is currently in use by another staff account.",
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
- If response is `409`, show that the window is occupied and stay on selection.
- If response is `400 window_unavailable`, show that the window cannot be selected.

### 3. Realtime reflection for other users

After a successful claim/release, backend broadcasts window updates through:

- `send_windows_update(service_id)`
- `WindowStatusConsumer`

So other users on the same service immediately see changes to `is_in_use`, `is_available`, and `claimed_by`.

## Staff Dashboard Flow

Dashboard data includes:

- `status`
- `is_available`
- `is_in_use`
- `claimed_by`
- `currently_serving`

Staff queue-serving actions should be enabled only when the logged-in user has claimed the selected window.

## Release Flow

When the staff user leaves a window, logs out, or explicitly exits the queue dashboard, the frontend should call:

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
2. Verifies release permissions.
3. If the window is not currently claimed, returns `session_not_found`.
4. If a ticket is currently being served on that window:
   - marks the ticket as `served`
   - sets `served_at`
   - sets `served_by`
5. Clears `current_staff`.
6. Keeps `status` unchanged.
7. Broadcasts realtime updates.

## Realtime Channels Used

### Window selection websocket

```text
ws/service/<service_id>/windows/
```

Purpose:

- powers the selection page
- shows live window usability and occupancy

### Staff dashboard websocket

```text
ws/staff/<service_id>/
```

Purpose:

- powers staff dashboard updates
- reflects current window occupancy and serving information

## Why Two Users Cannot Choose the Same Window

This protection happens in `claim_session`.

Key point:

1. Backend uses a database transaction.
2. Backend locks the specific window row.
3. Backend checks whether another staff already owns `current_staff`.
4. If owned by someone else, it returns `409`.
5. If unclaimed, it assigns the requester.

Because the row is locked during check-and-assign, two simultaneous claims on the same window cannot both succeed.

## Current Frontend Responsibility

1. Open one websocket connection for the selection screen.
2. Handle `is_available`, `is_in_use`, and `status` distinctly.
3. Handle `409 window_occupied` and `400 window_unavailable` properly.
4. Call release when the user leaves the claimed window.
5. Attempt release on tab close/page unload where possible.

## Summary

1. `ServiceWindow.status` describes usability, not occupancy.
2. `ServiceWindow.current_staff` and `is_in_use` describe occupancy.
3. `/api/sessions/claim` assigns staff ownership of a usable window.
4. `/api/sessions/release` clears ownership but keeps window status.
5. `ws/service/<service_id>/windows/` pushes realtime selection-state updates.