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
from .__init__ import __appdescription__
from .__init__ import __appname__
from .__init__ import __status__
from .__init__ import __version__
from .python_utils import cli_utils
from .python_utils import exceptions
from .python_utils import shell_utils


root_folder = os.path.realpath(os.path.abspath(os.path.join(
    os.path.normpath(os.getcwd()))))


docopt_doc = """{appname} {version} ({status})

{appdescription}

Usage:
    app.py (-h | --help | --manual | --version)
    app.py (-f | --flush-dns-cache) [-d | --dry-run]
    app.py run (update | build | install) [update] [build] [install]
               (-p <name> | --profile=<name>)
               [-o <key=value>... | --override=<key=value>...]
               [-f | --flush-dns-cache]
               [-u | --force-update]
               [-d | --dry-run]
    app.py server (start | stop | restart)
                  [--host=<host>]
                  [--port=<port>]
    app.py generate (system_executable | new_profile)

Options:

-h, --help
    Show this screen.

--manual
    Show this application manual page.

--version
    Show application version.

-p <name>, --profile=<name>
    The profile name to work with.

-o <key=value>, --override=<key=value>
    One or more sets of <key=value> that will override the configuration
    options set in the conf.py file.

-f, --flush-dns-cache
    Attempt to flush DNS cache for the new hosts file to take effect.

-u, --force-update
    Force the update of all sources, ignoring the frequency in which they
    should be updated. All previously downloaded sources will be removed.

-d, --dry-run
    Do not perform file system changes. Only display messages informing of the
    actions that will be performed or commands that will be executed.
    WARNING! Some file system changes will be performed (e.g., temporary files
    creation).

--host=<host>
    Host name. [Default: 0.0.0.0]

--port=<port>
    Port number. [Default: 80]

""".format(appname=__appname__,
           appdescription=__appdescription__,
           version=__version__,
           status=__status__)


class CommandLineInterface(cli_utils.CommandLineInterfaceSuper):
    """Command line interface.

    It handles the arguments parsed by the docopt module.

    Attributes
    ----------
    a : dict
        Where docopt_args is stored.
    func_names : list
        The name of the functions to run.
    hosts_manager : object
        See <class :any:`app_utils.HostsManager`>.
    """
    # Execution order depends on the order the function names were appended.
    func_names = []

    def __init__(self, docopt_args):
        """
        Parameters
        ----------
        docopt_args : dict
            The dictionary of arguments as returned by docopt parser.
        """
        self.a = docopt_args
        self._cli_header_blacklist = [self.a["--manual"]]

        super().__init__(__appname__, "UserData/logs")

        if self.a["--manual"]:
            self.func_names.append("display_manual_page")
        elif self.a["generate"]:
            if self.a["system_executable"]:
                self.func_names.append("system_executable_generation")

            if self.a["new_profile"]:
                self.func_names.append("new_profile_generation")
        elif self.a["server"]:
            self.logger.info("Command: server")
            self.logger.info("Arguments:")

            if self.a["start"]:
                self.logger.info("start")
                self.func_names.append("http_server_start")
            elif self.a["stop"]:
                self.logger.info("stop")
                self.func_names.append("http_server_stop")
            elif self.a["restart"]:
                self.logger.info("restart")
                self.func_names.append("http_server_restart")
        elif self.a["run"]:
            # Workaround docopt issue:
            # https://github.com/docopt/docopt/issues/134
            # Not perfect, but good enough for this particular usage case.
            args_overrides = list(set(self.a["--override"]))

            overrides_validator = app_utils.OverridesValidator(args_overrides)
            override_errors = overrides_validator.get_errors()

            if override_errors:
                self.logger.warning(
                    "Exiting due to errors found while processing the provided overrides:", date=False)

                for error in override_errors:
                    self.logger.info(shell_utils.get_cli_separator(), date=False)
                    self.logger.warning(error, date=False)

                sys.exit(0)

            self.hosts_manager = app_utils.HostsManager(profile=self.a["--profile"],
                                                        dry_run=self.a["--dry-run"],
                                                        settings_overrides=overrides_validator.get_valid_overrides(),
                                                        logger=self.logger)
            self.logger.info("Command: run")
            self.logger.info("Arguments:")

            if self.a["update"]:
                self.logger.info("update")
                self.func_names.append("update_all_sources")

            if self.a["build"]:
                self.logger.info("build")
                self.func_names.append("build_hosts_file")

            if self.a["install"]:
                self.logger.info("install")
                self.func_names.append("install_hosts_file")

        if self.a["--flush-dns-cache"]:
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
        """See :any:`app_utils.HostsManager.update_all_sources`
        """
        self.hosts_manager.update_all_sources(self.a["--force-update"])

    def build_hosts_file(self):
        """See :any:`app_utils.HostsManager.build_hosts_file`
        """
        self.hosts_manager.build_hosts_file()

    def install_hosts_file(self):
        """See :any:`app_utils.HostsManager.install_hosts_file`
        """
        self.hosts_manager.install_hosts_file()

    def flush_dns_cache(self):
        """See :any:`app_utils.flush_dns_cache`
        """
        app_utils.flush_dns_cache(dry_run=self.a["--dry-run"],
                                  logger=self.logger)

    def system_executable_generation(self):
        """See :any:`cli_utils.CommandLineInterfaceSuper._system_executable_generation`.
        """
        self._system_executable_generation(
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
        cmd_path = os.path.join(root_folder, "AppData", "data", "python_scripts", "http_server")

        # Use of os.execv() so at the end only one process is left executing.
        # The "http_server" executable also uses os.execv() to launch the real web application.
        os.execv(cmd_path, [" "] + [action,
                                    "HostsManager",
                                    self.a["--host"],
                                    self.a["--port"]])

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

    def display_manual_page(self):
        """See :any:`cli_utils.CommandLineInterfaceSuper._display_manual_page`.
        """
        self._display_manual_page(os.path.join(root_folder, "AppData", "data", "man", "app.py.1"))


def main():
    """Initialize command line interface.
    """
    cli_utils.run_cli(flag_file=".hosts-manager.flag",
                      docopt_doc=docopt_doc,
                      app_name=__appname__,
                      app_version=__version__,
                      app_status=__status__,
                      cli_class=CommandLineInterface)


if __name__ == "__main__":
    pass
