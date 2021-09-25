#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Module with utility functions and classes.

Attributes
----------
root_folder : str
    The main folder containing the application. All commands must be executed from this location
    without exceptions.
"""
import os
import re
import time

from collections import Callable
from datetime import datetime
from datetime import timedelta
from ipaddress import ip_address
from shutil import copy2
from shutil import rmtree
from socket import gethostname
from subprocess import CalledProcessError
from subprocess import STDOUT
from tempfile import NamedTemporaryFile

from .python_utils import cmd_utils
from .python_utils import exceptions
from .python_utils import file_utils
from .python_utils import json_schema_utils
from .python_utils import shell_utils
from .python_utils import string_utils
from .python_utils import tqdm_wget
from .python_utils import yaml_utils
from .python_utils.ansi_colors import Ansi
from .python_utils.tqdm import tqdm
from .schemas import settings_schema
from .schemas import sources_schema

from .pre_processors import pre_processors as builtin_pre_processors


root_folder = os.path.realpath(os.path.abspath(os.path.join(
    os.path.normpath(os.getcwd()))))

_hostname_regex = re.compile(r"(?!-)[\w-]{1,63}(?<!-)$")
_invalid_ip_msg = "Invalid IP address."
_invalid_integer_msg = "Invalid integer."
_profiles_path = os.path.join(root_folder, "UserData", "profiles")
_user_data_path = os.path.join(root_folder, "UserData")
_invalid_rule = None, None, None
_tar_allowed_args = {
    "--xz",
    "-J",
    "--gzip",
    "-z",
    "--bzip2",
    "-j"
}
_header = """# Date: {date}
# Number of unique domains: {number_of_rules}
# ===============================================================
"""

_header_static_hosts = """
0.0.0.0 0.0.0.0
127.0.0.1 local
127.0.0.1 localhost
127.0.0.1 localhost.localdomain
127.0.0.53 {host_name}
127.0.1.1 {host_name}
255.255.255.255 broadcasthost
::1 ip6-localhost
::1 ip6-loopback
::1 localhost
fe80::1%lo0 localhost
ff00::0 ip6-localnet
ff00::0 ip6-mcastprefix
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
ff02::3 ip6-allhosts

