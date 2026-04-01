"""Bloomberg API session management with singleton pattern.

Includes concurrency control (semaphore), queue depth limiting,
and automatic reconnection on session drop.
"""

import logging
import threading
import time
from typing import List, Optional, Dict, Any

import blpapi

logger = logging.getLogger(__name__)

# Concurrency limits
_MAX_CONCURRENT_REQUESTS = 8
_MAX_QUEUE_DEPTH = 32
_RECONNECT_MAX_RETRIES = 3
_RECONNECT_BACKOFF_BASE = 5  # seconds

from .responses import (
    parse_reference_data_response,
    parse_historical_data_response,
    parse_intraday_bar_response,
    SecurityData,
    HistoricalData,
    IntradayBar,
)


class BloombergSession:
    """
    Singleton session manager for Bloomberg API connections.

    This class manages the lifecycle of a Bloomberg API session, including
    connection, service opening, and request/response handling.
    """

    _instance: Optional["BloombergSession"] = None
    _lock = threading.Lock()

    def __new__(cls, host: str = "localhost", port: int = 8194):
        """Ensure only one instance of BloombergSession exists."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, host: str = "localhost", port: int = 8194):
        """
        Initialize Bloomberg session.

        Args:
            host: Bloomberg API host (default: localhost)
            port: Bloomberg API port (default: 8194)
        """
        # Only initialize once
        if hasattr(self, "_initialized"):
            return

        self._host = host
        self._port = port
        self._session: Optional[blpapi.Session] = None
        self._services: Dict[str, blpapi.Service] = {}
        self._connected = False
        self._initialized = True

        # Concurrency control
        self._semaphore = threading.Semaphore(_MAX_CONCURRENT_REQUESTS)
        self._queue_depth = 0
        self._queue_lock = threading.Lock()

    @classmethod
    def get_instance(cls, host: str = "localhost", port: int = 8194) -> "BloombergSession":
        """
        Get the singleton instance of BloombergSession.

        Args:
            host: Bloomberg API host (default: localhost)
            port: Bloomberg API port (default: 8194)

        Returns:
            The singleton BloombergSession instance
        """
        if cls._instance is None:
            cls._instance = cls(host, port)
        return cls._instance

    def connect(self) -> bool:
        """
        Establish connection to Bloomberg API.

        Returns:
            True if connection successful, False otherwise
        """
        if self._connected:
            return True

        try:
            # Create session options
            session_options = blpapi.SessionOptions()
            session_options.setServerHost(self._host)
            session_options.setServerPort(self._port)

            # Create and start session
            self._session = blpapi.Session(session_options)

            if not self._session.start():
                logger.error("Failed to start Bloomberg session")
                return False

            self._connected = True
            return True

        except Exception as e:
            logger.error("Error connecting to Bloomberg API: %s", e)
            return False

    def disconnect(self) -> None:
        """Close the Bloomberg API session."""
        if self._session is not None:
            try:
                self._session.stop()
            except Exception as e:
                logger.error("Error disconnecting from Bloomberg API: %s", e)
            finally:
                self._session = None
                self._services.clear()
                self._connected = False

    def is_connected(self) -> bool:
        """
        Check if session is connected.

        Returns:
            True if connected, False otherwise
        """
        return self._connected and self._session is not None

    def get_service(self, service_name: str) -> Optional[blpapi.Service]:
        """
        Get a Bloomberg service, opening it if necessary.

        Args:
            service_name: Name of the service (e.g., "//blp/refdata")

        Returns:
            Service object or None if service cannot be opened
        """
        if not self.is_connected():
            raise RuntimeError("Session is not connected. Call connect() first.")

        # Return cached service if available
        if service_name in self._services:
            return self._services[service_name]

        # Open the service
        try:
            if not self._session.openService(service_name):
                logger.error("Failed to open service: %s", service_name)
                return None

            service = self._session.getService(service_name)
            self._services[service_name] = service
            return service

        except Exception as e:
            logger.error("Error opening service %s: %s", service_name, e)
            return None

    def send_request(
        self,
        request: blpapi.Request,
        service_name: str,
        parse_func=None
    ) -> List[Any]:
        """
        Send a request and wait for response synchronously.

        Includes concurrency control (semaphore + queue depth limit)
        and automatic reconnection on session termination.

        Args:
            request: Bloomberg API request object
            service_name: Name of the service being used
            parse_func: Optional function to parse response messages

        Returns:
            List of parsed response objects
        """
        if not self.is_connected():
            raise RuntimeError("Session is not connected. Call connect() first.")

        # Queue depth check
        with self._queue_lock:
            if self._queue_depth >= _MAX_QUEUE_DEPTH:
                raise RuntimeError(
                    f"Bloomberg request queue full ({_MAX_QUEUE_DEPTH} pending). "
                    "Too many concurrent requests — retry later."
                )
            self._queue_depth += 1

        try:
            # Acquire semaphore (blocks if at max concurrency)
            self._semaphore.acquire()
            try:
                return self._send_request_impl(request, service_name, parse_func)
            finally:
                self._semaphore.release()
        finally:
            with self._queue_lock:
                self._queue_depth -= 1

    def _send_request_impl(
        self,
        request: blpapi.Request,
        service_name: str,
        parse_func=None
    ) -> List[Any]:
        """Internal: send request without concurrency guards."""
        results = []

        try:
            # Send request
            self._session.sendRequest(request)

            # Wait for response
            done = False
            while not done:
                event = self._session.nextEvent(timeout=30000)  # 30 second timeout
                event_type = event.eventType()

                if event_type == blpapi.Event.PARTIAL_RESPONSE:
                    # Process partial response
                    for msg in event:
                        if parse_func:
                            parsed = parse_func(msg)
                            if isinstance(parsed, list):
                                results.extend(parsed)
                            else:
                                results.append(parsed)
                        else:
                            results.append(msg.toPy())

                elif event_type == blpapi.Event.RESPONSE:
                    # Process final response
                    for msg in event:
                        if parse_func:
                            parsed = parse_func(msg)
                            if isinstance(parsed, list):
                                results.extend(parsed)
                            else:
                                results.append(parsed)
                        else:
                            results.append(msg.toPy())
                    done = True

                elif event_type == blpapi.Event.REQUEST_STATUS:
                    # Handle request failure
                    for msg in event:
                        if msg.messageType() == blpapi.Names.REQUEST_FAILURE:
                            reason = msg.getElement(blpapi.Name("reason"))
                            raise RuntimeError(f"Request failed: {reason}")
                    done = True

                elif event_type == blpapi.Event.TIMEOUT:
                    raise TimeoutError("Request timed out")

                elif event_type == blpapi.Event.SESSION_STATUS:
                    # Check for session termination
                    for msg in event:
                        if msg.messageType() in (
                            blpapi.Names.SESSION_TERMINATED,
                            blpapi.Names.SESSION_STARTUP_FAILURE,
                        ):
                            self._connected = False
                            raise RuntimeError("Session terminated")

        except Exception as e:
            logger.error("Error sending request: %s", e)
            raise

        return results

    def reconnect(self) -> bool:
        """Attempt to reconnect to Bloomberg after session drop.

        Tries up to _RECONNECT_MAX_RETRIES with exponential backoff.

        Returns:
            True if reconnection succeeded
        """
        logger.info("Attempting Bloomberg session reconnection...")
        self._connected = False

        if self._session is not None:
            try:
                self._session.stop()
            except Exception:
                pass
            self._session = None
        self._services.clear()

        for attempt in range(1, _RECONNECT_MAX_RETRIES + 1):
            try:
                session_options = blpapi.SessionOptions()
                session_options.setServerHost(self._host)
                session_options.setServerPort(self._port)
                self._session = blpapi.Session(session_options)

                if self._session.start():
                    self._connected = True
                    logger.info(
                        "Bloomberg session reconnected on attempt %d", attempt
                    )
                    return True
            except Exception as e:
                logger.warning(
                    "Reconnect attempt %d/%d failed: %s",
                    attempt, _RECONNECT_MAX_RETRIES, e,
                )

            backoff = _RECONNECT_BACKOFF_BASE * attempt
            time.sleep(backoff)

        logger.error(
            "Bloomberg session reconnect failed after %d attempts",
            _RECONNECT_MAX_RETRIES,
        )
        return False

    def get_reference_data(
        self,
        securities: List[str],
        fields: List[str],
        overrides: Optional[Dict[str, Any]] = None
    ) -> List[SecurityData]:
        """
        Get reference data for securities.

        Args:
            securities: List of security identifiers
            fields: List of field names to retrieve
            overrides: Optional dict of field overrides

        Returns:
            List of SecurityData objects
        """
        service = self.get_service("//blp/refdata")
        if service is None:
            raise RuntimeError("Failed to open reference data service")

        request = service.createRequest("ReferenceDataRequest")

        # Add securities
        securities_element = request.getElement("securities")
        for security in securities:
            securities_element.appendValue(security)

        # Add fields
        fields_element = request.getElement("fields")
        for field in fields:
            fields_element.appendValue(field)

        # Add overrides if provided
        if overrides:
            overrides_element = request.getElement("overrides")
            for field_id, value in overrides.items():
                override = overrides_element.appendElement()
                override.setElement("fieldId", field_id)
                override.setElement("value", value)

        return self.send_request(request, "//blp/refdata", parse_reference_data_response)

    def get_historical_data(
        self,
        securities: List[str],
        fields: List[str],
        start_date: str,
        end_date: str,
        periodicity: str = "DAILY",
        **kwargs
    ) -> List[HistoricalData]:
        """
        Get historical data for securities.

        Args:
            securities: List of security identifiers
            fields: List of field names to retrieve
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            periodicity: Data periodicity (DAILY, WEEKLY, MONTHLY, etc.)
            **kwargs: Additional request parameters

        Returns:
            List of HistoricalData objects
        """
        service = self.get_service("//blp/refdata")
        if service is None:
            raise RuntimeError("Failed to open reference data service")

        request = service.createRequest("HistoricalDataRequest")

        # Add securities
        request["securities"] = securities

        # Add fields
        request["fields"] = fields

        # Set date range
        request["startDate"] = start_date
        request["endDate"] = end_date

        # Set periodicity
        request["periodicitySelection"] = periodicity

        # Add any additional parameters
        for key, value in kwargs.items():
            request[key] = value

        return self.send_request(request, "//blp/refdata", parse_historical_data_response)

    def get_intraday_bars(
        self,
        security: str,
        event_type: str,
        start_datetime: str,
        end_datetime: str,
        interval: int = 60
    ) -> Optional[IntradayBar]:
        """
        Get intraday bar data for a security.

        Args:
            security: Security identifier
            event_type: Type of event (TRADE, BID, ASK, etc.)
            start_datetime: Start datetime in format "YYYY-MM-DDThh:mm:ss"
            end_datetime: End datetime in format "YYYY-MM-DDThh:mm:ss"
            interval: Bar interval in minutes (default: 60)

        Returns:
            IntradayBar object or None if error
        """
        service = self.get_service("//blp/refdata")
        if service is None:
            raise RuntimeError("Failed to open reference data service")

        request = service.createRequest("IntradayBarRequest")

        # Only one security per request
        request.set("security", security)
        request.set("eventType", event_type)
        request.set("interval", interval)
        request.set("startDateTime", start_datetime)
        request.set("endDateTime", end_datetime)

        results = self.send_request(request, "//blp/refdata", parse_intraday_bar_response)

        return results[0] if results else None

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
