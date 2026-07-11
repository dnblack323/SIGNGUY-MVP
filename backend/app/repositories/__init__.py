"""Repositories package.

Convention (EC1 — Module Standard):
- One repository class per collection.
- Repositories own tenant-scoped collection access.
- Repositories own index registration.
- Routers stay thin; they call repositories or services.
- Existing MVP modules keep their inline data access unless a substantial
  rewrite is required. New or substantially rebuilt modules land here.

Do not create parallel domain models. Every module in this package uses the
shared collection schema documented in
/app/docs/architecture/module_standard.md.
"""
