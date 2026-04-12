"""ClinicalTrials.gov API v2 client.

This module is the ONE place in the codebase that talks to CT.gov. Everything
else takes parsed dicts or model instances — the HTTP layer is sealed here.

Design notes:
- Uses `requests` (not httpx) because CT.gov blocks httpx's TLS fingerprint
- Synchronous — the ETL is a batch job, not a hot path, so we don't need async
- Paginates via nextPageToken as CT.gov returns it
- Retries on transient errors (5xx, network timeouts) with exponential backoff
- Fail loud on 4xx (our bug) but retry on 5xx (their bug)

The CT.gov API is free and doesn't require a key, but they ask you to send a
descriptive User-Agent. We include an email address so they can reach us if
our ETL misbehaves — being a good citizen is cheap insurance.
"""

import logging
import time
from typing import Iterator, Optional

import requests

from app.config import settings

logger = logging.getLogger(__name__)


class CTGovAPIError(Exception):
    """Raised when CT.gov returns something we can't work with.

    Wrapping upstream errors in our own exception type makes it easy to catch
    "CT.gov problems" at the ETL boundary without accidentally catching
    bugs in our own code.
    """


class CTGovClient:
    """Minimal synchronous client for the CT.gov v2 REST API.

    Usage:
        client = CTGovClient()

        # Fetch one trial
        trial = client.get_study("NCT04280705")

        # Paginate search results
        for trial in client.search_studies(condition="cardiovascular"):
            process(trial)
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        user_agent: Optional[str] = None,
        page_size: Optional[int] = None,
        max_retries: int = 3,
        backoff_seconds: float = 2.0,
    ):
        self.base_url = (base_url or settings.ctgov_api_base).rstrip("/")
        self.user_agent = user_agent or settings.ctgov_user_agent
        self.page_size = page_size or settings.ctgov_fetch_page_size
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds

        self._session = requests.Session()
        self._session.headers.update({"User-Agent": self.user_agent})

    # -------------------------------------------------------------------------
    # Public methods
    # -------------------------------------------------------------------------

    def get_study(self, nct_id: str) -> dict:
        """Fetch a single study by NCT ID. Returns the full raw API response dict.

        Raises CTGovAPIError if CT.gov returns a non-200 status after retries.
        """
        url = f"{self.base_url}/studies/{nct_id}"
        return self._request_json(url, params={"format": "json"})

    def search_studies(
        self,
        condition: Optional[str] = None,
        intervention: Optional[str] = None,
        location: Optional[str] = None,
        sponsor: Optional[str] = None,
        status: Optional[list[str]] = None,
        phase: Optional[list[str]] = None,
        study_type: Optional[str] = None,
        advanced_query: Optional[str] = None,
        fields: Optional[list[str]] = None,
        updated_since: Optional[str] = None,
        updated_before: Optional[str] = None,
    ) -> Iterator[dict]:
        """Search studies with pagination. Yields one study dict at a time.

        The CT.gov API paginates via nextPageToken; we follow it automatically
        so callers just iterate. If a caller needs only the first N, they can
        break out of the loop at any point.

        All search parameters are optional; leaving them all None returns
        every trial in the registry (not recommended — use filters).
        """
        url = f"{self.base_url}/studies"
        params: dict = {
            "format": "json",
            "pageSize": self.page_size,
            "countTotal": "true",
        }

        # Free-text query parameters — CT.gov uses dotted names like query.cond
        if condition:
            params["query.cond"] = condition
        if intervention:
            params["query.intr"] = intervention
        if location:
            params["query.locn"] = location
        if sponsor:
            params["query.lead"] = sponsor
        if advanced_query:
            params["query.term"] = advanced_query

        # Date range filter — uses filter.advanced with AREA[LastUpdatePostDate]
        # Dates must be MM/DD/YYYY format. This is how we do incremental refresh:
        # fetch only trials that changed since the last ETL run.
        if updated_since or updated_before:
            since = updated_since or "MIN"
            before = updated_before or "MAX"
            params["filter.advanced"] = (
                f"AREA[LastUpdatePostDate]RANGE[{since},{before}]"
            )

        # Structured filters — CT.gov v2 uses `aggFilters` with comma-separated
        # `facet:value` pairs. Phase values are short: 0/1/2/3/4/na.
        # Status values are lowercase short codes: com, rec, act, ter, wit, etc.
        # Learned the hard way (first attempt used filter.phase, which is invalid).
        agg_filters: list[str] = []

        if phase:
            phase_map = {
                "EARLY_PHASE1": "0",
                "PHASE1": "1",
                "PHASE2": "2",
                "PHASE3": "3",
                "PHASE4": "4",
                "NA": "na",
            }
            for p in phase:
                short = phase_map.get(p.upper(), p.lower())
                agg_filters.append(f"phase:{short}")

        if status:
            status_map = {
                "RECRUITING": "rec",
                "NOT_YET_RECRUITING": "not",
                "ENROLLING_BY_INVITATION": "enr",
                "ACTIVE_NOT_RECRUITING": "act",
                "COMPLETED": "com",
                "SUSPENDED": "sus",
                "TERMINATED": "ter",
                "WITHDRAWN": "wit",
                "UNKNOWN": "unk",
            }
            for s in status:
                short = status_map.get(s.upper(), s.lower())
                agg_filters.append(f"status:{short}")

        if study_type:
            # intr = interventional, obs = observational, exp = expanded access
            study_type_map = {
                "INTERVENTIONAL": "int",
                "OBSERVATIONAL": "obs",
                "EXPANDED_ACCESS": "exp",
            }
            short = study_type_map.get(study_type.upper(), study_type.lower())
            agg_filters.append(f"studyType:{short}")

        if agg_filters:
            params["aggFilters"] = ",".join(agg_filters)

        if fields:
            params["fields"] = ",".join(fields)

        page_num = 0
        next_token: Optional[str] = None
        total: Optional[int] = None

        while True:
            if next_token:
                params["pageToken"] = next_token

            data = self._request_json(url, params=params)
            page_num += 1

            if total is None:
                total = data.get("totalCount")
                if total is not None:
                    logger.info("CT.gov search: %s total trials matching", total)

            studies = data.get("studies") or []
            logger.debug("CT.gov page %s returned %s trials", page_num, len(studies))
            for study in studies:
                yield study

            next_token = data.get("nextPageToken")
            if not next_token:
                break

    # -------------------------------------------------------------------------
    # Internals
    # -------------------------------------------------------------------------

    def _request_json(self, url: str, params: Optional[dict] = None) -> dict:
        """GET a URL with retries. Returns parsed JSON dict.

        Retries on 5xx and network errors with exponential backoff. 4xx errors
        fail immediately because they usually indicate a bug on our side
        (bad NCT ID, malformed query, etc.) — retrying just wastes time.
        """
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._session.get(url, params=params, timeout=30.0)
                if 400 <= resp.status_code < 500:
                    # Client error — fail loud, don't retry
                    raise CTGovAPIError(
                        f"CT.gov returned {resp.status_code} for {url}: {resp.text[:200]}"
                    )
                resp.raise_for_status()
                return resp.json()
            except requests.HTTPError as e:
                last_exc = e
                logger.warning(
                    "CT.gov 5xx on attempt %s/%s: %s",
                    attempt,
                    self.max_retries,
                    e,
                )
            except requests.RequestException as e:
                last_exc = e
                logger.warning(
                    "CT.gov network error on attempt %s/%s: %s",
                    attempt,
                    self.max_retries,
                    e,
                )

            if attempt < self.max_retries:
                sleep_for = self.backoff_seconds * (2 ** (attempt - 1))
                time.sleep(sleep_for)

        raise CTGovAPIError(
            f"CT.gov request failed after {self.max_retries} attempts: {last_exc}"
        )
