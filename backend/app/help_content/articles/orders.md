---
slug: orders
title: Orders and order items
category: customers_sales
module: orders
order: 40
aliases: order-items
summary: How orders and their items work, what the tabs hold, and how statuses behave.
keywords: order, order item, status, totals, manual override, production required, work order
related: first-order, quotes, production-workflow, invoices-and-payments
links: Orders=/orders
---
An **order** is the record of a customer's job. Its **order items** are the individual things being made or done.

## Creating orders

- **New order** on the Orders page creates an order directly.
- **Convert to order** on an approved quote creates the order from the quote and keeps the link back to it.

## Order items

Each item has a category, description, quantity, size, material and price. Totals for each item and for the order are always calculated by the system from the items.

- Changing an item's price requires a **reason**, which is recorded.
- Each item says whether it **needs production**. Defaults come from the category; overriding the default also needs a reason.
- Pricing details used at the time are kept with the item so later settings changes do not rewrite it.

## Order detail tabs

Overview, Order Items, Production, Files & Artwork, Documents & Approvals, Financial, Completion & Comms and Activity. The lifecycle timeline and readiness check sit on the overview.

## Statuses

Order status describes the work only: draft, confirmed, in production, ready, completed, cancelled and archived. Payment is never an order status; see the invoice for money.

Completed orders are protected from accidental financial changes. Use the *Issues and rework* section to open an issue instead.
