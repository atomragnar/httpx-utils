import asyncio

import pytest
from httpx_utils import AuthType, Client, ClientBuilder
from httpx_utils.client_builder import (
    ClientSettings,
    _async_create_session,
    _create_session,
    _format_url,
)


def test_format_url():
    settings = ClientSettings()
    settings.base_url = "http://example.com/"
    result = _format_url(settings, "/test")
    assert result == "http://example.com/test"


def test_client_builder_sets_base_url():
    builder = ClientBuilder()
    builder.set_base_url("http://example.com")
    assert builder.settings.base_url == "http://example.com"


def test_client_builder_sets_token():
    builder = ClientBuilder()
    builder.set_auth_type(AuthType.TOKEN)
    builder.set_token("test-token")
    assert builder.settings.token == "test-token"
    assert builder.settings.auth_type == AuthType.TOKEN


def test_client_builder_build_creates_client(mocker):
    mocker.patch("httpx.Client", return_value=mocker.Mock())
    builder = ClientBuilder()
    client = builder.set_base_url("http://example.com").build()
    assert client._settings is not None
    assert client._settings.base_url == "http://example.com"


def test_client_get_request(mocker):
    mock_httpx_client = mocker.Mock()
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"key": "value"}
    mock_httpx_client.get.return_value = mock_response

    mocker.patch("httpx.Client", return_value=mock_httpx_client)

    settings = ClientSettings()
    settings.base_url = "http://example.com"

    client = Client.create(settings)

    response = client.get("/test")
    data = next(response.data)
    assert response.status_code == 200
    assert data == {"key": "value"}

    mock_httpx_client.get.assert_called_once_with(
        "http://example.com/test", headers={}, params=None
    )


def test_create_session_success(mocker):
    mock_httpx_client = mocker.Mock()
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.cookies = {"session": "12345"}
    # mock_response.cookies = mock_cookies
    mock_httpx_client.post.return_value = mock_response

    mocker.patch("httpx.Client", return_value=mock_httpx_client)

    session = _create_session(
        login_url="http://example.com/login",
        username="user",
        password="pass",
        verify=True,
        login_status_codes=[200],
    )

    mock_httpx_client.post.assert_called_once_with(
        "http://example.com/login",
        data={"username": "user", "password": "pass"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    # print(session.cookies.items())
    # assert session.cookies == mock_response.cookies


#
# @pytest.mark.asyncio
# async def test_async_create_session_success(mocker):
#     mock_async_client = mocker.Mock()
#     mock_response = mocker.Mock()
#     mock_response.status_code = 200
#     mock_async_client.post.return_value = mock_response
#
#     mocker.patch("httpx.AsyncClient", return_value=mock_async_client)
#
#     session = await _async_create_session(
#         login_url="http://example.com/login",
#         username="user",
#         password="pass",
#         verify=True,
#         login_status_codes=[200],
#     )
#
#     assert session.cookies == mock_response.cookies
#     mock_async_client.post.assert_called_once_with(
#         "http://example.com/login", json={"username": "user", "password": "pass"}
#     )
