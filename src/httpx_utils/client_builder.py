from enum import Enum
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional, Tuple

import httpx

from .client_response import AsyncClientResponse, ClientResponse


class AuthType(Enum):
    NONE = 0
    TOKEN = 1
    BASIC = 2
    SESSION = 3
    CUSTOM_TOKEN_HEADER = 4


class ClientSettings:
    base_url: str
    headers: Dict[str, str]
    auth_type: AuthType
    token: str
    username: str
    password: str
    custom_token_header: str
    login_url: str
    verify: bool
    data_key: Optional[str]
    login_status_codes: List[int]

    def __init__(self):
        self.base_url = ""
        self.headers = {}
        self.auth_type = AuthType.NONE
        self.token = ""
        self.username = ""
        self.password = ""
        self.custom_token_header = ""
        self.login_url = ""
        self.verify = True
        self.login_status_codes = [200]
        self.data_key = None


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

    def set_data_key(self, data_key: str) -> "ClientBuilder":
        self.settings.data_key = data_key
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

    def build(self) -> "Client":
        return Client.create(settings=self.settings)

    async def async_build(self) -> "AsyncClient":
        return await AsyncClient.create(settings=self.settings)


# comment


def check_status_codes(login_status_codes: List[int], response: httpx.Response) -> bool:
    for code in login_status_codes:
        if response.status_code == code:
            return True
    return False


def _format_url(settings: ClientSettings, ext: str) -> str:
    base_url = settings.base_url
    if ext.startswith("/"):
        ext = ext[1:]
    if base_url.endswith("/"):
        base_url = base_url[:-1]
    return f"{base_url}/{ext}"


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


# def _fetch_paginated(
#     client: "Client",
#     ext: str,
#     params: Optional[Dict[str, Any]] = None,
#     page_key: str = "page",
#     limit: int = 100,
# ) -> Generator[Any, Any, None]:
#     if client._settings is None:
#         raise Exception("Failed to fetch paginated: Missing settings")
#     params = params or {}
#     params[page_key] = 1
#     params["limit"] = limit
#     url = _format_url(client._settings, ext)
#     headers = client._settings.headers.copy()
#     while True:
#         response = client.client.get(url, headers=headers, params=params)
#         data = response.json()
#         yield data
#         if len(data) < limit:
#             break
#         params[page_key] += 1
#


