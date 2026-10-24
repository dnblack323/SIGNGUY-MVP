---
slug: first-order
title: Creating your first order
category: customers_sales
module: orders
order: 30
summary: Run one job end to end to prove your setup: customer, order, items, work order, invoice, payment.
keywords: first order, new order, create order, test job, walkthrough, tutorial
related: orders, quotes, production-workflow, invoices-and-payments
links: Customers=/customers; Orders=/orders; Production Board=/work-orders/board
---
The fastest way to learn SIGNGUY is to run one realistic job.

## Steps

1. **Add a customer** at *Customers > New customer*.
2. **Create the order.** At *Sales > Orders* select **New order** to create one directly, or approve a quote and use **Convert to order**.
3. **Add order items.** Describe each item with category, quantity, size and price. Mark which items need production.
4. **Attach artwork.** Use the order's *Files & Artwork* tab.
5. **Generate the work order.** On the order, select **Generate work order**. Only production items are included.
6. **Move it through production.** Open the [Production Board](/help/docs?article=production-board) and advance the stages.
7. **Invoice and collect.** Select **Create invoice** on the order, then record the payment on the invoice. See [Invoices and payments](/help/docs?article=invoices-and-payments).

## What to check

- The order total is calculated by the system from its items; you cannot type over it.
- The work order stays frozen as released, so later order edits do not silently change production.
- The invoice shows its balance and payment history.

If something is blocked, the order's readiness check lists the reasons, such as a missing approval or a deposit not yet received.
