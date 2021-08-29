import json
import requests

data1 = {"tool": "params", "command": "set_par", "args": ["imagetest", 1111], "kwargs": {}}

data2 = {"tool": "params", "command": "get_par", "args": ["imagetest"], "kwargs": {}}

data3 = {
    "tool": "params",
    "command": "set_par",
    "args": [],
    "kwargs": {"parameter": "imagetest", "value": 3333},
}

r = requests.post("http://localhost:2403/japi", json=data2)
print(r.status_code, r.json())