"""


class OverridesValidator(object):
    """Validate a list of settings passed as arguments.
    """
    _valid_settings = {
        "target_ip",
        "keep_domain_comments",
        "skip_static_hosts",
        "custom_static_hosts",
        "backup_old_generated_hosts",
        "backup_system_hosts"
    }

    def __init__(self, raw_overrides):
        """
        Parameters
        ----------
        raw_overrides : list
            The raw list of settings as passed to the CLI.
        """
        self._raw_overrides = raw_overrides
        self._valid_overrides = {}
        self._errors = []

        self._validate_overrides()

    def get_valid_overrides(self):
        """Get valid overrides.

        Returns
        -------
        dict
            The final list of settings validated.
        """
        return self._valid_overrides

    def get_errors(self):
        """Get validation errors.

        Returns
        -------
        list
            A list of validation errors to be displayed.
        """
        return self._errors

    def _validate_overrides(self):
        """Validate the raw overrides.
        """
        for raw_override in self._raw_overrides:
            override = raw_override.split("=")

            if len(override) != 2:
                self._errors.append("Wrong override format: '%s'" %
                                    raw_override + "\n" + "Correct format: 'key=value'")
                continue

            key, value = override

            if key not in self._valid_settings:
                self._errors.append("Wrong key name: '%s'" % key)
                continue

            if key == "target_ip":
                error_msg = _invalid_ip_msg
            elif key == "max_backups_to_keep":
                error_msg = _invalid_integer_msg
            else:
                error_msg = "Valid Boolean values are: true, 1, false or 0. (case insensitive)"

            if key == "target_ip" and is_valid_ip(value):
                self._valid_overrides[key] = value
                continue
            elif key == "max_backups_to_keep" and is_valid_integer(value):
                self._valid_overrides[key] = int(value)
                continue
            elif self._validate_bool(value):
                self._valid_overrides[key] = self._get_bool(value)
                continue
            else:
                self._errors.append("Wrong value for: '%s'" % raw_override + "\n" + error_msg)
                continue

    def _validate_bool(self, value):
        """Validate Boolean.

        Parameters
        ----------
        value : str
            The key value to validate.

        Returns
        -------
        bool
            If it is a valid value for a Boolean.
        """
        return value.lower() in {"true", "false", "0", "1"}

    def _get_bool(self, value):
        """Get a Boolean.

        Parameters
        ----------
        value : str
            The key value already validated.

        Returns
        -------
        bool
            The Boolean.
        """
        return value.lower() in {"true", "1"}


class HostsManager(object):
    """HostsManager class.

    Attributes
    ----------
    logger : object
        See <class :any:`LogSystem`>.
    """

    def __init__(self, profile="", dry_run=False, settings_overrides={}, logger=None):
        """
        Parameters
        ----------
        profile : str, optional
            The profile name.
        dry_run : bool, optional
            Log an action without actually performing it.
        settings_overrides : dict, optional
            A list of settings to override the default ones or the defined in the profile's
            configuration file.
        logger : object
            See <class :any:`LogSystem`>.

        Raises
        ------
        exceptions.MissingConfigFileForProfile
            See <class :any:`exceptions.MissingConfigFileForProfile`>.
        exceptions.NoProfileNameProvided
            See <class :any:`exceptions.NoProfileNameProvided`>.
        """
        if not profile:
            raise exceptions.NoProfileNameProvided("No profile name was provided.")

        self.logger = logger
        self._dry_run = dry_run
        self._merge_blacklist_file = None
        self._merge_whitelist_file = None
        self._final_file = None
        self._current_date = time.strftime("%B %d %Y", time.gmtime())  # Format = January 1 2018
        self._profile_path = os.path.join(_profiles_path, profile)

        try:
            with open(os.path.join(self._profile_path, "config.yaml"), "r") as config_file:
                config = yaml_utils.load(config_file)
        except Exception as err:
            self.logger.error(err, term=False)
            raise exceptions.MissingConfigFileForProfile(err)

        self._sources = config.get("sources", None)

        self._validate_sources()

        # Customizable settings.
        self._settings = {
            "target_ip": "0.0.0.0",
            "keep_domain_comments": False,
            "skip_static_hosts": False,
            "custom_static_hosts": "",
            "backup_old_generated_hosts": True,
            "backup_system_hosts": True,
            "max_backups_to_keep": 10,
        }

        profile_settings = config.get("settings", {})
        profile_settings.update(settings_overrides)

        self._settings.update(profile_settings)

        self._last_update_data = {}
        # Changing self._exclusions from a list to a set improved items iterations
        # from ~50.000 it/s to ~75.000 it/s.
        self._exclusions = set()
        self._compressed_sources = []
        self._number_of_rules = 0
        self._number_of_ignores = 0

        self._max_backups_to_keep = profile_settings.get("max_backups_to_keep", 10)

        self._validate_option_keys()

        # Paths to files/folders.
        self._hosts_file_path = os.path.join(self._profile_path, "hosts")
        sources_storage = os.path.join(self._profile_path, "sources_storage")
        self._sources_storage_raw = os.path.join(sources_storage, "raw")
        self._sources_storage_compressed = os.path.join(sources_storage, "compressed")
        self._sources_last_updated = os.path.join(self._profile_path, "last-updated.yaml")
        self._backups_storage = os.path.join(self._profile_path, "backups_storage")
        self._profile_whitelist_path = os.path.join(self._profile_path, "whitelist")
        self._global_whitelist_path = os.path.join(_user_data_path, "global_whitelist")
        self._profile_blacklist_path = os.path.join(self._profile_path, "blacklist")
        self._global_blacklist_path = os.path.join(_user_data_path, "global_blacklist")

        self._ensure_paths()
        self._expand_local_sources_data()

    def _log_shell_separator(self, char="-"):
        """Summary

        Parameters
        ----------
        char : str, optional
            Character used to generate the "CLI separator".
        """
        self.logger.info(shell_utils.get_cli_separator(char), date=False)

    def _validate_sources(self):
        """Validate sources.

        Raises
        ------
        exceptions.MalformedSources
            See <class :any:`exceptions.MalformedSources`>.
        exceptions.MissingSourcesOnConfigFile
            See <class :any:`exceptions.MissingSourcesOnConfigFile`>.
        """
        if not self._sources:
            raise exceptions.MissingSourcesOnConfigFile(
                "The 'sources' variable is not declared or it's empty.")

        if json_schema_utils.JSONSCHEMA_INSTALLED:
            json_schema_utils.validate(
                self._sources, sources_schema,
                error_message_extra_info="\n".join([
                    "File: %s" % os.path.join(self._profile_path, "config.yaml"),
                    "Data key: sources"
                ]),
                logger=self.logger)

        names = set()
        errors = []

        # TODO: Find a way to validate the following using JSON schema.
        # This doesn't seem possible with current JSON schema standards.
        # Checked up to daft 4 of the JSON schema standard.
        # Revisit when the stable version of the jsonschema module implements
        # the draft 7 of the standard.
        for source in self._sources:
            source_name = source.get("name", False)

            if source_name:
                # Do not allow more than one source with the same "name".
                if source_name in names:
                    errors.append("More than one source with the same name. <%s>" % source_name)
                else:
                    names.add(source_name)

        if errors:
            raise exceptions.MalformedSources(
                "Error/s found that must be fixed!!!\n%s" % "\n".join(errors))

    def _expand_local_sources_data(self):
        """Add additional data to the sources.
        """
        try:
            with open(self._sources_last_updated, "r", encoding="UTF-8") as json_file:
                self._last_update_data = yaml_utils.load(json_file)
        except Exception:
            self._last_update_data = {}

        for source in self._sources:
            # Generate and add "slugified_name".
            source["slugified_name"] = "hosts-%s" % string_utils.slugify(source["name"])

            # Generate and add the path for the downloaded file.
            if source.get("unzip_prog", False):
                source["downloaded_filename"] = \
                    os.path.join(self._sources_storage_compressed,
                                 source["slugified_name"],
                                 source["slugified_name"])
            else:
                source["downloaded_filename"] = os.path.join(
                    self._sources_storage_raw, source["slugified_name"])

            # Insert the date in which the source was last updated.
            if self._last_update_data:
                source["last_updated"] = self._last_update_data.get(source["slugified_name"], None)

        # Lastly, sort dictionaries by source names.
        self._sources = sorted(self._sources, key=lambda name: name["name"])

    def _validate_option_keys(self):
        """Validate keys.
        """
        if json_schema_utils.JSONSCHEMA_INSTALLED:
            json_schema_utils.validate(
                self._settings, settings_schema,
                error_message_extra_info="\n".join([
                    "File: %s" % os.path.join(self._profile_path, "config.yaml"),
                    "Data key: settings"
                ]),
                logger=self.logger)

    def install_hosts_file(self):
        """Install the generated hosts file.
        """
        self._log_shell_separator("#")

        print(Ansi.LIGHT_MAGENTA("Moving the hosts file requires administrative privileges.\n"
                                 "You might need to enter your password."))

        if self._settings["backup_system_hosts"]:
            try:
                self.logger.info("Backing up the system's hosts file...")
                backup_file_path = os.path.join(self._backups_storage, "system-hosts-{}".format(
                    time.strftime("%Y-%m-%d-%H-%M-%S")))

                if self._dry_run:
                    self.logger.log_dry_run("The file at /etc/hosts will be backed up into:\n%s"
                                            % backup_file_path)
                    self.logger.log_dry_run("Surplus files will be removed inside the folder:\n%s"
                                            % self._backups_storage)
                else:
                    copy2("/etc/hosts", backup_file_path)
                    file_utils.remove_surplus_files(self._backups_storage, "system-hosts-*",
                                                    max_files_to_keep=self._settings["max_backups_to_keep"])
            except Exception as err:
                self.logger.error(err)

        self._install_hosts_file()

    def build_hosts_file(self):
        """Build the hosts file from the local sources.
        """
        self._log_shell_separator("#")

        self._create_temporary_files()
        self._remove_old_hosts_file()
        self._populate_exclusions_list()
        self._populate_final_file()
        self._write_opening_header()
        self.logger.info("Hosts file building finished.")
        self.logger.info("It contains {:,} unique entries.".format(self._number_of_rules))

        if self._number_of_ignores:
            self.logger.warning(
                "A total of {:,} rules were ignored.".format(self._number_of_ignores))
            self.logger.warning("(Ignored rules are listed inside the log file)")

    def update_all_sources(self, force_update):
        """Update all host files, regardless of folder depth.

        Parameters
        ----------
        force_update : bool
            Ignore source update frequency and update its file/s anyway.

        Raises
        ------
        exceptions.KeyboardInterruption
            See <class :any:`exceptions.KeyboardInterruption`>.
        """
        self._log_shell_separator("#")
        self.logger.info("Updating sources...")

        if force_update:
            if self._dry_run:
                self.logger.log_dry_run("The following directory will be removed:\n%s" %
                                        "\n".join([self._sources_storage_raw,
                                                   self._sources_storage_compressed]))
            else:
                rmtree(self._sources_storage_raw)
                rmtree(self._sources_storage_compressed)

        try:
            for source in self._sources:
                self._log_shell_separator()

                if force_update or self._should_update_source(source):
                    self.logger.info("Updating source <%s>" % source["name"])

                    try:
                        self._download_source(source)
                    except Exception as err:
                        self.logger.error("Error in updating source. URL: ", source["url"])
                        self.logger.error(err)
                        continue
                    except (KeyboardInterrupt, SystemExit):
                        raise exceptions.KeyboardInterruption()
                else:
                    self.logger.info("Source <%s> doesn't need updating." % source["name"])
        except (KeyboardInterrupt, SystemExit):
            raise exceptions.KeyboardInterruption()
        else:
            if self._dry_run:
                self.logger.log_dry_run("Last update data for sources will be saved at:\n%s" %
                                        self._sources_last_updated)
            else:
                with open(self._sources_last_updated, "w", encoding="UTF-8") as data_file:
                    yaml_utils.dump(self._last_update_data, data_file)

        if self._compressed_sources:
            self._handle_compressed_sources()

    def _should_update_source(self, source):
        """Check if source should be updated.

        Parameters
        ----------
        source : dict
            The source to check.

        Returns
        -------
        bool
            If the source needs to be updated depending on its configured specified
            update frequency.
        """
        frequency = source.get("frequency", "m")
        last_updated = source.get("last_updated", False)

        if frequency == "d" or not last_updated:
            return True

        downloaded_filename = source.get("downloaded_filename", False)
        downloaded_filename_exists = downloaded_filename and os.path.exists(downloaded_filename)

        # Check separated to avoid unnecessary file existence checks.
        if not downloaded_filename_exists:
            return True

        try:
            then = datetime.strptime(last_updated, "%B %d %Y")
            now = datetime.strptime(self._current_date, "%B %d %Y")

            if frequency == "w":  # Weekly.
                return (now - then) > timedelta(days=6)
            elif frequency == "m":  # Monthly.
                return (now - then) > timedelta(days=29)
            elif frequency == "s":  # Semestrial.
                return (now - then) > timedelta(days=87)
        except Exception:
            return True

    def _install_hosts_file(self):
        """Copy the newly-created hosts file into its correct location on the OS.
        """
        self.logger.info("Installing hosts file...")

        if os.path.exists(self._hosts_file_path):
            cmd = ["/usr/bin/sudo", "cp", self._hosts_file_path, "/etc/hosts"]

            if self._dry_run:
                self.logger.log_dry_run("Command that will be executed:\n%s" % " ".join(cmd))
            else:
                if cmd_utils.run_cmd(cmd, stdout=None, stderr=None).returncode:
                    self.logger.error("Copying the file failed.")
                else:
                    self.logger.success("Hosts file successfully installed.")

            forget_credentials_cmd = ["/usr/bin/sudo", "-K"]
            forget_credentials_msg = "Removing cached sudo credentials {result}."

            if self._dry_run:
                self.logger.log_dry_run("Command that will be executed:\n%s" %
                                        " ".join(forget_credentials_cmd))
            else:
                if cmd_utils.run_cmd(forget_credentials_cmd, stdout=None, stderr=None).returncode:
                    self.logger.error(forget_credentials_msg.format(result="failed"))
                else:
                    self.logger.success(forget_credentials_msg.format(result="succeeded"))
        else:
            self.logger.warning("There doesn't seem to be a generated hosts file.")

    def _download_source(self, source):
        """Download the source files.

        Parameters
        ----------
        source : dict
            The source data.

        Raises
        ------
        exceptions.KeyboardInterruption
            See <class :any:`exceptions.KeyboardInterruption`>.
        """
        is_compressed_source = source.get("unzip_prog")

        parent_dir = os.path.dirname(source["downloaded_filename"])

        if not file_utils.is_real_dir(parent_dir):
            if self._dry_run:
                self.logger.log_dry_run("Directory will be created at:\n%s" % parent_dir)
            else:
                try:
                    os.makedirs(parent_dir, exist_ok=True)
                except Exception as err:
                    self.logger.error(err)

        try:
            if self._dry_run:
                self.logger.log_dry_run("File will be downloaded:")
                self.logger.log_dry_run("URL: %s" % source["url"])
                self.logger.log_dry_run("Location: %s" % source["downloaded_filename"])
            else:
                tqdm_wget.download(source["url"], source["downloaded_filename"])
        except (KeyboardInterrupt, SystemExit):
            raise exceptions.KeyboardInterruption()
        except Exception as err:
            self.logger.error(err)
        else:
            if not self._dry_run:
                self._last_update_data[source["slugified_name"]] = self._current_date

            if is_compressed_source:
                self._compressed_sources.append(source)

    def _handle_compressed_sources(self):
        """Handle the downloaded sources with compressed files.

        Raises
        ------
        exceptions.KeyboardInterruption
            See <class :any:`exceptions.KeyboardInterruption`>.
        """
        self._log_shell_separator("#")
        self.logger.info("Handling compressed sources...")

        try:
            for source in self._compressed_sources:
                self._log_shell_separator()
                self.logger.info("Decompressing source <%s>." % source["name"])

                aborted_msg = "Extract operation for <%s> aborted." % source["name"]
                src_dir_path = os.path.dirname(source["downloaded_filename"])
                src_path = os.path.join(src_dir_path, source["unzip_target"])
                dst_path = os.path.join(self._sources_storage_raw,
                                        os.path.basename(source["downloaded_filename"]))
                cmd = []

                if not cmd_utils.which(source["unzip_prog"]):
                    self.logger.error("Command <%s> not found on your system." %
                                      source["unzip_prog"] + aborted_msg)
                    continue

                if source["unzip_prog"] == "7z":
                    cmd += ["7z", "e", "-y", source["downloaded_filename"]]
                elif source["unzip_prog"] == "unzip":
                    cmd += ["unzip", "-o", source["downloaded_filename"]]
                elif source["unzip_prog"] == "tar":
                    untar_arg = source.get("untar_arg")
                    cmd = ["tar", "--extract"]

                    if untar_arg:
                        if untar_arg not in _tar_allowed_args:
                            self.logger.warning("untar_arg key ignored!")
                            self.logger.warning("Allowed arguments are:\n%s" %
                                                ", ".join(_tar_allowed_args))
                        else:
                            cmd += [untar_arg]

                    cmd += [
                        "--file",
                        source["downloaded_filename"],
                        "--totals"
                    ]

                if cmd:
                    try:
                        if self._dry_run:
                            self.logger.log_dry_run(
                                "Command that will be executed:\n%s" % " ".join(cmd))
                        else:
                            self.logger.info("Running command:\n%s" % " ".join(cmd))

                            cmd_utils.run_cmd(cmd,
                                              stderr=STDOUT,
                                              check=True,
                                              cwd=src_dir_path)

                        if os.path.exists(dst_path):
                            if self._dry_run:
                                self.logger.log_dry_run("File will be removed:\n%s"
                                                        % dst_path)
                            else:
                                os.remove(dst_path)

                        if self._dry_run:
                            self.logger.log_dry_run("File will be copied:")
                            self.logger.log_dry_run("Source: %s" % src_path)
                            self.logger.log_dry_run("Destination: %s" % dst_path)
                        else:
                            copy2(src_path, dst_path)
                    except Exception as err1:
                        self.logger.error(err1)
                        continue
                    except CalledProcessError as err2:
                        self.logger.error(err2)
                        continue
        except (KeyboardInterrupt, SystemExit):
            raise exceptions.KeyboardInterruption()

    def _write_opening_header(self):
        """Write the header information into the newly-created hosts file.
        """
        self.logger.info("Writing the opening header...")
        self._final_file.seek(0)  # Reset file pointer.
        file_contents = self._final_file.readlines()  # Store content.
        file_contents.sort()  # Sort content.

        self._final_file.seek(0)  # Write at the top.

        header = _header.format(
            date=self._current_date,
            number_of_rules="{:,}".format(self._number_of_rules)
        )

        if not self._settings["skip_static_hosts"]:
            header += _header_static_hosts.format(host_name=gethostname())

        if self._settings["custom_static_hosts"]:
            header += self._settings["custom_static_hosts"].format(host_name=gethostname())

        self._final_file.write(bytes(header, "UTF-8"))
        self._final_file.writelines(file_contents)

        base_msg = "Newly generated hosts file at:\n%s"

        if self._dry_run:
            self.logger.log_dry_run(
                "The following temporary file will not be automatically deleted:")
            self.logger.log_dry_run(base_msg % self._final_file.name)
        else:
            self.logger.info(base_msg % self._hosts_file_path)

        self._final_file.close()

    def _remove_old_hosts_file(self):
        """Remove the old generated hosts file.

        This is a hotfix because merging with an already existing hosts file leads
        to artifacts and duplicates.
        """
        self.logger.info("Removing old generated hosts file...")

        if self._dry_run:
            self.logger.log_dry_run("The following actions will be performed at:\n%s" %
                                    "\n".join([
                                        self._hosts_file_path,
                                        "- Back up the file if the appropriate option is enabled.",
                                        "- Remove the file if it exists.",
                                        "- And finally create an empty file."
                                    ]))
        else:
            # Create if already removed, so remove won't raise an error.
            open(self._hosts_file_path, "a").close()

            if self._settings["backup_old_generated_hosts"]:
                backup_file_path = os.path.join(self._backups_storage, "generated-hosts-{}".format(
                    time.strftime("%Y-%m-%d-%H-%M-%S")))

                # Make a backup copy, marking the date in which the list was updated
                copy2(self._hosts_file_path, backup_file_path)
                self.logger.info("Old generated hosts file backed up...")
                file_utils.remove_surplus_files(self._backups_storage, "generated-hosts-*",
                                                max_files_to_keep=self._settings["max_backups_to_keep"])

            os.remove(self._hosts_file_path)
            self.logger.info("Old generated hosts file removed...")

            # Create new empty hosts file
            open(self._hosts_file_path, "a").close()

    def _ensure_paths(self):
        """Ensure the existence of some folders inside the profile folder.
        """
        if self._dry_run:
            self.logger.log_dry_run("The following directories will be created:\n%s" %
                                    "\n".join([self._sources_storage_raw,
                                               self._sources_storage_compressed,
                                               self._backups_storage]))
        else:
            os.makedirs(self._sources_storage_raw, exist_ok=True)
            os.makedirs(self._sources_storage_compressed, exist_ok=True)
            os.makedirs(self._backups_storage, exist_ok=True)

    def _create_temporary_files(self):
        """Create temporary files.

        Initialize the files in which all source files will be merged for later pruning.
        """
        self._merge_blacklist_file = NamedTemporaryFile()
        self._merge_whitelist_file = NamedTemporaryFile()

        self.logger.info("Creating initial temporary file...")
        self.logger.info("Collecting data from raw sources...")

        for s in tqdm(range(len(self._sources))):
            source = self._sources[s]
            source_path = os.path.join(self._sources_storage_raw, source["slugified_name"])

            if os.path.isfile(source_path):
                source_data = None

                # Deal only with UTF-8 and cp1252 encodings.
                # If a source with any other encoding is found, FORGET OF ITS EXISTENCE!!!
                try:
                    with open(source_path, "r", encoding="UTF-8") as curFile:
                        source_data = curFile.read()
                except UnicodeDecodeError:
                    try:
                        with open(source_path, "r", encoding="cp1252") as curFile:
                            source_data = curFile.read()
                    except UnicodeDecodeError as err:
                        self.logger.warning("Attempt to open file with cp1252 encoding failed.")
                        self.logger.warning("File ignored.")
                        self.logger.error(err)
                        continue

                if source_data:
                    source_data = source_data.replace("\r", "")

                    if source.get("pre_processors"):
                        for pp in source.get("pre_processors"):
                            try:
                                if isinstance(pp, Callable):
                                    pp_qual_name = pp.__qualname__
                                    source_data = pp(source_data, self.logger)
                                elif pp in builtin_pre_processors:
                                    builtin_pre_pro = builtin_pre_processors.get(pp)
                                    pp_qual_name = builtin_pre_pro.__qualname__
                                    source_data = builtin_pre_pro(source_data, self.logger)
                            except Exception as err:
                                # Log the pre-processor function's qualified name.
                                self.logger.error("Pre-processor error: %s" % pp_qual_name)
                                self.logger.error(err)
                                continue

                    getattr(self,
                            "_merge_whitelist_file"
                            if source.get("is_whitelist") else
                            "_merge_blacklist_file"
                            ).write(bytes(source_data + "\n", "UTF-8"))

        self.logger.info("Collecting data from blacklist files...")

        for blacklist_file in [self._profile_blacklist_path, self._global_blacklist_path]:
            if os.path.isfile(blacklist_file):
                self.logger.info("Adding data from <%s>" %
                                 os.path.relpath(blacklist_file, _user_data_path))
                with open(blacklist_file, "r", encoding="UTF-8") as curFile:
                    self._merge_blacklist_file.write(bytes(curFile.read(), "UTF-8"))

    def _populate_exclusions_list(self):
        """Populate exclusions list.

        Raises
        ------
        exceptions.KeyboardInterruption
            See <class :any:`exceptions.KeyboardInterruption`>.
        """
        self.logger.info("Populating the exclusions list...")

        self.logger.info("Processing local whitelist files...")

        for whitelist_file in [self._profile_whitelist_path, self._global_whitelist_path]:
            if os.path.isfile(whitelist_file):
                self.logger.info("Adding data from <%s>..." %
                                 os.path.relpath(whitelist_file, _user_data_path))
                with open(whitelist_file, "r", encoding="UTF-8") as ins:
                    for line in ins:
                        line = line.strip(" \t\n\r")

                        if line and line[0] != "#":
                            self._exclusions.add(line)

        self.logger.info("Processing whitelist sources...")

        self._merge_whitelist_file.seek(0)  # reset file pointer
        merge_whitelist_file_lines = self._merge_whitelist_file.readlines()

        try:
            for l in tqdm(range(len(merge_whitelist_file_lines))):
                line = merge_whitelist_file_lines[l].decode("UTF-8").strip()

                if line and line[0] != "#" and line[:3] != "::1":
                    target_ip, hostname, comment = self._normalize_rule(line)

                    if hostname:
                        self._exclusions.add(hostname)
        except (KeyboardInterrupt, SystemExit):
            self._merge_whitelist_file.close()
            raise exceptions.KeyboardInterruption()

        self._merge_whitelist_file.close()

    def _populate_final_file(self):
        """Populate the final hosts file.

        Remove duplicates and remove hosts that we are excluding.

        We check for duplicate host names as well as remove any host names that
        have been explicitly excluded by the user.

        Raises
        ------
        exceptions.KeyboardInterruption
            See <class :any:`exceptions.KeyboardInterruption`>.
        """
        self.logger.info("Populating the new generated hosts file...")

        if self._dry_run:
            self._final_file = NamedTemporaryFile(prefix="generated-hosts-file-", delete=False)
        else:
            self._final_file = open(self._hosts_file_path, "w+b")

        self._merge_blacklist_file.seek(0)  # reset file pointer

        hostnames = {
            "0.0.0.0"
            "broadcasthost",
            "ip6-allhosts",
            "ip6-allnodes",
            "ip6-allrouters",
            "ip6-localhost",
            "ip6-localnet",
            "ip6-loopback",
            "ip6-mcastprefix",
            "local",
            "localhost",
            "localhost.localdomain",
        }

        cache_size = 250000
        cache_storage = ""

        merge_blacklist_file_lines = self._merge_blacklist_file.readlines()
        processed_lines = len(merge_blacklist_file_lines)

        self.logger.info("Adding rules to the final hosts file...")
        try:
            # DO NOT USE "continue" INSIDE THIS LOOP!!!
            for l in tqdm(range(len(merge_blacklist_file_lines))):
                line = merge_blacklist_file_lines[l].decode("UTF-8").strip()
                processed_lines -= 1
                normalized_rule = ""

                # Do not use continue. This is to avoid exiting the loop
                # while there is still data stored inside cache_storage.
                if line and line[0] != "#" and line[:3] != "::1":
                    # Normalize rule.
                    target_ip, hostname, comment = self._normalize_rule(line)

                    # Changing self._exclusions from a list to a set improved items
                    # iterations from ~50.000 it/s to ~75.000 it/s.
                    if hostname and hostname not in self._exclusions:
                        if comment and self._settings["keep_domain_comments"]:
                            normalized_rule = "%s %s #%s" % (target_ip, hostname, comment)
                        else:
                            normalized_rule = "%s %s" % (target_ip, hostname)

                        if normalized_rule and (hostname not in hostnames):
                            cache_size -= 1
                            cache_storage += normalized_rule + "\n"
                            hostnames.add(hostname)
                            self._number_of_rules += 1

                if (cache_size == 1 and cache_storage) or processed_lines == 1:
                    self._final_file.write(bytes(cache_storage, "UTF-8"))
                    cache_storage = ""
                    cache_size = 250000
        except (KeyboardInterrupt, SystemExit):
            self._merge_blacklist_file.close()
            raise exceptions.KeyboardInterruption()

        self._merge_blacklist_file.close()

    def _normalize_rule(self, line):
        """Standardize and format the rule string provided.

        Parameters
        ----------
        line : str
            The line to be standardized.

        Returns
        -------
        tuple
            The rules elements.
        """
        try:
            stripped_rule, comment = [part.strip() for part in line.split("#", 1)]
        except Exception:
            stripped_rule, comment = line.strip(), ""

        rule_parts = stripped_rule.split()

        try:
            try:
                # In "ip host" format. Most likely a line from a file in hosts format.
                hostname = rule_parts[1].lower()
            except Exception:
                # In "host" format. Most likely a line for a file with a list of domains.
                hostname = rule_parts[0].lower()
        except Exception:
            hostname = None

        if hostname and is_valid_host(hostname):
            return self._settings["target_ip"], hostname, comment
        else:
            self._number_of_ignores += 1
            self.logger.warning("Ignored line: %s" % line, term=False, date=False)

        return _invalid_rule


def is_valid_host(host):
    """IDN compatible domain validation.

    Parameters
    ----------
    host : str
        The host name to check.

    Returns
    -------
    bool
        Whether the host name is valid or not.

    Note
    ----
    Based on: `Validate-a-hostname-string \
    <https://stackoverflow.com/questions/2532053/validate-a-hostname-string>`__
    """
    host = host.rstrip(".")

    return all([len(host) > 1,
                len(host) < 253] + [_hostname_regex.match(x) for x in host.split(".")])


def is_valid_ip(address):
    """Validate IP address (IPv4 or IPv6).

    Parameters
    ----------
    address : str
        The IP address to validate.

    Returns
    -------
    bool
        If it is a valid IP address or not.
    """
    try:
        ip_address(address)
    except ValueError:
        return False

    return True


def is_valid_integer(integer):
    """Validate integer.

    Parameters
    ----------
    integer : str
        The string to validate.

    Returns
    -------
    bool
        If the value is a valid integer or not.
    """
    return str(integer).isdigit()


def flush_dns_cache(dry_run=False, logger=None):
    """Flush the DNS cache.

    Parameters
    ----------
    dry_run : bool, optional
        Log an action without actually performing it.
    logger : object
        See <class :any:`LogSystem`>.
    """
    print(Ansi.LIGHT_MAGENTA("""Flushing the DNS cache to utilize new hosts file...
