# Tasks 9 & 10 Review Report

**Reviewer:** TypeScript senior engineer
**Date:** 2026-08-03

---

## Verdicts

| | Result | Evidence |
|---|---|---|
| **Spec** | ✅ | All 7 files created; every interface, Fuse.js config key/weight/threshold, URL param name, BASE_URL path, and exported type matches the brief exactly |
| **Quality** | ❌ | `recently_verified` sort picks the wrong offering for freshness comparison; 4 of 5 sort-field branches have no tests |

---

## Findings

### Important | `src/lib/filters.ts` | `recently_verified` sort reads the wrong offering

`filterProviders` stores offerings sorted by `start_date` ascending:
```ts
const sortedOfferings = [...futureOfferings].sort((a, b) => a.start_date.localeCompare(b.start_date))
results.push({ ..., offerings: sortedOfferings, ... })
```

`sortProviderResults` then uses `offerings[0]` to determine freshness:
```ts
const aStatus = a.offerings[0]?.freshness_status ?? 'no_public_schedule'
```

`offerings[0]` is the earliest-starting offering, not the most recently verified one. A provider whose nearest run has `freshness_status: 'stale'` but whose later offerings are `'verified'` will rank lower than a provider where the nearest run happens to be `'verified'` — regardless of which data is actually fresher. The sort should use the best freshness status across all offerings (i.e. `Math.min` over `statusOrder` for each provider), or the maximum `last_verified` timestamp. As written, the sort conflates "earliest start date" with "freshness" in a way that can produce counterintuitive ordering.

---

### Important | `tests/frontend/filters.test.ts` | Only 1 of 5 sort-field branches is tested

`sortProviderResults` has five `switch` cases. The test suite only exercises `earliest_date`. The following cases have zero test coverage:

- `lowest_price` — null-last logic and numeric comparison
- `provider_name` — locale-aware string sort
- `recently_verified` — freshness-status priority map (which also has the logic issue above)
- `location` — city-name sort with null fallback

A bug in any of the untested branches (e.g. reversed null-first/null-last logic in `lowest_price`) would go undetected.

---

### Important | `tests/frontend/` | No tests for `encodeFilters` / `decodeFilters`

The global constraint explicitly states the encode/decode pair must be round-trip safe. No test file verifies this. Edge cases that lack coverage include:

- `hasDates: false` → encode → decode round-trip produces `hasDates: false` (fine), but `false` is an inert no-op in `filterProviders` (see Minor finding below) — a test would expose this disconnect
- `maxPrice: 0` — `'0'` is truthy in JS so `Number('0')` works correctly, but this is non-obvious and deserves a test
- An unknown `sortBy` value in the URL silently becomes an invalid `SortField` via `as SortField` cast with no runtime guard

---

### Minor | `src/lib/urls.ts` + `src/lib/filters.ts` | `hasDates: false` encodes to `hasDates=0` but is a filter no-op

`encodeFilters` writes `hasDates=0` when `filters.hasDates === false`. `decodeFilters` correctly reads it back as `false`. However, `filterProviders` evaluates:

```ts
if (filters.hasDates && futureOfferings.length === 0) continue
```

`false &&` short-circuits, so `hasDates: false` is functionally identical to `hasDates: undefined`. A URL containing `?hasDates=0` appears to request providers without dates but actually has no effect. Either:
- The encoding should not write `hasDates=0` (treat `false` as absent, matching its no-op behaviour), **or**
- The filter should treat `hasDates === false` as "exclude providers that have dates" with the corresponding logic

As written, the URL state `hasDates=0` is encoded but meaningless, which will confuse future developers reading the URL.

---

### Minor | `src/lib/filters.ts` | `recently_verified` sort — no tiebreaker

When two providers share the same top freshness-status ordinal, the sort is unstable (JS `Array.sort` is stable in modern engines, but there is no secondary criterion). A secondary sort by `last_verified` timestamp on the best offering would make rankings deterministic and user-visible.

---

## Clean areas

- All TypeScript interfaces are verbatim-accurate against the brief; no field names, optional/required markers, or union variants differ
- Fuse.js is imported from the package (not re-implemented); config is exact: threshold 0.3, four keys with correct weights
- `useData` correctly uses `import.meta.env.BASE_URL` and parallelises all five fetches with `Promise.all`
- `filterProviders` correctly keeps providers with zero offerings (the `hasDates` guard only fires on `true`, not absence)
- `offering.start_date >= today` ISO string comparison is correct for `YYYY-MM-DD`
- No `any` leaks, no `dangerouslySetInnerHTML`, no hardcoded `/data/` path, no unused imports
- `maxPrice` filter is GBP-scoped and the pass-through for non-GBP providers is consistent with the stated design intent

