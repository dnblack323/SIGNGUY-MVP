# Help article slug registry

Contract for deep links into Documentation: `/help/docs?article=<slug>`.
Frontend helper: `helpDocsPath(slug)` and `HELP_ARTICLE_SLUGS` in `frontend/src/lib/help.js`.
Backend source: `backend/app/help_content/catalog.py` (`ONBOARDING_ARTICLE_SLUGS`) and `backend/app/help_content/articles/*.md`.

Behavior: the article opens and is selected; an alias resolves to its canonical article (the URL is rewritten to the canonical slug); an unknown slug shows a friendly "could not find that article" state with a way back to Documentation.

## Stable slugs for Guided Onboarding

| Onboarding topic | Slug |
|---|---|
| Getting Started | `getting-started` |
| Company Profile | `company-profile` |
| Pricing Setup | `pricing-setup` |
| Employees and Permissions | `employees-and-permissions` |
| Production Workflow | `production-workflow` |
| Customer Portal | `customer-portal` |
| First Order | `first-order` |
| Webstore Setup | `webstore-setup` |

Slugs are never renamed. If an article must move, keep the old slug as an `aliases:` entry in its front matter.

## Aliases already supported

The onboarding task catalog (`onboarding_catalog.py`, in the Guided Onboarding branch) links to these; each resolves today.

| Alias | Resolves to |
|---|---|
| `branding` | `company-profile` |
| `production-workflows` | `production-workflow` |
| `employees` | `employees-and-permissions` |
| `shop-schedule` | `scheduling` |
| `pricing-setup-guide` | `pricing-setup` |
| `failed-subscription-guidance` | `subscription-and-billing` |

`pricing-foundation`, `invoices-and-payments`, `customers`, `orders`, `time-clock` are real article slugs.
