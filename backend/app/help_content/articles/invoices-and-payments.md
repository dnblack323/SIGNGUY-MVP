---
slug: invoices-and-payments
title: Invoices, deposits and payments
category: customers_sales
module: invoices
order: 60
aliases: invoices, payments
summary: Create an invoice from an order, record payments, and understand deposits, partial payments and voids.
keywords: invoice, payment, deposit, balance, refund, void, record payment, partial, stripe
related: orders, customer-portal, finances-and-expenses, troubleshooting
links: Invoices=/invoices
---
## Creating an invoice

Open an order and select **Create invoice**. There is **one invoice per order**. Email it with **Email invoice**; customers can also see it in the Customer Portal.

## Two statuses

- **Document status:** draft, issued or void. A draft can still be edited.
- **Financial status:** unpaid, partial, paid, refunded or voided. This is calculated from the payments; you cannot set an invoice to "paid" by hand.

## Recording payments

On the invoice select **Record payment** and enter the amount, method and any reference. Rules:

- The amount must be positive and cannot exceed the balance.
- A mistake in a manual payment can be **voided** with a reason.
- Voiding an invoice that has confirmed payments is blocked.

The **Payment history** shows every payment and the balance.

## Deposits

An order can require a deposit, or payment, before production. Until enough payment is recorded on its invoice, the order's readiness check shows a *deposit required* blocker. Record the payment and the blocker clears.

## Online payments

Customers can pay online only if your payment integration is connected and enabled for your shop. If it is not, record the payment manually. Online payments can be refunded from the payment record with a reason.
