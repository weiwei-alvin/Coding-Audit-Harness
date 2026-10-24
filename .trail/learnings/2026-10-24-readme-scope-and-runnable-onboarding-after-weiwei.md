---
title: README scope and runnable onboarding after P3
author: Weiwei-alvin
date: 2026-10-24
branch: main
touches:
  - README.md
  - milestone.md
  - PLAN.md
  - SPEC.md
  - requirements.txt
---

## Decided
The current public README describes the Runner kernel and optional UI pack. V2 means UI Design Integration in milestone.md; PLAN.md and SPEC.md describe the deferred Audit Console. The bundled ui-pack starts at DISCOVERY and uses DESIGN as the actual stage ID. code-default starts at TICKETS. Conditional DESIGN enforces a gate guard and does not implement automatic stage skipping.

## Tried and ruled out
Do not describe the UI pack as an existing Web Console, or historical P3 acceptance as a fresh test run. Contract validation and UI review PASS alone retain ui_acceptance=UNVERIFIED. Full UI E2E requires browser setup and prior evidence; kernel CI does not run it.

## Watch out
The calculator onboarding needs both harness/ and requirements.txt copied into its new target directory, plus calc.py before verification. README review examples need the final integration criterion for the one-ticket walkthrough. Verify runnable documentation in an isolated target and keep generated evidence under ignored test-results/.
