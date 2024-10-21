from typing import Any, AsyncGenerator, Generator, Optional, Tuple

import httpx


class ClientResponse:
    data: Generator[Any, None, None]
    status_code: int
    headers: Any

    def __init__(
        self, status_code: int, headers: Any, data: Generator[Any, None, None]
    ):
        self.status_code = status_code
        self.headers = headers
        self.data = data

    @classmethod
    def from_httpx_response(
        cls, response: httpx.Response, data_key: Optional[str] = None
    ) -> "ClientResponse":
        def temp_generator():
            if data_key:
                yield response.json()[data_key]
            else:
                yield response.json()

        return cls(
            status_code=response.status_code,
            headers=response.headers,
            data=temp_generator(),
        )

    @classmethod
    def from_paginated_httpx_response(
        cls, paginated_resp: Tuple[int, Any, Generator[Any, None, None]]
    ) -> "ClientResponse":
        return cls(
            status_code=paginated_resp[0],
            headers=paginated_resp[1],
            data=paginated_resp[2],
        )


class AsyncClientResponse:
    data: AsyncGenerator[Any, None]
    status_code: int
    headers: Any

    def __init__(self, status_code: int, headers: Any, data: AsyncGenerator[Any, None]):
        self.status_code = status_code
        self.headers = headers
        self.data = data

    @classmethod
    def from_httpx_response(
        cls, response: httpx.Response, data_key: Optional[str] = None
    ) -> "AsyncClientResponse":
        async def temp_generator():
            if data_key:
                yield response.json()[data_key]
            else:
                yield response.json()

        return cls(
            status_code=response.status_code,
            headers=response.headers,
            data=temp_generator(),
        )

    @classmethod
    def from_paginated_httpx_response(
        cls, paginated_resp: Tuple[int, Any, AsyncGenerator[Any, None]]
    ) -> "AsyncClientResponse":
        return cls(
            status_code=paginated_resp[0],
            headers=paginated_resp[1],
            data=paginated_resp[2],
        )
