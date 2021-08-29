# azcam-fastapi

*azcam-fastapi* is an *azcam* extension which adds support for a fastapi-based web server.

## Installation

`pip install azcam-fastapi`

or download from github: https://github.com/mplesser/azcam-fastapi.git.

## Uage Example

```python
from azcam_fastapi.fastapi_server import WebServer
webserver = WebServer()
webserver.index = f"index_mysystem.html"
webserver.start()
```
