# Asset Distribution

A small Django app for a family to catalog estate items, express interest in them,
and let an administrator assign each item to a person — with email notifications and
self-service password reset.

This rewrite removes the old turn-based "phase" workflow. Anyone with an account can
browse the catalog and rank their interests at any time; the administrator decides
who ultimately gets each item.

---

## Highlights

- **Real user accounts** — Django's built-in auth (PBKDF2-hashed passwords).
- **Invite-code signup** — anyone with the shared invite code can self-register.
- **Drag-to-reorder interests** — strict 1..N priority per user, no ties possible.
- **Branch-aware admin** — every user belongs to a branch (Lynn / Richard / Rob)
  so the admin can see distribution balance at a glance.
- **Self-service password reset** — Google SMTP if configured, otherwise the email
  is printed to the console for development.
- **Assignment notifications** — when the admin assigns an item, the recipient is
  emailed automatically.
- **Manual password reset** — admin can set a temporary password for any user and
  hand it over verbally as a fallback.
- **Editable disclaimers** — a welcome message appears in a modal after login
  (with a "Don't show me this again" option) and a confirmation modal appears every
  time a user clicks "I want this", reminding them they're responsible for
  arranging collection / shipping. Both messages are editable from the admin
  portal under **Disclaimers**.

---

## Quick start

```bash
# 1. Clone and enter the project
cd Asset-Distribution

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy the example env and fill in what you need
cp .env.example .env
# Edit .env — at minimum set DJANGO_SECRET_KEY.
# Email settings are optional; without them, password-reset emails print to console.

# 4. Run migrations and seed branches + categories
python manage.py migrate
python manage.py setup_initial_data

# 5. Create the first admin user
#    Either set ASSET_ADMIN_* in .env and re-run setup_initial_data,
#    or use the standard Django command:
python manage.py createsuperuser

# 6. Start the server
python manage.py runserver
```

Open http://localhost:8000/ — you'll be sent to the login page.

> **First-time admin tip:** after `createsuperuser` finishes, log in once at
> `/django-admin/` and attach a `UserProfile` (with a branch) to the new user, or
> create the admin via `setup_initial_data` instead — that command sets the profile
> automatically.

---

## How signup works

1. A prospective user visits `/signup/`.
2. They pick a username, email, password, and **branch** (Lynn / Richard / Rob).
3. They enter the **invite code** — the value of `SIGNUP_INVITE_CODE` from `.env`
   (default `reviresco`).
4. The account is created immediately. No admin approval step.

To rotate the invite code, just change `SIGNUP_INVITE_CODE` in `.env` and restart.

---

## How interests work

- On any asset detail page, click **♡ I Want This** to add it to your wishlist.
  It's appended to the bottom of your list.
- Visit **My Interests** to see your full ranked list.
- **Drag rows** by the ☰ handle to reorder. The new order saves automatically.
- Position 1 is your most-wanted item. Positions are always contiguous (1..N) and
  unique per user — you cannot tie two items.
- Removing an interest re-numbers everything below it.

---

## Admin panel

Available at `/admin-panel/` for any user with `is_staff=True`. (The Django admin
remains at `/django-admin/`.)

- **Dashboard** — totals, plus how many items each branch has been assigned.
- **Users** — list of every account, filterable by branch, with last-login,
  number of items received, and buttons to:
    - Reset the user's password manually.
    - Toggle admin (`is_staff`) status.
    - Disable/enable the account.
- **Assets** — full CRUD plus a quick-assign modal. Assigning an item triggers an
  email notification to the recipient (if email is configured).
- **Categories** — add/rename/delete (cannot delete a category that has items).
- **Interests** — view interest by item or by person.
- **Reports** — totals per category and per user; CSV export.

---

## Email setup (Google SMTP)

Email is **optional**. Without it, password-reset emails are printed to the server's
console — fine for development, useless in production.

To use Gmail/Google Workspace:

1. Enable 2-factor auth on the Google account.
2. Create an **App Password** at https://myaccount.google.com/apppasswords.
3. Set these in `.env`:
   ```
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=587
   EMAIL_USE_TLS=1
   EMAIL_HOST_USER=you@gmail.com
   EMAIL_HOST_PASSWORD=the-16-char-app-password
   DEFAULT_FROM_EMAIL=Asset Distribution <you@gmail.com>
   ```
4. Restart the server.

When `EMAIL_HOST_PASSWORD` is empty the app silently falls back to the console
backend, so the rest of the system keeps working.

If a user's email isn't deliverable they can ask the admin to use **Reset PW** in
the user list and hand the temporary password over in person.

---

## Environment variables

See [`.env.example`](.env.example) for the full list. The important ones:

| Variable | Purpose |
|----------|---------|
| `DJANGO_SECRET_KEY` | Required. Generate with `get_random_secret_key()`. |
| `DJANGO_DEBUG` | `1` for development, `0` for production. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated. Required when `DEBUG=0`. |
| `SIGNUP_INVITE_CODE` | The shared code people enter on the signup page. Default `reviresco`. |
| `ASSET_ADMIN_USERNAME` / `_PASSWORD` / `_EMAIL` / `_BRANCH` | Optional. If set, `setup_initial_data` creates this superuser with a branch profile. |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | Google SMTP credentials. Leave blank to use the console backend. |
| `DEFAULT_FROM_EMAIL` | The "From" address on outgoing mail. |

---

## Project layout

```
asset_distribution/        Django settings, root URLconf
core/                      The single app (models, views, forms, admin)
  models.py                Branch, UserProfile, Category, Asset, AssetPhoto, Interest
  views.py                 All views (auth + browsing + admin panel)
  email.py                 Best-effort send helpers
  management/commands/
    setup_initial_data.py  Branches, categories, optional bootstrap superuser
templates/
  base.html, login.html, signup.html, dashboard.html, ...
  admin/                   Admin panel templates
  registration/            Django password-reset flow templates
  email/                   Plain-text email bodies
```

---

## Data model in one paragraph

Each Django `User` has a `UserProfile` pointing at one `Branch`. `Asset`s belong to
a `Category` and may be `assigned_to` a `User`. `Interest` links a user to an asset
with a strict positive integer `position`; `(user, position)` and `(user, asset)`
are both unique, so you can never have ties or duplicate interests. There is no
turn-based state and no separate "family member" record — the admin simply assigns
items directly using the **Assign** button.

---

## Development notes

- Python 3.11+, Django 5.x, SQLite (swap `DATABASES` in `asset_distribution/settings.py`
  for production).
- After model changes: `python manage.py makemigrations core && python manage.py migrate`.
- The drag-to-reorder UI uses [SortableJS](https://github.com/SortableJS/Sortable)
  loaded from a CDN — no build step.
- Reordering is wrapped in a database transaction that first shifts every position
  to a negative offset, then assigns the final 1..N values, to avoid violating the
  `(user, position)` unique constraint mid-update.
