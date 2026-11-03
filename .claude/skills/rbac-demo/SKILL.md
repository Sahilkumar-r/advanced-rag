---
name: rbac-demo
description: Conventions for the demo auth and RBAC system. Use when editing src/ragx/auth or any protected route.
---
# RBAC demo conventions
- Roles: admin, developer, viewer, guest. Permissions: ask, ask_image, view_history, manage_memory, run_evals, view_metrics, manage_users (matrix in docs/05-BACKEND-SCHEMA.md).
- Enforce permissions server side on every route with one shared dependency; the UI only hides controls.
- argon2 hashes; JWT access 15 min, refresh 7 days stored as a hash; secrets from env.
- scripts/seed_users.py reads passwords from env and refuses short or missing ones. No passwords in any file, README or test fixture.
- Log denials and admin actions to audit_log. Write a test for every cell of the permission matrix.
- This is a demo of RBAC, not production identity. Say so in the README.
