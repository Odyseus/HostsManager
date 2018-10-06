#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Web application.

Attributes
----------
bottle_app : object
    Bottle application.
root_folder : str
    The "root of the website". The root of the folder were the website files are stored and
    from were this web application is launched.
"""
import os
import sys

try:
    from python_utils import bottle
except (ImportError, SystemError):
    from .python_utils import bottle

root_folder = os.path.realpath(os.path.abspath(os.path.join(
    os.path.normpath(os.getcwd()))))

bottle_app = bottle.Bottle()


class HostsManager():
    """Hosts manager web application.

    Attributes
    ----------
    host : str
        Host name used by the web application.
    port : int
        Port number used by the web application.
    """

    def __init__(self, host, port):
        """Initialize.

        Parameters
        ----------
        host : str
            Host name used by the web application.
        port : int
            Port number used by the web application.
        """
        super().__init__()
        self.host = host
        self.port = port

    def run(self):
        """Run.
        """
        bottle_app.run(host=self.host, port=self.port)

    @bottle_app.route("/")
    def index():
        """Index.

        Returns
        -------
        str
            The content of the "landing page" (the index page).
        """
        with open(os.path.join(root_folder, "index.html"), "r") as file:
            file_data = file.read()

        return file_data


# FIXME: Convert this script into a module.
# Just because it's the right thing to do.
# As it is right now, everything works as "it should".
if __name__ == "__main__":
    args = sys.argv[1:]

    if len(args) == 2:
        app = HostsManager(args[0], args[1])
        app.run()
