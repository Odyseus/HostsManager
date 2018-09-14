#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Main command line application.

Attributes
----------
docopt_doc : str
    Used to store/define the docstring that will be passed to docopt as the "doc" argument.
root_folder : str
    The main folder containing the application. All commands must be executed from this location
    without exceptions.
"""

import os
import sys

from threading import Thread

from . import app_utils
from .__init__ import __appname__, __appdescription__, __version__, __status__
from .python_utils import exceptions, log_system, shell_utils, file_utils
from .python_utils.docopt import docopt

if sys.version_info < (3, 5):
    raise exceptions.WrongPythonVersion()


root_folder = os.path.realpath(os.path.abspath(os.path.join(
    os.path.normpath(os.getcwd()))))


docopt_doc = """{__appname__} {__version__} {__status__}

{__appdescription__}

Usage:
    app.py run (update | build | install) [update] [build] [install]
               (-p <name> | --profile=<name>)
               [-o <key=value>... | --override=<key=value>...]
               [-d | --flush-dns-cache]
               [-f | --force-update]
    app.py server (start | stop | restart)
                  [--host=<host>]
                  [--port=<port>]
    app.py generate (system_executable | new_profile)
    app.py (-h | --help | --version | -d | --flush-dns-cache)

Options:

-h, --help
    Show this screen.

--version
    Show application version.

-p <name>, --profile=<name>
    The profile name to work with. This is actually the name of a folder inside
    the profiles folder.

-o <key=value>, --override=<key=value>
    One or more sets of <key=value> that will override the configuration
    options set in the conf.py file.

-d, --flush-dns-cache
    Attempt to flush DNS cache for the new hosts file to take effect.

-f, --force-update
    Force the update of all sources, ignoring the frequency in which they
    should be updated.

--host=<host>
    Host name. [Default: 0.0.0.0]

--port=<port>
    Port name. [Default: 80]

Sub-commands for the `server` command:
    start                Start server.
    stop                 Stop server.
    restart              Restart server.

Sub-commands for the `generate` command:
    new_profile          Generate a new profile.
    system_executable    Create an executable for this application on the system
                         PATH to be able to run it from anywhere.

