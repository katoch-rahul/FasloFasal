"""Excel lookup for the IS Claim fill module.

Loads the IS-claim workbook once and exposes a fast account-number -> values
lookup. Account numbers are normalised to bare digit strings so that values
read from the portal header match regardless of formatting / float quirks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd

import config


@dataclass(frozen=True)
class ISClaimRecord:
    account: str
    disbursal_date: str        # already formatted as config.IS_CLAIM_DATE_FORMAT
    cycle_end_date: str        # already formatted as config.IS_CLAIM_DATE_FORMAT
    applicable_is: str         # plain integer string, no separators


def _normalise_account(value) -> str:
    """Reduce any account representation to bare digits.

    Handles ints, floats that arrived as 8.7118600000022e13, and strings with
    stray spaces / decimals."""
    if value is None:
        return ""
    if isinstance(value, float):
        # avoid scientific notation and a trailing ".0"
        value = f"{value:.0f}"
    s = str(value).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return re.sub(r"\D", "", s)


def _format_date(value) -> str:
    fmt = config.IS_CLAIM_DATE_FORMAT
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.strftime(fmt)
    # fall back to pandas' parser for strings / other types
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=False)
    if pd.isna(parsed):
        return str(value).strip()
    return parsed.strftime(fmt)


def _format_amount(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (int,)):
        return str(value)
    # strip currency symbols / separators from strings like "₹1,578"
    s = re.sub(r"[^\d.-]", "", str(value))
    try:
        f = float(s)
        return str(int(f)) if f.is_integer() else str(f)
    except ValueError:
        return str(value).strip()


class ISClaimLookup:
    def __init__(self, records: dict[str, ISClaimRecord], duplicates: list[str]):
        self._records = records
        self.duplicates = duplicates

    @property
    def count(self) -> int:
        return len(self._records)

    def get(self, account) -> ISClaimRecord | None:
        return self._records.get(_normalise_account(account))

    @classmethod
    def load(cls, path: Path | str | None = None) -> "ISClaimLookup":
        # Path is supplied at runtime (user upload). Fall back to config only if
        # something is explicitly set there (normally None).
        path = path if path is not None else config.IS_CLAIM_EXCEL
        if not path:
            raise ValueError(
                "No IS-claim Excel provided - the user must upload/select the "
                "workbook before a run can start."
            )
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"IS claim Excel not found: {path}")

        # find which excel columns supply each excel-sourced field
        col_disbursal = _field_col("disbursal_date")
        col_cycle_end = _field_col("cycle_end_date")
        col_applicable = _field_col("applicable_is")
        match_col = config.IS_CLAIM_MATCH_COLUMN

        df = pd.read_excel(path, sheet_name=config.IS_CLAIM_EXCEL_SHEET)
        needed = [match_col, col_disbursal, col_cycle_end, col_applicable]
        missing = [c for c in needed if c not in df.columns]
        if missing:
            raise KeyError(
                f"Excel sheet '{config.IS_CLAIM_EXCEL_SHEET}' is missing columns: "
                f"{missing}. Found: {list(df.columns)}"
            )

        records: dict[str, ISClaimRecord] = {}
        duplicates: list[str] = []
        cols = list(df.columns)
        for row in df.itertuples(index=False, name=None):
            d = dict(zip(cols, row))
            acct = _normalise_account(d[match_col])
            if not acct:
                continue
            if acct in records:
                duplicates.append(acct)
            records[acct] = ISClaimRecord(
                account=acct,
                disbursal_date=_format_date(d[col_disbursal]),
                cycle_end_date=_format_date(d[col_cycle_end]),
                applicable_is=_format_amount(d[col_applicable]),
            )
        return cls(records, duplicates)


def _field_col(key: str) -> str:
    for f in config.IS_CLAIM_FIELDS:
        if f["key"] == key:
            return f["excel_column"]
    raise KeyError(f"No IS_CLAIM_FIELDS entry with key={key!r}")


if __name__ == "__main__":
    # Smoke test against a workbook path passed on the command line. We do NOT
    # hardcode any real account numbers here — this repo may be public.
    import sys

    if len(sys.argv) < 2:
        print("usage: python is_claim_data.py <path-to-excel>")
        raise SystemExit(2)
    lookup = ISClaimLookup.load(sys.argv[1])
    print(f"Loaded {lookup.count} accounts; {len(lookup.duplicates)} duplicate keys.")
    first = next(iter(lookup._records.values()), None)
    print(f"first record (sanity check): {first}")
