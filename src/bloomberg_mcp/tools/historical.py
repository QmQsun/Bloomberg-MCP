"""Historical data tools for Bloomberg API.

Provides functions to retrieve historical time series data.
"""

from typing import List

from ..core.session import BloombergSession
from ..core.requests import build_historical_data_request
from ..core.responses import HistoricalData, parse_historical_data_response


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

    Example:
        >>> data = get_historical_data(
        ...     securities=["IBM US Equity"],
        ...     fields=["PX_LAST", "VOLUME"],
        ...     start_date="20240101",
        ...     end_date="20241231",
        ...     periodicity="DAILY",
        ... )
        >>> for security in data:
        ...     for point in security.data:
        ...         print(f"{point['date']}: {point}")
    """
    # Get the Bloomberg session instance
    session = BloombergSession.get_instance()

    # Auto-connect if not connected
    if not session.is_connected():
        if not session.connect():
            raise RuntimeError("Failed to connect to Bloomberg")

    # Get the reference data service
    service = session.get_service("//blp/refdata")

    # Build the historical data request
    request = build_historical_data_request(
        service=service,
        securities=securities,
        fields=fields,
        start_date=start_date,
        end_date=end_date,
        periodicity=periodicity,
    )

    # Send the request and get response (with parser)
    results = session.send_request(
        request,
        service_name="//blp/refdata",
        parse_func=parse_historical_data_response
    )

    return results
