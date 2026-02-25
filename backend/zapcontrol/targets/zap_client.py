"""ZAP API client utilities.

Safety guardrail: Only scan targets you own or have explicit permission to test.
"""

from __future__ import annotations

import requests


class ZapClientError(Exception):
    pass


class ZapClient:
    def __init__(self, base_url: str, api_key: str = "", timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _params(self, extra: dict | None = None) -> dict:
        params = {"apikey": self.api_key} if self.api_key else {}
        if extra:
            params.update(extra)
        return params

    def _json_get(self, path: str, params: dict | None = None, timeout: int | None = None) -> dict:
        try:
            response = requests.get(
                f"{self.base_url}{path}",
                params=self._params(params),
                timeout=timeout or self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise ZapClientError(str(exc)) from exc

    def version(self) -> str:
        return self._json_get("/JSON/core/view/version/").get("version", "")

    def start_spider(self, target_url: str) -> str:
        payload = self._json_get("/JSON/spider/action/scan/", {"url": target_url, "recurse": "true"})
        scan_id = payload.get("scan")
        if not scan_id:
            raise ZapClientError("Spider scan id was empty")
        return str(scan_id)

    def spider_status(self, spider_id: str) -> int:
        payload = self._json_get("/JSON/spider/view/status/", {"scanId": spider_id})
        return int(payload.get("status", "0"))

    def start_active_scan(self, target_url: str) -> str:
        payload = self._json_get(
            "/JSON/ascan/action/scan/",
            {"url": target_url, "recurse": "true", "inScopeOnly": "false"},
        )
        scan_id = payload.get("scan")
        if not scan_id:
            raise ZapClientError("Active scan id was empty")
        return str(scan_id)

    def active_scan_status(self, scan_id: str) -> int:
        payload = self._json_get("/JSON/ascan/view/status/", {"scanId": scan_id})
        return int(payload.get("status", "0"))

    def alerts(self, base_url: str, start: int = 0, count: int = 9999) -> list[dict]:
        payload = self._json_get(
            "/JSON/core/view/alerts/",
            {"baseurl": base_url, "start": str(start), "count": str(count)},
            timeout=90,
        )
        return payload.get("alerts", [])

    def html_report(self) -> str:
        return requests.get(
            f"{self.base_url}/OTHER/core/other/htmlreport/",
            params=self._params(),
            timeout=90,
        ).text