def _paginated_get(
    client: "Client",
    url: str,
    headers: Dict[str, str],
    data_key: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    page_key: str = "page",
    limit: int = 100,
) -> Tuple[int, Any, Generator[Any, None, None]]:
    if client._settings is None:
        raise Exception("Failed to fetch paginated: Missing settings")
    params = params or {}
    params[page_key] = 1
    params["limit"] = limit
    response = client.client.get(url, headers=headers, params=params)
    resp_status_code = response.status_code
    resp_headers = response.headers
    data = response.json()

    try:
        per_page = data["per_page"]
        limit = per_page
    except KeyError:
        pass

    def data_generator(
        response: httpx.Response, data: Dict[str, Any]
    ) -> Generator[Any, None, None]:
        first_request = True
        while True:
            if not first_request:
                response = client.client.get(url, headers=headers, params=params)
                data = response.json()
            first_request = False
            if data_key:
                return_data = data[data_key]
            else:
                return_data = data
            if isinstance(return_data, list):
                for item in return_data:
                    yield item
            else:
                yield return_data
            if len(return_data) < limit:
                break
            params[page_key] += 1

    return resp_status_code, resp_headers, data_generator(response=response, data=data)


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
        custom_data_key: Optional[str] = None,
        paginate: bool = False,
        page_key: str = "page",
        limit: int = 100,
    ) -> ClientResponse:
        if self._settings is None:
            raise Exception("Failed to get: Missing clientsettings settings")

        headers = self._settings.headers.copy()
        if custom_headers:
            headers.update(custom_headers)

        data_key = self._settings.data_key
        if custom_data_key:
            data_key = custom_data_key

        url = _format_url(self._settings, ext)
        if paginate:
            paginated_resp = _paginated_get(
                client=self,
                url=url,
                headers=headers,
                data_key=data_key,
                params=params,
                page_key=page_key,
                limit=limit,
            )
            return ClientResponse.from_paginated_httpx_response(paginated_resp)
        else:
            response = self._client.get(url, headers=headers, params=params)
            return ClientResponse.from_httpx_response(response, data_key=data_key)

    # def get(
    #     self,
    #     ext: str,
    #     params: Optional[Dict[str, Any]] = None,
    #     custom_headers: Optional[Dict[str, str]] = None,
    #     paginate: bool = False,
    #     page_key: str = "page",
    #     limit: int = 100,
    # ) -> Generator[Any, Any, None]:
    #     if self._settings is None:
    #         raise Exception("Failed to get: Missing clientsettings settings")
    #     if paginate:
    #         for data in _fetch_paginated(
    #             client=self,
    #             ext=ext,
    #             params=params,
    #             page_key=page_key,
    #             limit=limit,
    #         ):
    #             yield data
    #     else:
    #         headers = self._settings.headers.copy()
    #         if custom_headers:
    #             for k, v in custom_headers.items():
    #                 headers[k] = v
    #         url = _format_url(self._settings, ext)
    #         response = self._client.get(url, headers=headers, params=params)
    #         yield response.json()
    #
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

    def put(
        self,
        ext: str,
        data: Optional[Dict[str, Any]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        if self._settings is None:
            raise Exception("Failed to put: Missing settings")

        headers = self._settings.headers.copy()
        if custom_headers:
            headers.update(custom_headers)

        url = _format_url(self._settings, ext)
        response = self._client.put(url, headers=headers, json=data)

        return response.json()

    def delete(
        self,
        ext: str,
        params: Optional[Dict[str, Any]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        if self._settings is None:
            raise Exception("Failed to delete: Missing settings")

        headers = self._settings.headers.copy()
        if custom_headers:
            headers.update(custom_headers)

        url = _format_url(self._settings, ext)
        response = self._client.delete(url, headers=headers, params=params)

        return response.json()

    @property
    def client(self):
        return self._client

    @property
    def settings(self):
        return self._settings


async def _async_create_session(
    login_url: str,
    username: str,
    password: str,
    verify: bool,
    login_status_codes: List[int],
) -> httpx.AsyncClient:
    if login_url and username and password:
        async with httpx.AsyncClient(verify=verify) as c:
            response = await c.post(
                login_url,
                json={"username": username, "password": password},
            )
            if not check_status_codes(login_status_codes, response):
                raise Exception("Failed to create session")
        client = httpx.AsyncClient(cookies=response.cookies, verify=verify)
        return client
    raise Exception("Failed to create session: Missing client settings")


async def _async_get_client(
    settings: ClientSettings,
) -> Optional[httpx.AsyncClient]:
    if settings.auth_type == AuthType.SESSION:
        client = await _async_create_session(
            settings.login_url,
            settings.username,
            settings.password,
            settings.verify,
            settings.login_status_codes,
        )
        return client
    if settings.auth_type == AuthType.BASIC:
        auth = httpx.BasicAuth(username=settings.username, password=settings.password)
        return httpx.AsyncClient(auth=auth, verify=settings.verify)
    if settings.auth_type == AuthType.TOKEN:
        settings.headers["Authorization"] = f"Bearer {settings.token}"
    if settings.auth_type == AuthType.CUSTOM_TOKEN_HEADER:
        settings.headers[settings.custom_token_header] = settings.token
    return httpx.AsyncClient(verify=settings.verify)


# TODO: update to match sync cloent
async def _async_fetch_paginated(
    client: "AsyncClient",
    url: str,
    headers: Dict[str, str],
    data_key: Optional[str],
    params: Optional[Dict[str, Any]] = None,
    page_key: str = "page",
    limit: int = 100,
) -> Tuple[int, Any, AsyncGenerator]:
    if client._settings is None:
        raise Exception("Failed to fetch paginated: Missing settings")
    params = params or {}
    params[page_key] = 1
    params["limit"] = limit

    response = await client._client.get(url, headers=headers, params=params)
    resp_status_code = response.status_code
    resp_headers = response.headers
    data = response.json()

    try:
        per_page = data["per_page"]
        limit = per_page
    except KeyError:
        pass

    # TODO: change this logic
    async def data_generator(
        response: httpx.Response, data: Dict[str, Any]
    ) -> AsyncGenerator[Any, None]:
        first_request = True
        while True:
            if not first_request:
                response = await client._client.get(url, headers=headers, params=params)
                data = response.json()
            first_request = False
            if data_key:
                return_data = data[data_key]
            else:
                return_data = data

            if isinstance(return_data, list):
                for item in return_data:
                    yield item
            else:
                yield return_data
            if len(data) < limit:
                break
            params[page_key] += 1

    return resp_status_code, resp_headers, data_generator(response, data)


class AsyncClient:
    _settings: Optional[ClientSettings]
    _client: httpx.AsyncClient

    def __init__(self):
        self._settings = None

    def _set_settings(self, settings: ClientSettings):
        self._settings = settings

    @classmethod
    async def create(cls, settings: ClientSettings) -> "AsyncClient":
        client = cls()
        client._set_settings(settings)
        if client._settings is None:
            raise Exception("Failed to create client: Missing settings")
        c = await _async_get_client(client._settings)
        if not c:
            raise Exception("Failed to create client")
        client._client = c
        return client

    async def get(
        self,
        ext: str,
        params: Optional[Dict[str, Any]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        custom_data_key: Optional[str] = None,
        paginate: bool = False,
        page_key: str = "page",
        limit: int = 100,
    ) -> AsyncClientResponse:
        if self._settings is None:
            raise Exception("Failed to get: Missing clientsettings")

        headers = self._settings.headers.copy()
        if custom_headers:
            headers.update(custom_headers)

        data_key = self._settings.data_key
        if custom_data_key:
            data_key = custom_data_key

        url = _format_url(self._settings, ext)
        if paginate:
            paginated_resp = await _async_fetch_paginated(
                client=self,
                url=url,
                headers=headers,
                data_key=data_key,
                params=params,
                page_key=page_key,
                limit=limit,
            )
            return AsyncClientResponse.from_paginated_httpx_response(paginated_resp)
        else:
            response = await self._client.get(url, headers=headers, params=params)
            return AsyncClientResponse.from_httpx_response(response, data_key)

    async def post(
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
        response = await self._client.post(url, headers=headers, json=data)
        return response.json()

    async def put(
        self,
        ext: str,
        data: Optional[Dict[str, Any]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        if self._settings is None:
            raise Exception("Failed to put: Missing settings")

        headers = self._settings.headers.copy()
        if custom_headers:
            headers.update(custom_headers)

        url = _format_url(self._settings, ext)
        response = await self._client.put(url, headers=headers, json=data)

        return response.json()

    async def delete(
        self,
        ext: str,
        params: Optional[Dict[str, Any]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        if self._settings is None:
            raise Exception("Failed to delete: Missing settings")

        headers = self._settings.headers.copy()
        if custom_headers:
            headers.update(custom_headers)

        url = _format_url(self._settings, ext)
        response = await self._client.delete(url, headers=headers, params=params)

        return response.json()

    @property
    def client(self):
        return self._client

    @property
    def settings(self):
        return self._settings