""".format(__appname__=__appname__,
           __appdescription__=__appdescription__,
           __version__=__version__,
           __status__=__status__)


class CommandLineTool():
    """Command line tool.

    It handles the arguments parsed by the docopt module.

    Attributes
    ----------
    action : method
        Set the method that will be executed when calling CommandLineTool.run().
    force_update : bool
        Ignore source update frequency and update its file/s anyway.
    func_names : list
        The name of the functions to run.
    host : str
        Host name used by the web application.
    hosts_manager : object
        See <class :any:`app_utils.HostsManager`>.
    logger : object
        See <class :any:`LogSystem`>.
    port : int
        Port number used by the web application.
    """

    def __init__(self, args):
        """
        Parameters
        ----------
        args : dict
            The dictionary of arguments as returned by docopt parser.
        """
        super(CommandLineTool, self).__init__()

        self.action = None
        logs_storage_dir = "UserData/logs"
        log_file = log_system.get_log_file(storage_dir=logs_storage_dir,
                                           prefix="CLI")
        file_utils.remove_surplus_files(logs_storage_dir, "CLI*")
        self.logger = log_system.LogSystem(filename=log_file,
                                           verbose=True)

        self.force_update = args["--force-update"]
        self.host = args["--host"]
        self.port = args["--port"]
        self.func_names = []

        self.logger.info(shell_utils.get_cli_header(__appname__), date=False)
        print("")

        if args["generate"]:
            if args["system_executable"]:
                self.func_names.append("system_executable_generation")

            if args["new_profile"]:
                self.func_names.append("new_profile_generation")

        if args["server"]:
            self.logger.info("Command: server")
            self.logger.info("Arguments:")

            if args["start"]:
                self.logger.info("start")
                self.func_names.append("http_server_start")
            elif args["stop"]:
                self.logger.info("stop")
                self.func_names.append("http_server_stop")
            elif args["restart"]:
                self.logger.info("restart")
                self.func_names.append("http_server_restart")

        if args["run"]:
            # Workaround docopt issue:
            # https://github.com/docopt/docopt/issues/134
            # Not perfect, but good enough for this particular usage case.
            args_overrides = list(set(args["--override"]))

            raw_overrides = app_utils.ValidatedOverrides(args_overrides)
            override_errors = raw_overrides.get_errors()

            if override_errors:
                self.logger.warning(
                    "Exiting due to errors found while processing the provided overrides:", date=False)

                for error in override_errors:
                    self.logger.info(shell_utils.get_cli_separator(), date=False)
                    self.logger.warning(error, date=False)

                sys.exit(0)

            self.hosts_manager = app_utils.HostsManager(profile=args["--profile"],
                                                        options_overrides=raw_overrides.get_valid_overrides(),
                                                        logger=self.logger)
            self.logger.info("Command: run")
            self.logger.info("Arguments:")

            if args["update"]:
                self.logger.info("update")
                self.func_names.append("update_all_sources")

            if args["build"]:
                self.logger.info("build")
                self.func_names.append("build_hosts_file")

            if args["install"]:
                self.logger.info("install")
                self.func_names.append("install_hosts_file")

        if args["--flush-dns-cache"]:
            self.func_names.append("flush_dns_cache")

    def run(self):
        """Run tasks depending on the arguments passed.

        Raises
        ------
        exceptions.KeyboardInterruption
            See <class :any:`exceptions.KeyboardInterruption`>.
        """
        try:
            threads = []

            if self.func_names:
                for func in self.func_names:
                    t = Thread(target=getattr(self, func, None))
                    t.daemon = True
                    t.start()
                    threads.append(t)

                    for thread in threads:
                        if thread is not None and thread.isAlive():
                            thread.join()
        except (KeyboardInterrupt, SystemExit):
            raise exceptions.KeyboardInterruption()

    def update_all_sources(self):
        """Summary
        """
        self.hosts_manager.update_all_sources(self.force_update)

    def build_hosts_file(self):
        """Summary
        """
        self.hosts_manager.build_hosts_file()

    def install_hosts_file(self):
        """Summary
        """
        self.hosts_manager.install_hosts_file()

    def flush_dns_cache(self):
        """Summary
        """
        app_utils.flush_dns_cache(self.logger)

    def system_executable_generation(self):
        """See :any:`template_utils.system_executable_generation`
        """
        from .python_utils import template_utils

        template_utils.system_executable_generation(
            exec_name="hosts-manager-cli",
            app_root_folder=root_folder,
            sys_exec_template_path=os.path.join(
                root_folder, "AppData", "data", "templates", "system_executable"),
            bash_completions_template_path=os.path.join(
                root_folder, "AppData", "data", "templates", "bash_completions.bash"),
            logger=self.logger
        )

    def new_profile_generation(self):
        """See :any:`app_utils.new_profile_generation`
        """
        app_utils.new_profile_generation(logger=self.logger)

    def http_server(self, action="start"):
        """Start/Stop/Restart the HTTP server.

        Parameters
        ----------
        action : str, optional
            Any of the following: start/stop/restart.
        """
        www_root = os.path.join(root_folder, "UserData", "block_page")
        os.chdir(www_root)
        # The "http_server" executable could be inside app's AppData folder.
        # (The app was made standalone)
        cmd_path = os.path.join(root_folder, "AppData", "data", "python_scripts", "http_server")

        if not os.path.exists(cmd_path):
            # The app wasn't made standalone, so the "http_server" executable
            # is inside the main app (__app__).
            cmd_path = os.path.join(os.path.join(root_folder, ".."), "__app__",
                                    "data", "python_scripts", "http_server")

        # Use of os.execv() so at the end only one process is left executing.
        # The "http_server" executable also uses os.execv() to launch the real web application.
        os.execv(cmd_path, [" "] + [action,
                                    "HostsManager",
                                    self.host,
                                    self.port])

    def http_server_start(self):
        """Self explanatory.
        """
        self.http_server(action="start")

    def http_server_stop(self):
        """Self explanatory.
        """
        self.http_server(action="stop")

    def http_server_restart(self):
        """Self explanatory.
        """
        self.http_server(action="restart")


def main():
    """Initialize main command line interface.

    Raises
    ------
    exceptions.BadExecutionLocation
        Do not allow to run any command if the "flag" file isn't
        found where it should be. See :any:`exceptions.BadExecutionLocation`.
    """
    if not os.path.exists(".hosts-manager.flag"):
        raise exceptions.BadExecutionLocation()

    arguments = docopt(docopt_doc, version="%s %s %s" % (__appname__, __version__, __status__))
    cli = CommandLineTool(arguments)
    cli.run()


if __name__ == "__main__":
    pass
