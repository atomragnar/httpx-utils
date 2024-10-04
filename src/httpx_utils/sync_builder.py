from typing import Any, Dict, Generator, List, Optional

import httpx

from .helpers import check_status_codes
from .settings import AuthType, ClientSettings


def _create_session(
    login_url: str,
    username: str,
    password: str,
    verify: bool,
    login_status_codes: List[int],
) -> httpx.Client:
    if not login_url or not username or not password:
        raise Exception("Failed to create session: Missing client settings")

    client = httpx.Client(verify=verify)

    payload = {"username": username, "password": password}
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }

    response = client.post(login_url, data=payload, headers=headers)

    if not check_status_codes(login_status_codes, response):
        raise Exception("Failed to create session")

    client.cookies.update(response.cookies)

    return client


def _get_client(
    settings: ClientSettings,
) -> httpx.Client:
    if settings.auth_type == AuthType.SESSION:
        return _create_session(
            settings.login_url,
            settings.username,
            settings.password,
            settings.verify,
            settings.login_status_codes,
        )
    if settings.auth_type == AuthType.BASIC:
        auth = httpx.BasicAuth(username=settings.username, password=settings.password)
        return httpx.Client(auth=auth, verify=settings.verify)
    if settings.auth_type == AuthType.TOKEN:
        settings.headers["Authorization"] = f"Bearer {settings.token}"
    if settings.auth_type == AuthType.CUSTOM_TOKEN_HEADER:
        settings.headers[settings.custom_token_header] = settings.token
    return httpx.Client(verify=settings.verify)


def _format_url(settings: ClientSettings, ext: str) -> str:
    base_url = settings.base_url
    if ext.startswith("/"):
        ext = ext[1:]
    if base_url.endswith("/"):
        base_url = base_url[:-1]
    return f"{base_url}/{ext}"


def _fetch_paginated(
    client: "Client",
    ext: str,
    params: Optional[Dict[str, Any]] = None,
    page_key: str = "page",
    limit: int = 100,
) -> Generator[Any, Any, None]:
    if client._settings is None:
        raise Exception("Failed to fetch paginated: Missing settings")
    params = params or {}
    params[page_key] = 1
    params["limit"] = limit
    url = _format_url(client._settings, ext)
    headers = client._settings.headers.copy()
    while True:
        response = client.client.get(url, headers=headers, params=params)
        data = response.json()
        yield data
        if len(data) < limit:
            break
        params[page_key] += 1


class Client:
    _settings: Optional[ClientSettings]
    _client: httpx.Client

    def __init__(self):
        self._settings = None

    def _set_settings(self, settings: ClientSettings):
        self._settings = settings

    @classmethod
    def create(cls, settings: ClientSettings) -> "Client":
        client = cls()
        client._set_settings(settings)
        if client._settings is None:
            raise Exception("Failed to create client: Missing settings")
        c = _get_client(client._settings)
        if not c:
            raise Exception("Failed to create client")
        client._client = c
        return client

    def get(
        self,
        ext: str,
        params: Optional[Dict[str, Any]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        paginate: bool = False,
        page_key: str = "page",
        limit: int = 100,
    ) -> Generator[Any, Any, None]:
        if self._settings is None:
            raise Exception("Failed to get: Missing clientsettings settings")
        if paginate:
            for data in _fetch_paginated(
                client=self,
                ext=ext,
                params=params,
                page_key=page_key,
                limit=limit,
            ):
                yield data
        else:
            headers = self._settings.headers.copy()
            if custom_headers:
                for k, v in custom_headers.items():
                    headers[k] = v
            url = _format_url(self._settings, ext)
            response = self._client.get(url, headers=headers, params=params)
            yield response.json()

    def post(
        self,
        ext: str,
        data: Optional[Dict[str, Any]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        if self._settings is None:
            raise Exception("Failed to post: Missing settings")
        headers = self._settings.headers.copy()
        if custom_headers:
            for k, v in custom_headers.items():
                headers[k] = v
        url = _format_url(self._settings, ext)
        response = self._client.post(url, headers=headers, json=data)
        return response.json()

    @property
    def client(self):
        return self._client

    @property
    def settings(self):
        return self._settings


class ClientBuilder:
    def __init__(self):
        self.settings = ClientSettings()

    def set_base_url(self, base_url: str) -> "ClientBuilder":
        self.settings.base_url = base_url
        return self

    def set_headers(self, headers: Dict[str, str]) -> "ClientBuilder":
        self.settings.headers = headers
        return self

    def set_auth_type(self, auth_type: AuthType) -> "ClientBuilder":
        self.settings.auth_type = auth_type
        return self

    def set_token(self, token: str) -> "ClientBuilder":
        self.settings.token = token
        return self

    def set_basic_auth(self, username: str, password: str) -> "ClientBuilder":
        self.settings.username = username
        self.settings.password = password
        return self

    def set_custom_token_header(
        self, custom_token_header: str, token: str
    ) -> "ClientBuilder":
        self.settings.custom_token_header = custom_token_header
        self.settings.token = token
        return self

    def set_login_url(self, login_url: str) -> "ClientBuilder":
        self.settings.login_url = login_url
        return self

    def set_verify(self, verify: bool) -> "ClientBuilder":
        self.settings.verify = verify
        return self

    def set_login_status(self, status_codes: List[int]) -> "ClientBuilder":
        has_200 = False
        for code in status_codes:
            if code < 200 or code > 599:
                raise ValueError("Invalid status code")
            if code == 200:
                has_200 = True
        if not has_200:
            status_codes.append(200)
        self.settings.login_status_codes = status_codes
        return self

    def build(self) -> Client:
        return Client.create(settings=self.settings)
