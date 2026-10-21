---
slug: production-workflow
title: Production workflow
category: production
module: production
order: 10
aliases: production-workflows, job-workflow
summary: How work moves from an approved order to a finished job, and how to configure your stages.
keywords: production, stages, workflow, work order, status, blocked, ready, completed
related: production-board, first-order, artwork-and-files, installation-and-completion
links: Production Workflows=/settings/production-workflows; Production Board=/work-orders/board
---
## The idea

Production in SIGNGUY runs on **Work Orders**. A work order is created from an order's production items and moves through stages until the job is done. There is no separate production database: the board, the list and the order all show the same work order.

## Work order statuses

Draft, released, queued, in progress, blocked, ready, completed, cancelled and superseded. Moving to *blocked* or *cancelled* requires a reason. Priority is low, normal, high or rush.

Changing a work order's status also updates the order's operational status (for example, in progress moves the order to in production). Money is never touched by a production change.

## Configure your stages

Owners and admins define stages at **Control Center > Production Workflows**. Stages are reusable definitions of the steps your shop uses, such as design, production and installation. Review them before your first real job.

## Generating and regenerating

On an order, **Generate work order** includes only items marked as needing production. If one already exists you are taken to it rather than creating a duplicate. If the order changes after release, **Regenerate** creates a new version with a reason and keeps the old one as superseded, so history is preserved.

## Tips

- Mark items that need no production (such as pure fees) so they stay off the board.
- Use *blocked* with a clear reason instead of letting a job sit silently.
