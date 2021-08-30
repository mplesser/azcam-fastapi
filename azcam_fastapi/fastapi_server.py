"""
Configure and start fastapi application using uvicorn.
Import this after all configuration has been completed.
All API commands suported here must start with ""http://locahost:2402/api/".
Both GET and POST are supported for /api/.

URL example: "http://locahost:2402/api/instrument/set_filter?filter=1&filter_id=2"

Default response is JSON:
    response = {
        "message": "Finished",
        "command": urlparse(url).path,
        "data": reply,
    }
If webserver.return_json is False, then just "data" is returned.

"""

import logging
import os
import sys
import threading
import subprocess
from urllib.parse import urlparse

# from flask import Flask, render_template, request, send_from_directory
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import azcam


class WebServer(object):
    """
    Azcam web server.
    """

    def __init__(self):

        self.templates_folder = ""
        self.index = "index.html"
        self.upload_folder = ""

        self.logcommands = 0
        self.logstatus = 0

        # port for webserver
        self.port = None

        self.is_running = 0

        azcam.db.webserver = self

    def initialize(self):
        """
        Initialize application.
        """

        # create app
        app = FastAPI()
        self.app = app
        self.root_folder = os.path.dirname(__file__)

        app.mount(
            "/static",
            StaticFiles(directory=os.path.join(self.root_folder, "static")),
            name="static",
        )

        templates = Jinja2Templates(directory=os.path.join(self.root_folder, "templates"))

        @app.get("/", response_class=HTMLResponse)
        def home(request: Request, id: str = "Mike"):
            return templates.TemplateResponse(self.index, {"request": request, "id": id})

        # ******************************************************************************
        # API command - .../api/tool/command
        # ******************************************************************************
        @app.get("/api/<path:command>")
        @app.post("/api/<path:command>")
        def api(command):
            """
            Remote web api commands. such as: /api/expose or /api/exposure/reset
            """

            url = request.url
            if self.logcommands:
                if not ("/get_status" in url or "/watchdog" in url):
                    azcam.log(url, prefix="Web-> ")

            reply = self.web_command(url)

            if self.logcommands:
                if not ("/get_status" in url or "/watchdog" in url):
                    azcam.log(reply, prefix="Web->   ")

            return reply

        # ******************************************************************************
        # JSON API command - .../api/tool/command
        # ******************************************************************************
        @app.route("/japi", methods=["GET", "POST"])
        def japi():
            """
            Remote web api commands using JSON.
            """

            url = request.url
            azcam.log(url, prefix="Web-> ")

            args = request.get_json()
            print("args", args)

            toolid = getattr(azcam.db, args["tool"])
            command = getattr(toolid, args["command"])

            arglist = args["args"]
            kwargs = args["kwargs"]
            reply = command(*arglist, **kwargs)

            response = {
                "message": "Finished",
                "command": f"{args['tool']}.{args['command']}",
                "data": reply,
            }

            return response

    def stop(self):
        """
        Stops command server running in thread.
        """

        azcam.log("Stopping the webserver is not supported")

        return

    def start(self):
        """
        Start web server.
        """

        self.initialize()

        if self.port is None:
            self.port = azcam.db.cmdserver.port + 1

        azcam.log(f"Starting webserver - listening on port {self.port}")

        uvicorn.run(self.app)

        """
        # turn off development server warning
        cli = sys.modules["flask.cli"]
        cli.show_server_banner = lambda *x: None

        if 1:
            log1 = logging.getLogger("werkzeug")
            log1.setLevel(logging.ERROR)

        # 1 => threaded for command line use (when imported)
        if 0:
            self.app.jinja_env.auto_reload = True
            self.app.config["TEMPLATES_AUTO_RELOAD"] = True
            self.app.config["JSONIFY_PRETTYPRINT_REGULAR"] = False
            self.app.config["UPLOAD_FOLDER"] = self.upload_folder
            self.app.run(debug=True, threaded=False, host="0.0.0.0", port=self.port)
        else:
            self.app.jinja_env.auto_reload = True
            self.app.config["TEMPLATES_AUTO_RELOAD"] = True
            self.app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True
            self.app.config["UPLOAD_FOLDER"] = self.upload_folder
            self.webthread = threading.Thread(
                target=self.app.run,
                kwargs={
                    "debug": False,
                    "threaded": True,
                    "host": "0.0.0.0",
                    "port": self.port,
                },
            )
            self.webthread.daemon = True  # terminates when main process exits
            self.webthread.start()
            self.is_running = 1
        """

        return

    def web_command(self, url):
        """
        Parse and execute a command string received as a URL.
        Returns the reply as a JSON packet.
        """

        try:
            obj, method, kwargs = self.parse(url)

            # primary object must be in db.remote_tools
            objects = obj.split(".")
            if objects[0] not in azcam.db.remote_tools:
                raise azcam.AzcamError(f"remote call not allowed in API: {obj}", 4)

            if len(objects) == 1:
                objid = azcam.db.get(obj)
            elif len(objects) == 2:
                objid = getattr(azcam.db.get(objects[0]), objects[1])
            elif len(objects) == 3:
                objid = getattr(getattr(azcam.db.get(objects[0]), objects[1]), objects[2])
            else:
                objid = None  # too complicated for now

            caller = getattr(objid, method)
            reply = caller() if kwargs is None else caller(**kwargs)

        except azcam.AzcamError as e:
            azcam.log(f"web_command error: {e}")
            if e.error_code == 4:
                reply = "remote call not allowed"
            else:
                reply = f"web_command error: {repr(e)}"
        except Exception as e:
            azcam.log(e)
            reply = f"invalid API command: {url}"

        # generic response
        response = {
            "message": "Finished",
            "command": urlparse(url).path,
            "data": reply,
        }

        return response

    def parse(self, url):
        """
        Parse URL.
        Return the caller object, method, and keyword arguments.
        Object may be compound, like "exposure.image.focalplane".

        URL example: http://locahost:2402/api/instrument/set_filter?filter=1&filter_id=2
        """

        # parse URL
        s = urlparse(url)
        # remove /api/
        if s.path.startswith("/api/"):
            p = s.path[5:]
        else:
            raise azcam.AzcamError("Invalid API command: must start with /api/")

        try:
            tokens = p.split("/")
        except Exception as e:
            raise e("Invalid API command")

        # get oject and method
        if len(tokens) != 2:
            raise azcam.AzcamError("Invalid API command")
        obj, method = tokens

        # get arguments
        args = s.query.split("&")
        if args == [""]:
            kwargs = None
        else:
            kwargs = {}
            for arg1 in args:
                if "=" in arg1:
                    arg, par = arg1.split("=")
                else:
                    arg = arg1
                    par = None
                kwargs[arg] = par

        return obj, method, kwargs
