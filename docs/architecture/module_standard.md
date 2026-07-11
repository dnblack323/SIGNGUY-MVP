# Module Standard (LOCKED — EC1)

## Backend layout

New or substantially rebuilt modules use:

```
backend/app/
  models/<module>.py       # Pydantic payloads + stored shapes
  repositories/<module>.py # Tenant-scoped collection access + index registration
  routers/<module>.py      # Thin: dep → repo/service → activity event → typed response
  services/<module>.py     # Calculations, workflows, reconciliation, cross-module
```

- **Routers stay thin.** They call repositories or services.
- **Repositories own tenant filtering** on every read + write.
- **Services own algorithms** (pricing, reconciliation, workflow engines).
- **Models define payloads** and stored shapes; every write path is typed.
- **Every new collection registers indexes** in `core/db.py::ensure_indexes()`.
- **Every write creates an audit or activity event** via `services/audit.py`.
- **No giant router files.** Split by concern.
- **No direct cross-module repository access.** Go through services.
- **No duplicated shared services** (Auth, Storage, Sequences, Audit, Email are singletons).

Existing MVP modules keep their inline data access unless a substantial rewrite is required. EC1 does not refactor stable MVP modules into repositories.

## Frontend layout

```
frontend/src/
  pages/                   # Route-level pages (default-export function per file)
  components/
    common/                # Shared cross-module UI
    forms/                 # Form primitives (MoneyInput lives here)
    layout/                # Shell / header / etc.
    <module>/              # Module-specific UI
    ui/                    # shadcn/ui (do not edit upstream shapes)
  lib/                     # api client, utils, navigation, formatting
  auth/                    # AuthContext, RequireAuth, PermissionGate
```

- **No monolithic App.js.** App.js is a router-only surface.
- **Pages > 400 lines get split.**
- **Sidebar + flyouts** live in `lib/navigation.js` (single source of truth).
- **Frontend permission checks control visibility only.** Backend enforcement is authoritative.

## Prohibited (permanent, LOCKED)

- Parallel Customer / Order / Invoice / Payment / User / Auth / Storage / Audit / Settings / Notification / Portal-identity / Entitlement systems.
- Base64-in-Mongo file storage.
- Direct payment-status mutation outside the payment service.
- Frontend-only permissions.
- Missing tenant filters or hardcoded tenant IDs.
