"""Periodically ingest official, end-of-day NAVs from AMFI's public report."""

import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from urllib.request import Request, urlopen

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from .database import SessionLocal, run_migrations
from .models import FundNav, MutualFund, NavSyncRun

AMFI_NAV_URL = os.getenv("AMFI_NAV_URL", "https://portal.amfiindia.com/spages/NAVAll.txt")
REFRESH_INTERVAL_SECONDS = max(int(os.getenv("NAV_REFRESH_INTERVAL_SECONDS", "21600")), 300)
TOKEN_RE = re.compile(r"[a-z0-9]+")
IGNORED_TOKENS = {"fund", "mutual", "plan", "option", "direct", "regular", "growth"}
# A few long-running schemes have official AMFI names that changed after their
# original branding. Each alias was verified against the AMFI complete report.
AMFI_SCHEME_ALIASES = {
    "Axis Bluechip Fund": "Axis Large Cap Fund",
    "HDFC Top 100 Fund": "HDFC Large Cap Fund",
    "SBI Bluechip Fund": "SBI LARGE & MIDCAP FUND",
    "Kotak Bluechip Fund": "Kotak Large Cap Fund",
    "Canara Robeco Bluechip Equity Fund": "Canara Robeco Large Cap Fund",
    "HDFC Mid-Cap Opportunities Fund": "HDFC Mid Cap Fund",
    "PGIM India Midcap Opportunities Fund": "PGIM India Midcap Fund",
    "SBI Magnum Midcap Fund": "SBI MIDCAP FUND",
    "Kotak Flexicap Fund": "Kotak Flexi Cap Fund",
    "JM Flexicap Fund": "JM Flexi Cap Fund",
    "Kotak Multicap Fund": "Kotak Multi Cap Fund",
    "ICICI Prudential Multicap Fund": "ICICI Prudential Multi Cap Fund",
    "Invesco India Multicap Fund": "Invesco India Multi Cap Fund",
    "Quant Active Fund": "Quant Flexi Cap Fund",
}


@dataclass(frozen=True)
class AmfiNav:
    scheme_code: str
    scheme_name: str
    plan: str
    option: str
    nav: Decimal
    nav_date: date


def normalized_tokens(value: str) -> set[str]:
    return {token for token in TOKEN_RE.findall(value.lower()) if token not in IGNORED_TOKENS}


def parse_amfi_report(report: str) -> list[AmfiNav]:
    records: list[AmfiNav] = []
    for line in report.splitlines():
        fields = [field.strip() for field in line.split(";")]
        if len(fields) < 8 or not fields[0].isdigit():
            continue
        try:
            records.append(
                AmfiNav(
                    scheme_code=fields[0],
                    scheme_name=fields[3],
                    plan=fields[4],
                    option=fields[5],
                    nav=Decimal(fields[6]),
                    nav_date=datetime.strptime(fields[7], "%d-%b-%Y").date(), # noqa: DTZ007
                )
            )
        except (InvalidOperation, ValueError):
            continue
    return records


def fetch_amfi_navs() -> list[AmfiNav]:
    request = Request(AMFI_NAV_URL, headers={"User-Agent": "MF-Tracker/1.0 (+https://amfiindia.com)"})
    with urlopen(request, timeout=45) as response:  # nosec B310 - URL is deployment configuration
        return parse_amfi_report(response.read().decode("utf-8-sig", errors="replace"))


def preference(record: AmfiNav) -> int:
    text = f"{record.plan} {record.option}".lower()
    return (2 if "direct" in text else 0) + (1 if "growth" in text else 0)


def match_score(fund_name: str, scheme_name: str) -> float:
    fund_tokens = normalized_tokens(fund_name)
    scheme_tokens = normalized_tokens(scheme_name)
    if not fund_tokens or not scheme_tokens:
        return 0.0
    coverage = len(fund_tokens & scheme_tokens) / len(fund_tokens)
    compact_fund = " ".join(sorted(fund_tokens))
    compact_scheme = " ".join(sorted(scheme_tokens))
    similarity = SequenceMatcher(None, compact_fund, compact_scheme).ratio()
    return (coverage * 0.7) + (similarity * 0.3)


def select_nav(fund: MutualFund, records: list[AmfiNav]) -> AmfiNav | None:
    if fund.amfi_scheme_code:
        code_matches = [record for record in records if record.scheme_code == fund.amfi_scheme_code]
        if code_matches:
            return max(code_matches, key=preference)

    alias = AMFI_SCHEME_ALIASES.get(fund.fund_name)
    if alias:
        alias_matches = [record for record in records if record.scheme_name.lower() == alias.lower()]
        if alias_matches:
            return max(alias_matches, key=preference)

    candidates = []
    for record in records:
        score = match_score(fund.fund_name, record.scheme_name)
        if score >= 0.76:
            candidates.append((score, preference(record), record))
    return max(candidates, default=None, key=lambda item: (item[0], item[1]))[2] if candidates else None


def run_sync() -> tuple[int, int]:
    session = SessionLocal()
    run = NavSyncRun(status="running")
    session.add(run)
    session.commit()
    try:
        records = fetch_amfi_navs()
        funds = session.scalars(select(MutualFund)).all()
        matched = 0
        claimed_scheme_codes = {fund.amfi_scheme_code for fund in funds if fund.amfi_scheme_code}
        for fund in funds:
            record = select_nav(fund, records)
            if record is None or (record.scheme_code in claimed_scheme_codes and record.scheme_code != fund.amfi_scheme_code):
                continue
            # Once matched, pin the official AMFI scheme code instead of relying
            # on a fuzzy name comparison on every later refresh.
            fund.amfi_scheme_code = record.scheme_code
            claimed_scheme_codes.add(record.scheme_code)
            upsert = insert(FundNav).values(
                fund_id=fund.id,
                nav_date=record.nav_date,
                nav=record.nav,
                nav_source="amfi",
            ).on_conflict_do_update(
                constraint="uq_fund_nav_date",
                set_={"nav": record.nav, "nav_source": "amfi"},
            )
            session.execute(upsert)
            matched += 1
        run.status = "success"
        run.completed_at = func.now()
        run.matched_funds = matched
        run.fetched_records = len(records)
        session.commit()
        return matched, len(records)
    except Exception as error:
        session.rollback()
        failed_run = session.get(NavSyncRun, run.id)
        if failed_run is not None:
            failed_run.status = "failed"
            failed_run.completed_at = func.now()
            failed_run.error_message = str(error)[:1000]
            session.commit()
        raise
    finally:
        session.close()


def main() -> None:
    run_migrations()
    while True:
        try:
            matched, total = run_sync()
            print(f"AMFI NAV sync succeeded: {matched} tracked funds matched from {total} records", flush=True)
        except Exception as error: # noqa: BLE001
            print(f"AMFI NAV sync failed: {error}", flush=True)
        time.sleep(REFRESH_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
