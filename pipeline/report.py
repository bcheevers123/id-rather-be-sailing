from datetime import datetime, timezone


def build_coverage_report(
    courses: list[dict],
    providers: list[dict],
    approvals: list[dict],
    offerings: list[dict],
    parse_failures: list[dict],
) -> dict:
    provider_ids_with_dates = {o["provider_id"] for o in offerings if o.get("start_date")}
    provider_ids_with_prices = {o["provider_id"] for o in offerings if o.get("price") is not None}

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_courses": len(courses),
        "total_providers": len(providers),
        "total_approvals": len(approvals),
        "providers_with_dates": len(provider_ids_with_dates),
        "providers_with_prices": len(provider_ids_with_prices),
        "providers_requiring_manual_review": 0,
        "providers_blocking_automated_collection": 0,
        "providers_no_public_schedule": len(providers) - len(provider_ids_with_dates),
        "last_successful_full_refresh": datetime.now(timezone.utc).isoformat(),
        "parse_failures": parse_failures,
    }
