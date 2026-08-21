# ADR-015: Dual-Track Product System

## Status

Accepted as an additive operating layer on 2026-08-21.

## Context

The project has two failure modes: technically impressive work that never becomes a sellable product, and commercial promises that outrun engineering, security, and production evidence. The objective is to create deep, exportable value from Algeria without collapsing research, code quality, customer proof, and revenue into one uncheckable claim.

## Decision

The project adopts two explicit tracks:

1. The **Engineering/Product Track** owns architecture, implementation, standards, university evidence, security, tests, performance, observability, deployment, and runtime truth.
2. The **Production/Commercial Track** owns customer discovery, paid problem, offer boundaries, pilots, delivery economics, lawful collection, contracts/payments, renewals, and measured Algerian value.
3. Both tracks share an `alignment_id`. A capability cannot advance to production release or commercial activation when the corresponding evidence is missing.
4. Seven canonical offer lines remain in `OFFER_CATALOG.json`; they remain `PROPOSED` until verifiable customer evidence exists.
5. The executable alignment registry is `DUAL_TRACK_ALIGNMENT.json`, and `check_dual_track_alignment.py` is a required CI gate.
6. New tracks, offers, or evidence are added through new records. No existing project asset is deleted or silently replaced.

## Consequences

The system makes technical and commercial progress visible separately while preventing either side from claiming completion alone. Some research and foundation work will correctly remain non-commercial; it must state its enablement value and cannot be presented as foreign-currency revenue. Conversely, a commercial pilot must respect the engineering safety and production boundaries.

## Limitations

This decision does not create a contract, guarantee foreign-currency revenue, provide legal or tax advice, or prove employment impact. It creates a disciplined route for those claims to become provable through qualified review and evidence.
