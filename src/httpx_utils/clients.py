from typing import (
    Any,
    AsyncGenerator,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
)

from .async_builder import Client as CustomAsyncClient
from .async_builder import ClientBuilder as AsyncClientBuilder
from .settings import AuthType, ClientSettings
from .sync_builder import Client as CustomSyncClient
from .sync_builder import ClientBuilder as SyncClientBuilder

T = TypeVar("T", bound="AsyncBaseClientWrapper")
V = TypeVar("V", bound="SyncBaseClientWrapper")

# Async clients, models etc


class AsyncBaseClientWrapper:
    _client: Optional[CustomAsyncClient]

    def __init__(self):
        self._client = None

    @classmethod
    async def create(cls: Type[T], *args: Any, **kwargs: Any) -> T:
        self = cls()
        await self._async_init(*args, **kwargs)
        return self

    async def _async_init(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def get(
        self,
        ext: str,
        params: Optional[Dict[str, Any]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        paginate: bool = False,
        page_key: str = "page",
        limit: int = 100,
    ) -> AsyncGenerator[Any, Any]:
        if self._client is None:
            raise ValueError("Client not initialized")
        return self._client.get(ext, params, custom_headers, paginate, page_key, limit)


class AsyncBasicAuthClient(AsyncBaseClientWrapper):
    async def _async_init(
        self,
        base_url: str,
        login_url: str,
        headers: Dict[str, str],
        login_statuses: List[int],
        verify: bool,
        auth: Tuple[str, str],
    ) -> None:
        client_builder = AsyncClientBuilder()
        self._client = await (
            client_builder.set_base_url(base_url)
            .set_headers(headers)
            .set_auth_type(AuthType.SESSION)
            .set_login_url(login_url)
            .set_login_status(login_statuses)
            .set_verify(verify)
            .set_basic_auth(username=auth[0], password=auth[1])
            .build()
        )


class AsyncTokenClient(AsyncBaseClientWrapper):
    async def _async_init(self) -> None:
        pass


# Sync clients, models etc


class SyncBaseClientWrapper:
    _client: Optional[CustomSyncClient]

    def __init__(self):
        self._client = None

    @classmethod
    def create(cls: Type[V], *args: Any, **kwargs: Any) -> V:
        self = cls()
        self._sync_init(*args, **kwargs)
        return self

    def _sync_init(self, *args: Any, **kwargs: Any) -> None:
        pass

    def get(
        self,
        ext: str,
        params: Optional[Dict[str, Any]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        paginate: bool = False,
        page_key: str = "page",
        limit: int = 100,
    ) -> Any:
        if self._client is None:
            raise ValueError("Client not initialized")
        return self._client.get(ext, params, custom_headers, paginate, page_key, limit)
