from typing import List

import httpx


def check_status_codes(login_status_codes: List[int], response: httpx.Response) -> bool:
    for code in login_status_codes:
        if response.status_code == code:
            return True
    return False
