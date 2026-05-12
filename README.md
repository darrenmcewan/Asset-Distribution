# Asset Distribution

A small Django app for a family to catalog estate items, express interest in them,
and let an administrator assign each item to a person — with email notifications and
self-service password reset.

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
