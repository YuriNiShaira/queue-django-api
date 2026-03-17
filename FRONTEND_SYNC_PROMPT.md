Update the frontend to match the new backend window and service behavior.

Backend rules now:

1. service.is_active means the service is accepting new tickets.
2. window.status means whether a window is usable.
   - active = usable
   - inactive = disabled/unavailable
   - maintenance = unavailable
3. window.current_staff / claimed_by / is_in_use means whether a staff member is currently using that window.
4. A window is available to choose only when:
   - status is active
   - is_available is true
   - is_in_use is false
5. Claiming or releasing a window no longer changes the window status.
   It only assigns or clears current_staff.

Important frontend changes:

1. Do not treat window.status === active as "currently in use".
   Use is_in_use instead.
2. Do not disable a window just because status is active.
   Disable it only when:
   - is_in_use is true, or
   - status is inactive, or
   - status is maintenance
3. Use is_available as the main "can choose this window" flag.
4. Show claimed_by or current_staff_name in the UI when is_in_use is true.
5. Keep service ticket generation enabled based only on service.is_active.
   Do not require any claimed window before allowing customers to get tickets.
6. Staff actions like call next / call specific / start serving should only be available after the staff member has successfully claimed a window.

Relevant backend response fields:

Window payloads now expose:
- id
- name
- number or window_number
- status
- is_available
- is_in_use
- claimed_by
- current_staff
- current_staff_name

Expected UI behavior:

1. On the window selection screen:
   - show all usable windows
   - mark a window as occupied only when is_in_use is true
   - allow selection when is_available is true
2. On staff dashboard:
   - show the currently claimed window for the logged-in staff
   - prevent queue-serving actions until a window is claimed
3. On public ticket generation:
   - allow ticket creation whenever service.is_active is true, even if no staff has claimed any window yet
4. On cutoff/closing:
   - stop new tickets based on service.is_active being false
   - do not infer service closure from window occupancy

API behavior changes to account for:

1. POST /api/sessions/claim
   - succeeds when the window is usable and not already claimed by another staff member
   - returns window_occupied only when another staff member already claimed it
2. POST /api/sessions/release
   - clears current_staff but keeps the existing window status
3. Staff serving endpoints now expect the selected window to already be claimed by the logged-in staff user

Please update any window badges, button disable logic, and queue action guards to follow these rules exactly.