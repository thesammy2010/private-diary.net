import json
from typing import Dict, List


with open(file="./config.json", mode="r") as file:
    _config: Dict[str, Dict[str, str]] = json.load(file)

USERNAME = _config["credentials"]["username"]
PASSWORD = _config["credentials"]["password"]

COOKIES: List[Dict[str, str]] = [
    {
        "name": key,
        "value": value,
        "domain": "privatediary.net",
        "httpOnly": True,
    } for key, value in _config["cookies"].items()
]
