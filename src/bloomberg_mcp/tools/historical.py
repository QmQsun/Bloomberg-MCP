"""Historical data tools for Bloomberg API.

Provides functions to retrieve historical time series data.
Requests with >BATCH_SIZE securities are automatically split into
sequential batches and merged transparently.
"""

import logging
from typing import List

from ..core.session import BloombergSession
from ..core.requests import build_historical_data_request
from ..core.responses import HistoricalData, parse_historical_data_response

logger = logging.getLogger(__name__)

BATCH_SIZE = 500


def get_historical_data(
    securities: List[str],
    fields: List[str],
    start_date: str,
    end_date: str,
    periodicity: str = "DAILY",
) -> List[HistoricalData]:
    """Get historical time series data.

    Args:
        securities: List of security identifiers (e.g., ["IBM US Equity"])
        fields: List of Bloomberg field mnemonics (e.g., ["PX_LAST", "VOLUME"])
        start_date: Start date in YYYYMMDD format (e.g., "20240101")
        end_date: End date in YYYYMMDD format (e.g., "20241231")
        periodicity: Data frequency - "DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "YEARLY"

    Returns:
        List of HistoricalData objects containing time series for each security

    Note:
        Requests with more than 500 securities are automatically batched.
    """
    session = BloombergSession.get_instance()
    if not session.is_connected():
        if not session.connect():
            raise RuntimeError("Failed to connect to Bloomberg")

    service = session.get_service("//blp/refdata")

    if len(securities) <= BATCH_SIZE:
        return _send_bdh_batch(
            session, service, securities, fields, start_date, end_date, periodicity
        )

    # Auto-batch
    all_results = []
    total_batches = (len(securities) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(securities), BATCH_SIZE):
        batch = securities[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        logger.info("BDH batch %d/%d: %d tickers", batch_num, total_batches, len(batch))

        results = _send_bdh_batch(
            session, service, batch, fields, start_date, end_date, periodicity
        )
        all_results.extend(results)

    return all_results


def _send_bdh_batch(
    session: BloombergSession,
    service,
    securities: List[str],
    fields: List[str],
    start_date: str,
    end_date: str,
    periodicity: str,
) -> List[HistoricalData]:
    """Send a single BDH request batch."""
    request = build_historical_data_request(
        service=service,
        securities=securities,
        fields=fields,
        start_date=start_date,
        end_date=end_date,
        periodicity=periodicity,
    )
    return session.send_request(
        request,
        service_name="//blp/refdata",
        parse_func=parse_historical_data_response,
    )