Flushing the DNS cache requires administrative privileges.
You will need to enter your password.
"""))

    dns_cache_found = False

    nscd_prefixes = ["/etc", "/etc/rc.d"]
    nscd_msg = "Flushing the DNS cache by restarting nscd {result}."

    for nscd_prefix in nscd_prefixes:
        nscd_cache = nscd_prefix + "/init.d/nscd"

        if os.path.isfile(nscd_cache):
            dns_cache_found = True
            nscd_cmd = ["/usr/bin/sudo", nscd_cache, "restart"]

            if dry_run:
                logger.info("Command that will be executed:\n%s" % " ".join(nscd_cmd))
            else:
                if cmd_utils.run_cmd(nscd_cmd, stdout=None, stderr=None).returncode:
                    logger.error(nscd_msg.format(result="failed"))
                else:
                    logger.success(nscd_msg.format(result="succeeded"))

    system_prefixes = ["/usr", ""]
    service_types = ["NetworkManager", "wicd", "dnsmasq", "networking"]

    for system_prefix in system_prefixes:
        systemctl = system_prefix + "/bin/systemctl"
        system_dir = system_prefix + "/lib/systemd/system"

        for service_type in service_types:
            service = service_type + ".service"
            service_file = os.path.join(system_dir, service)
            service_msg = "Flushing the DNS cache by restarting " + service + " {result}."

            if os.path.isfile(service_file):
                dns_cache_found = True
                dns_service_cmd = ["/usr/bin/sudo", systemctl, "restart", service]

                if dry_run:
                    logger.info("Command that will be executed:\n%s" % " ".join(dns_service_cmd))
                else:
                    if cmd_utils.run_cmd(dns_service_cmd, stdout=None, stderr=None).returncode:
                        logger.error(service_msg.format(result="failed"))
                    else:
                        logger.success(service_msg.format(result="succeeded"))

    dns_clean_file = "/etc/init.d/dns-clean"
    dns_clean_msg = "Flushing the DNS cache via dns-clean executable {result}."

    if os.path.isfile(dns_clean_file):
        dns_cache_found = True
        dns_clean_cmd = ["/usr/bin/sudo", dns_clean_file, "start"]

        if dry_run:
            logger.info("Command that will be executed:\n%s" % " ".join(dns_clean_cmd))
        else:
            if cmd_utils.run_cmd(dns_clean_cmd, stdout=None, stderr=None).returncode:
                logger.error(dns_clean_msg.format(result="failed"))
            else:
                logger.success(dns_clean_msg.format(result="succeeded"))

    if not dns_cache_found:
        logger.warning("Unable to determine DNS management tool.")

    forget_credentials_cmd = ["/usr/bin/sudo", "-K"]
    forget_credentials_msg = "Removing cached sudo credentials {result}."

    if dry_run:
        logger.info("Command that will be executed:\n%s" % " ".join(forget_credentials_cmd))
    else:
        if cmd_utils.run_cmd(forget_credentials_cmd, stdout=None, stderr=None).returncode:
            logger.error(forget_credentials_msg.format(result="failed"))
        else:
            logger.success(forget_credentials_msg.format(result="succeeded"))


def new_profile_generation(logger):
    """Generate a new profile.

    Parameters
    ----------
    logger : object
        See <class :any:`LogSystem`>.
    """
    from.python_utils import prompts, template_utils
    config_template = os.path.join(root_folder, "AppData", "data", "templates", "config.yaml")

    d = {
        "name": "default"
    }

    prompts.do_prompt(d, "name", "Enter a profile name", "default")

    new_profile_path = os.path.join(_profiles_path, d["name"])

    if os.path.exists(new_profile_path):
        logger.warning("Profile seems to exists. Choose a different name.")
        new_profile_generation(logger)
    else:
        os.makedirs(new_profile_path, exist_ok=True)
        config_path = os.path.join(new_profile_path, "config.yaml")
        template_utils.generate_from_template(config_template, config_path, logger=logger)
        logger.info("New profile generated.")


if __name__ == "__main__":
    pass
