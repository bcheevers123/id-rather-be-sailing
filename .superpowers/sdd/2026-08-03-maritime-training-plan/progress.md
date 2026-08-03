# SDD ledger — plan: docs/superpowers/plans/2026-08-03-maritime-training-plan.md

Branch: feature/maritime-training
Started: 2026-08-03

Task 1: complete (commits ba65eec..43cf1c3, review clean; minor: lxml 5.2.2→6.1.0 for Python 3.14 compat)
Task 2: complete (commit 7462963, review clean; minor deferred: broken internal path in PRODUCT_REQUIREMENTS.md cross-ref)
Task 3: complete (commit c6b90a6, review clean; minor deferred: capsys unused in test_validate_all_filters_invalid — from brief spec, not implementer error)
Task 4: complete (commit c94b9be, review clean; minor deferred: unused PdfLink import in tests, relative fixture path; lxml concern was false positive — already in requirements.txt)
Task 5: complete (commits b564491+62d2dea, fix loop R1 resolved 3 findings: _clean newline preservation, unused imports, unescaped regex dot)
Task 6: complete (commit e9636b0, review clean; minor deferred: unused timezone import in freshness.py, boundary coverage gap from brief)
Task 7: complete (commit 21c9f0d, review clean; medium deferred: offering ID truncation inherited from brief (safe at current slug lengths); low deferred: redundant £ in _PRICE_RE)
Task 8: complete (commit 9fcfe6b, review clean; medium deferred: dry_run param unused (output_dir controls safe writes per brief); low deferred: detect_changes imported but not called, unused os/MagicMock imports in test)
Task 9+10: complete (commits 8053984+0b9a9f8+caeb7ec, fix loop R1 resolved 3 findings: recently_verified sort across all offerings, 4 missing sort tests, url round-trip tests; minor deferred: hasDates:false is no-op vs undefined, tiebreaker absent in recently_verified)
