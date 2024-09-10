from enum import Enum
from typing import Dict, List


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
