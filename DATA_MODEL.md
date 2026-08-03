# Data Model

All data lives in `src/data/` as static JSON. Schemas are in `pipeline/schemas/`.

## courses.json

| Field | Type | Notes |
|---|---|---|
| id | string | Stable slug, e.g. `pst` |
| official_name | string | Exact MCA name |
| abbreviation | string \| null | Verified abbreviation |
| aliases | string[] | Controlled alias list |
| category | string | See category list in spec |
| description | string \| null | Brief plain-English summary |
| confusion_note | string \| null | Shown when similar courses exist |
| source_pdf_url | string | Current PDF URL |
| source_updated_date | string | ISO date |
| provider_count | number | Active approvals count |
| earliest_known_date | string \| null | ISO date |
| lowest_known_price_gbp | number \| null | GBP only |

## providers.json

| Field | Type |
|---|---|
| id | string |
| official_name | string |
| alt_names | string[] |
| address | string |
| city | string |
| region | string |
| country | string (ISO 3166-1 alpha-2) |
| postcode | string \| null |
| lat / lng | number \| null |
| website | string \| null |
| email | string \| null |
| telephone | string \| null |
| not_open_to_public | boolean |

## approvals.json

| Field | Type |
|---|---|
| course_id | string |
| provider_id | string |
| source_pdf_url | string |
| source_updated_date | string |
| status | "active" \| "removed" |
| first_seen | string (ISO date) |
| last_seen | string (ISO date) |
| not_open_to_public | boolean |

## offerings.json

| Field | Type |
|---|---|
| id | string |
| course_id | string |
| provider_id | string |
| start_date | string (ISO date) |
| end_date | string (ISO date) |
| timezone | string (IANA) |
| duration_days | number \| null |
| price | number \| null |
| currency | string (ISO 4217) \| null |
| vat_included | boolean \| null |
| delivery_format | "in_person" \| "blended" \| "online" \| "unknown" |
| availability | string \| null |
| booking_url | string \| null |
| source_url | string |
| last_verified | string (ISO datetime) |
| freshness_status | "verified" \| "recently_checked" \| "stale" \| "source_unavailable" \| "no_public_schedule" |

## retrieval_log.json — array of entries

| Field | Type |
|---|---|
| source_url | string |
| retrieved_at | string (ISO datetime) |
| http_status | number \| null |
| content_hash | string \| null |
| parser_id | string |
| parse_result | "ok" \| "failed" \| "no_data" |
| error_detail | string \| null |
| offerings_found | number |
| previous_good_result_at | string \| null |

## coverage_report.json

See `pipeline/schemas/coverage_report.schema.json` for full schema.
