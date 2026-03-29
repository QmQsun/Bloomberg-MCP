"""Reference data tools for Bloomberg API.

Provides functions to retrieve current field values for securities.
Requests with >BATCH_SIZE securities are automatically split into
sequential batches and merged transparently.
"""

import logging
from typing import Any, Dict, List, Optional

from ..core.session import BloombergSession
from ..core.requests import build_reference_data_request
from ..core.responses import SecurityData, parse_reference_data_response

logger = logging.getLogger(__name__)

BATCH_SIZE = 500


def get_reference_data(
    securities: List[str],
    fields: List[str],
    overrides: Optional[Dict[str, Any]] = None,
) -> List[SecurityData]:
    """Get current field values for securities.

    Args:
        securities: List of security identifiers (e.g., ["IBM US Equity", "AAPL US Equity"])
        fields: List of Bloomberg field mnemonics (e.g., ["PX_LAST", "NAME"])
        overrides: Optional field overrides as key-value pairs

    Returns:
        List of SecurityData objects containing field values for each security

    Note:
        Requests with more than 500 securities are automatically batched.
    """
    session = BloombergSession.get_instance()
    if not session.is_connected():
        if not session.connect():
            raise RuntimeError("Failed to connect to Bloomberg")

    service = session.get_service("//blp/refdata")

    if len(securities) <= BATCH_SIZE:
        return _send_bdp_batch(session, service, securities, fields, overrides)

    # Auto-batch
    all_results = []
    total_batches = (len(securities) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(securities), BATCH_SIZE):
        batch = securities[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        logger.info("BDP batch %d/%d: %d tickers", batch_num, total_batches, len(batch))

        results = _send_bdp_batch(session, service, batch, fields, overrides)
        all_results.extend(results)

    return all_results


def _send_bdp_batch(
    session: BloombergSession,
    service,
    securities: List[str],
    fields: List[str],
    overrides: Optional[Dict[str, Any]] = None,
) -> List[SecurityData]:
    """Send a single BDP request batch."""
    request = build_reference_data_request(
        service=service,
        securities=securities,
        fields=fields,
        overrides=overrides,
    )
    return session.send_request(
        request,
        service_name="//blp/refdata",
        parse_func=parse_reference_data_response,
    )
