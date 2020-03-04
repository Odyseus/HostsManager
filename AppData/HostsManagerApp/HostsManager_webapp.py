#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Web application.

Attributes
----------
root_folder : str
    The "root of the website". The root of the folder were the website files are stored and
    from were this web application is launched.
"""
import os
import sys

# NOTE: Failsafe imports due to this file being used as a script (when launching the server)
# and as a module (when generating documentation with Sphinx).
try:
    from python_utils.bottle_utils import bottle_app
    from python_utils.bottle_utils import WebApp
except (ImportError, SystemError):
    from .python_utils.bottle_utils import bottle_app
    from .python_utils.bottle_utils import WebApp

root_folder = os.path.realpath(os.path.abspath(os.path.join(
    os.path.normpath(os.getcwd()))))


class HostsManager(WebApp):
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
