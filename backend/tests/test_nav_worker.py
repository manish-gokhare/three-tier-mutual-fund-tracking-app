from decimal import Decimal

from app.nav_worker import parse_amfi_report


def test_parse_amfi_report():
    report = """
119551;Some AMC;Some Code;Aditya Birla Sun Life Flexi Cap Fund - Growth;Direct;Growth;123.456;05-Sep-2026
120503;Some AMC;Some Code;HDFC Mid-Cap Opportunities Fund - Growth;Direct;Growth;234.567;05-Sep-2026
"""

    records = parse_amfi_report(report)

    assert len(records) == 2

    first_record = records[0]

    assert first_record.scheme_code == "119551"
    assert first_record.scheme_name == "Aditya Birla Sun Life Flexi Cap Fund - Growth"
    assert first_record.plan == "Direct"
    assert first_record.option == "Growth"
    assert first_record.nav == Decimal("123.456")

    assert first_record.nav_date.year == 2026
    assert first_record.nav_date.month == 9
    assert first_record.nav_date.day == 5
