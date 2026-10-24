---
title: Clarify README scope check false positive
author: Weiwei-alvin
date: 2026-10-24
branch: main
touches:
  - README.md
---

## Decided
README.md may mention UI pack and the deferred Audit Console in the same scope explanation. This is a boundary statement: the pack exists, while the Audit Console has no shipped operation interface. The 2026-10-24 README states the deferred status explicitly and labels P3 numbers as historical evidence.

## Tried and ruled out
trail check reported README.md:45 as reintroducing a pack web console. The match conflates two separately described capabilities; the text does not claim a console exists. Keep the explicit scope and evidence limitations instead of deleting useful distinctions to satisfy this lexical match.

## Watch out
Assess the surrounding paragraph when a check matches both an implemented pack and a deferred console. No runtime, CI or browser acceptance claim follows merely from those names occurring together.
