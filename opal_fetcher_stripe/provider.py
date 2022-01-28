"""
Simple fetch provider for Stripe.

This fetcher also serves as an example how to build custom OPAL Fetch Providers.
"""
from typing import Optional, List, Dict

from pydantic import BaseModel, Field
from tenacity import wait, stop, retry_unless_exception_type
from async_stripe import stripe
from stripe.error import AuthenticationError, APIConnectionError, StripeError

from opal_common.fetcher.fetch_provider import BaseFetchProvider
from opal_common.fetcher.events import FetcherConfig, FetchEvent
from opal_common.logger import logger


class StripeConnectionParams(BaseModel):
    """
    Stripe connection parameters:
    - api_ley (required): Your secret API key. You can get it from [Stripe](https://dashboard.stripe.com/test/apikeys)
    - max_network_retries (optional): Number of attempts that stripe library will do during connection
    - log_level (optional): Stripe library logging level, can be (critical,error,warning,info,debug,notset)
    - enable_telemetry (optional): By default, the library sends request latency telemetry to Stripe
    """

    api_key: str = Field(None, description="Stripe secret API key")
    max_network_retries: Optional[int] = Field(2, description="Number of fetch retries")
    log_level: Optional[str] = Field("info", description="Stripe log level")
    enable_telemetry: Optional[bool] = Field(
        True, description="Stripe latency telemetry"
    )


class StripeRequestParams(BaseModel):
    """
    Stripe request parameters:
    - stripe_account (optional): Specific Stripe version
    - stripe_version (optional): Specific Stripe connected account
    - expand (optional): List of expandable [fields](https://stripe.com/docs/api/expanding_objects)
    """

    stripe_account: Optional[str] = Field(
        None, description="Specific stripe connected account"
    )
    stripe_version: Optional[str] = Field(None, description="Specific stripe version")
    expand: Optional[List[str]] = Field(None, description="Stripe expandable fields")


class StripeFetcherConfig(FetcherConfig):
    """
    Config for StripeFetchProvider, instance of `FetcherConfig`.

    When an OPAL client receives an update, it contains a list of `DataSourceEntry` objects.
    Each `DataSourceEntry` has a `config` key - which is usually an instance of a subclass of `FetcherConfig`.

    When writing a custom provider, you must:
    - derive your class (inherit) from FetcherConfig
    - override the `fetcher` key with your fetcher class name
    - (optional): add any fields relevant to a data entry of your fetcher.
        - In this example: since we pull data from Stripe API - we added a `query` key to hold the SQL query.
    """

    fetcher: str = "StripeFetchProvider"
    connection_params: StripeConnectionParams = Field(
        ...,
        description="""
these params can override or complement parts of the dsn (connection string)
""",
    )
    request_params: Optional[StripeRequestParams] = Field(
        None,
        description="""
these params can override or complement parts of the dsn (connection string)
""",
    )


class StripeFetchEvent(FetchEvent):
    """
    A FetchEvent shape for the Stripe Fetch Provider.

    When writing a custom provider, you must create a custom FetchEvent subclass, just like this class.
    In your own class, you must set the value of the `fetcher` key to be your custom provider class name.
    """

    fetcher: str = "StripeFetchProvider"
    config: StripeFetcherConfig = None


