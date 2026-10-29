# Changelog

## 1.0.0 (2026-10-28)

First public release.

- Three pyRevit buttons: Export MEP, Compare Models, Issue Shots.
- Geometry-based matching of two independently built models: segments by both endpoints
  (direction-agnostic), components by insertion point, never across disciplines.
- Disciplines: ducts, pipes, cable trays, conduits, plus terminals, sprinklers and equipment.
- Segments shifted sideways within 1 m are reported as moved, not as missing plus extra.
- Same family with a different family type (e.g. 45° vs 80° transition) is reported as a type mismatch.
- Centerline coverage per discipline, independent of how runs are split.
- Detects non-reference families in the model under test.
- Side-by-side issue screenshots with section boxes, issue elements colored, other elements greyed.
- English and Traditional Chinese UI, following pyRevit's language setting.
- Synthetic sample data with seeded differences, unit tests and CI.
