from __future__ import annotations


class FilingAdapter:
    """SEC/OpenDART filing adapter placeholder.

    US:
      - SEC EDGAR submissions/companyfacts JSON.
    Korea:
      - OpenDART disclosures and financial statements.
    """

    def fetch_recent_filings(self, ticker: str, days: int = 30) -> list[dict]:
        raise NotImplementedError