class StripeFetchProvider(BaseFetchProvider):
    """
    An OPAL fetch provider for Stripe.

    We fetch data from a Stripe API by running a SELECT query,
    transforming the results to json and dumping the results into the policy store.

    When writing a custom provider, you must:
    - derive your provider class (inherit) from BaseFetchProvider
    - create a custom config class, as shown above, that derives from FetcherConfig
    - create a custom event class, as shown above, that derives from FetchEvent

    At minimum, your custom provider class must implement:
    - __init__() - and call super().__init__(event)
    - parse_event() - this method gets a `FetchEvent` object
    and must transform this object to *your own custom event class*.
        - Notice that `FetchEvent` is the base class
        - Notice that `StripeFetchEvent` is the custom event class
    - _fetch_() - your custom fetch method, can use the data from your event
    and config to figure out *what and how to fetch* and actually do it.
    - _process_() - if your fetched data requires some processing, you should do it here.
        - The return type from this method must be json-able, i.e: can be serialized to json.

    You may need to implement:
    - __aenter__() - if your provider has state that needs to be cleaned up,
    (i.e: http session, postgres connection, etc) the state may be initialized in this method.
    - __aexit__() - if you initialized stateful objects (i.e: acquired resources)
    in your __aenter__, you must release them in __aexit__
    """

    RETRY_CONFIG = {
        "wait": wait.wait_random_exponential(),
        "stop": stop.stop_after_attempt(10),
        "retry": retry_unless_exception_type(StripeError),
        "reraise": True,
    }

    def __init__(self, event: FetchEvent) -> None:
        """
        Fetch provider initialization, StripeFetcherConfig is required.
        """
        if event.config is None:
            logger.error("incomplete fetcher config!")
            return

        super().__init__(event)

        self._event: StripeFetchEvent  # type casting

        if self._event.config.request_params is None:
            self._event.config.request_params = StripeRequestParams()
        connection_params: dict = self._event.config.connection_params.dict(
            exclude_none=True
        )

        self._stripe = stripe

        stripe.api_key = connection_params["api_key"]

        if connection_params["max_network_retries"]:
            stripe.max_network_retries = connection_params["max_network_retries"]

        if connection_params["enable_telemetry"]:
            stripe.enable_telemetry = connection_params["enable_telemetry"]

        if connection_params["log_level"]:
            stripe.log = connection_params["log_level"]

    def parse_event(self, event: FetchEvent) -> StripeFetchEvent:
        """
        Transform `FetchEvent` object to `StripeFetchEvent` object.
        """
        return StripeFetchEvent(**event.dict(exclude={"config"}), config=event.config)

    async def _fetch_(self) -> List[any]:
        """
        Gets a list of data from Stripe using `request_params` and `url` as Stripe resource
        """
        self._event: StripeFetchEvent  # type casting

        logger.debug(f"{self.__class__.__name__} fetching from {self._url}")

        request_params: dict = self._event.config.request_params.dict(exclude_none=True)
        result = []
        try:
            fetch = getattr(stripe, self._url)
            response = await fetch.list(**request_params)
            result = response["data"]
        except AttributeError:
            logger.error("wrong stripe resource, for example 'url':'Customer'")
        except AuthenticationError:
            logger.error("wrong stripe api_key")
        except APIConnectionError as e:
            logger.error(f"stripe connection error: {e}")
        except Exception as e:
            logger.error(f"stripe fetch unhandled exception: {e}")

        return result

    @staticmethod
    def parse_invoice_lines(lines: List[any]) -> Dict[str, any]:
        """
        Parses invoice lines to get a list of products
        """
        result = {}
        for line in lines:
            result[line["price"]["product"]] = {
                "type": line["type"],
                "amount": line["amount"],
                "description": line["description"],
            }

        return result

    @staticmethod
    def update_customer_record(
        customers: Dict[str, Dict[str, any]],
        record: Dict[str, any],
        record_type: str,
        data: Dict[str, any] = None,
    ) -> None:
        """
        Create or update a item in the customer's dictionary
        """
        customer = record["customer"]
        if data is None:
            data = {record["id"]: record["status"]}
        if customer in customers:
            customers[customer][record_type].extend(data)
        else:
            customers[customer] = {
                record_type: data,
            }

    async def _process_(self, records: List[any]) -> Dict[str, any]:
        """
        Processes items from a list of records
        """
        processed_records = {}

        for record in records:
            if "customer" in record["object"]:
                processed_records[record["email"]] = {"id": record["id"]}
            elif "invoice" in record["object"]:
                if "paid" not in record["status"]:
                    continue
                self.update_customer_record(
                    customers=processed_records,
                    record=record,
                    record_type="products",
                    data=self.parse_invoice_lines(record["lines"]["data"]),
                )
            elif "subscription" in record["object"]:
                if "active" not in record["status"]:
                    continue
                self.update_customer_record(
                    processed_records, record, record_type="subscriptions"
                )
            elif "payment_intent" in record["object"]:
                if "succeeded" not in record["status"]:
                    continue
                self.update_customer_record(
                    processed_records, record, record_type="payments"
                )
            else:
                continue

        return processed_records
