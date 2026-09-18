from __future__ import annotations

import os
import time
from typing import Any

import httpx

SANDBOX_API = "https://api-sandbox.euipo.europa.eu"
SANDBOX_AUTH = "https://auth-sandbox.euipo.europa.eu/oidc/accessToken"
PRODUCTION_API = "https://api.euipo.europa.eu"
PRODUCTION_AUTH = "https://euipo.europa.eu/cas-server-webapp/oidc/accessToken"


class EUIPOClient:
    def __init__(self) -> None:
        self.client_id = os.environ.get("EUIPO_CLIENT_ID", "")
        self.client_secret = os.environ.get("EUIPO_CLIENT_SECRET", "")
        use_sandbox = os.environ.get("EUIPO_USE_SANDBOX", "true").lower() != "false"

        if use_sandbox:
            self.api_base = SANDBOX_API
            self.auth_url = SANDBOX_AUTH
            self.env_label = "sandbox"
        else:
            self.api_base = PRODUCTION_API
            self.auth_url = PRODUCTION_AUTH
            self.env_label = "production"

        self._token: str | None = None
        self._token_expires_at: float = 0
        self._http = httpx.AsyncClient(timeout=30)

    @property
    def has_credentials(self) -> bool:
        return bool(self.client_id and self.client_secret)

    async def _ensure_token(self) -> str:
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token

        resp = await self._http.post(
            self.auth_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "uid",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expires_at = time.time() + data.get("expires_in", 7200)
        return self._token  # type: ignore[return-value]

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        token = await self._ensure_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "X-IBM-Client-Id": self.client_id,
            "Accept": "application/json",
        }
        url = f"{self.api_base}{path}"
        resp = await self._http.request(method, url, headers=headers, **kwargs)
        resp.raise_for_status()
        return resp.json()

    # --- Trademark Search API ---

    async def search_trademarks(
        self,
        query: str,
        nice_class: str | None = None,
        status: str | None = None,
        mark_feature: str | None = None,
        applicant_name: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        page: int = 0,
        size: int = 10,
    ) -> dict[str, Any]:
        parts: list[str] = []
        if query:
            parts.append(f"wordMarkSpecification.verbalElement==*{query}*")
        if nice_class:
            for cls in nice_class.split(","):
                parts.append(f"niceClasses=={cls.strip()}")
        if status:
            parts.append(f"status=={status}")
        if mark_feature:
            parts.append(f"markFeature=={mark_feature}")
        if applicant_name:
            parts.append(f"applicants.name==*{applicant_name}*")
        if date_from:
            parts.append(f"applicationDate=ge={date_from}")
        if date_to:
            parts.append(f"applicationDate=le={date_to}")

        params: dict[str, Any] = {"page": page, "size": max(size, 10)}
        if parts:
            params["query"] = ";".join(parts)

        return await self._request("GET", "/trademark-search/trademarks", params=params)

    async def get_trademark(self, application_number: str) -> dict[str, Any]:
        return await self._request("GET", f"/trademark-search/trademarks/{application_number}")

    async def get_trademark_image_url(self, application_number: str, thumbnail: bool = True) -> str:
        path = f"/trademark-search/trademarks/{application_number}/image"
        if thumbnail:
            path += "/thumbnail"
        return f"{self.api_base}{path}"

    # --- Goods and Services API ---

    async def search_gs_terms(
        self,
        language: str = "en",
        term_text: str | None = None,
        class_number: str | None = None,
        page: int = 0,
        size: int = 10,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"language": language, "page": page, "size": max(size, 10)}
        if term_text:
            params["termText"] = term_text
        if class_number:
            params["classNumber"] = class_number
        return await self._request("GET", "/goods-and-services/terms", params=params)

    async def get_gs_class_headings(self, language: str = "en") -> dict[str, Any]:
        return await self._request("GET", "/goods-and-services/classHeadings", params={"language": language})

    async def get_gs_taxonomy(
        self,
        language: str = "en",
        term_text: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"language": language}
        if term_text:
            params["termText"] = term_text
        return await self._request("GET", "/goods-and-services/taxonomy", params=params)

    async def suggest_gs_terms(
        self,
        language: str,
        texts: list[str],
        class_number: int | None = None,
        max_suggestions: int = 20,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"language": language, "texts": texts}
        if class_number is not None:
            body["classNumber"] = class_number
        return await self._request(
            "POST",
            "/goods-and-services/terms-suggestion-list",
            params={"maxSuggestions": min(max_suggestions, 200)},
            json=body,
        )

    async def validate_gs_classification(
        self,
        language: str,
        goods_and_services: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/goods-and-services/classification-validation",
            json={"sourceLanguage": language, "goodsAndServices": goods_and_services},
        )

    async def translate_gs_classification(
        self,
        source_language: str,
        target_languages: list[str],
        goods_and_services: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/goods-and-services/classification-translation",
            json={
                "sourceLanguage": source_language,
                "languagesToTranslate": target_languages,
                "goodsAndServices": goods_and_services,
            },
        )

    async def close(self) -> None:
        await self._http.aclose()
