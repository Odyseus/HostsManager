#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Web application.

Attributes
----------
www_root : str
    The "root of the website". The root of the folder were the website files are stored and
    from were this web application is launched.
"""
import os
import sys


try:
    # If executed as a script to start the web server.
    host, port, app_dir_path = sys.argv[1:]
except Exception:
    # If imported as a module by Sphinx.
    host, port = None, None
    app_dir_path = os.path.realpath(os.path.abspath(os.path.join(
        os.path.normpath(os.path.dirname(__file__)))))

sys.path.insert(0, app_dir_path)

from python_utils.bottle_utils import WebApp
from python_utils.bottle_utils import bottle_app

www_root = os.path.realpath(os.path.abspath(os.path.join(
    os.path.normpath(os.getcwd()))))


class HostsManagerWebApp(WebApp):
    """Web server.
    """

    def __init__(self, *args, **kwargs):
        """Initialization.

        Parameters
        ----------
        *args
            Arguments.
        **kwargs
            Keyword arguments.
        """
        super().__init__(*args, **kwargs)

    @bottle_app.route("/")
    def index():
        """Index.

        Returns
        -------
        str
            The content of the "landing page" (the index page).
        """
        with open(os.path.join(www_root, "index.html"), "r") as file:
            file_data = file.read()

        return file_data


# FIXME: Convert this script into a module.
# Just because it's the right thing to do.
# As it is right now, everything works as "it should".
if __name__ == "__main__" and host and port:
    app = HostsManagerWebApp(host, port)
    app.run()
