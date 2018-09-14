#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Module with utility functions and classes.

Attributes
----------
HOSTNAME_REGEX : re
    Regular expression used to validate the host names.
INVALID_INTEGER_MSG : str
    Message to show validating integers.
INVALID_IP_MSG : str
    Message to show validating IP addresses.
root_folder : str
    The main folder containing the application. All commands must be executed from this location
    without exceptions.
"""

import json
import os
import re
import sys
import time

from datetime import datetime, timedelta
from ipaddress import ip_address
from runpy import run_path
from shutil import copy2
from socket import gethostname
from subprocess import call, Popen, STDOUT, PIPE
from tempfile import NamedTemporaryFile

from .python_utils import exceptions, tqdm, tqdm_wget, file_utils, cmd_utils
from .python_utils.ansi_colors import Ansi

try:
    from slugify import slugify
except (SystemError, ImportError):
    raise exceptions.MissingDependencyModule("Module not installed: <python-slugify>")


root_folder = os.path.realpath(os.path.abspath(os.path.join(
    os.path.normpath(os.getcwd()))))

HOSTNAME_REGEX = re.compile(r"(?!-)[\w-]{1,63}(?<!-)$")
INVALID_IP_MSG = "Invalid IP address."
INVALID_INTEGER_MSG = "Invalid integer."


class ValidatedOverrides(object):
    """Validate a list of options passed as arguments.

    Attributes
    ----------
    errors : list
        A list of validation errors to be displayed.
    raw_overrides : list
        The raw list of options as passed to the CLI.
    valid_options : list
        The list of valid options used to check.
    valid_overrides : dict
        The final list of options validated.
    """
    valid_options = [
        "target_ip",
        "keep_domain_comments",
        "skip_static_hosts",
        "backup_old_generated_hosts",
        "backup_system_hosts"
    ]

    def __init__(self, raw_overrides):
        """
        Parameters
        ----------
        raw_overrides : list
            The raw list of options as passed to the CLI.
        """
        super(ValidatedOverrides, self).__init__()
        self.raw_overrides = raw_overrides
        self.valid_overrides = {}
        self.errors = []

        self._validate_overrides()

    def get_valid_overrides(self):
        """Get valid overrides.

        Returns
        -------
        dict
            The final list of options validated.
        """
        return self.valid_overrides

    def get_errors(self):
        """Get validation errors.

        Returns
        -------
        list
            A list of validation errors to be displayed.
        """
        return self.errors

    def _validate_overrides(self):
        """Validate the raw overrides.
        """
        for raw_override in self.raw_overrides:
            override = raw_override.split("=")

            if len(override) != 2:
                self.errors.append("Wrong override format: '%s'" %
                                   raw_override + "\n" + "Correct format: 'key=value'")
                continue

            key, value = override

            if key not in self.valid_options:
                self.errors.append("Wrong key name: '%s'" % key)
                continue

            if key == "target_ip":
                error_msg = INVALID_IP_MSG
            elif key == "max_backups_to_keep":
                error_msg = INVALID_INTEGER_MSG
            else:
                error_msg = "Valid Boolean values are: true, 1, false or 0. (case insensitive)"

            if key == "target_ip" and is_valid_ip(value):
                self.valid_overrides[key] = value
                continue
            elif key == "max_backups_to_keep" and is_valid_integer(value):
                self.valid_overrides[key] = int(value)
                continue
            elif self._validate_bool(value):
                self.valid_overrides[key] = self._get_bool(value)
                continue
            else:
                self.errors.append("Wrong value for: '%s'" % raw_override + "\n" + error_msg)
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
        return value.lower() in ["true", "false", "0", "1"]

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
        return value.lower() in ["true", "1"]


class HostsManager(object):
    """HostsManager class.

    Attributes
    ----------
    backup_old_generated_hosts : bool
        Back up the old generated hosts file before generating a new one.
    backup_system_hosts : bool
        Backup the system hosts file before installing a new one.
    backups_storage : str
        Path to the profile's back ups files.
    basedir_path : str
        The path to the USerData directory.
    blacklist : str
        Path to the blacklist file for the profile.
    compressed_sources : list
        The list of compressed sources.
    current_date : str
        The current date.
    exclusions : list
        List of domains to exclude from the hosts file.
    final_file : file object
        The file object that points to the newly-created hosts file.
    global_blacklist : str
        Path to the global_blacklist file.
    global_whitelist : str
        Path to the global_whitelist file.
    header : str
        Hosts file template header.
    header_static_hosts : str
        Static hosts template.
    hosts_file : str
        Path to the hosts file for the profile.
    invalid_rule : tuple
        Invalid rule template.
    keep_domain_comments : bool
        Keep domain comments.
    last_update_data : dict
        The dictionary containing the dates in which the sources were updated.
    logger : object
        See <class :any:`LogSystem`>.
    max_backups_to_keep : int
        The maximum amount of backup file to keep.
    merge_file : file object
        The temporary file object that contains the host names from all sources.
    number_of_ignores : int
        Number of ignored rules that didn't passed the host name validation.
    number_of_rules : int
        The total amount of rules that the generated hosts file will contain.
    profile : str
        Path to the current profile.
    profiles_path : str
        The path to were all profiles are stored.
    skip_static_hosts : bool
        Skip static local host entries in the final hosts file.
    sources : list
        The list of sources used to retrieve the hosts files.
    sources_last_updated : str
        Path to the JSON file were the last updated dates are stored for the profile.
    sources_storage : str
        Path to the folder were the downloaded sources are stored.
    sources_storage_compressed : str
        Storage for sources whose downloaded files are compressed files.
    sources_storage_raw : str
        Storage for sources whose downloaded files are raw files.
    target_ip : str
        Target IP address that will be used in the generated hosts file.
    whitelist : str
        Path to the whitelist file for the profile.
    """
    basedir_path = os.path.join(root_folder, "UserData")
    profiles_path = os.path.join(root_folder, "UserData", "profiles")
    invalid_rule = None, None, None

    header = """# Date: {date}
# Number of unique domains: {number_of_rules}
# ===============================================================
"""

    header_static_hosts = """
127.0.0.1 localhost
127.0.0.1 localhost.localdomain
127.0.0.1 local
255.255.255.255 broadcasthost
::1 localhost ip6-localhost ip6-loopback
fe80::1%lo0 localhost
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
0.0.0.0 0.0.0.0
127.0.1.1 {host_name}
127.0.0.53 {host_name}

"""

    def __init__(self, profile="", options_overrides={}, logger=None):
        """
        Parameters
        ----------
        profile : str, optional
            The profile name.
        options_overrides : dict, optional
            A list of options to override the default ones or the defined in the profile's
            configuration file.
        logger : object
            See <class :any:`LogSystem`>.

        Raises
        ----------------
        exceptions.MissingConfigFileForProfile
            See <class :any:`exceptions.MissingConfigFileForProfile`>.
        exceptions.NoProfileNameProvided
            See <class :any:`exceptions.NoProfileNameProvided`>.
        """
        super(HostsManager, self).__init__()
        if not profile:
            raise exceptions.NoProfileNameProvided("No profile name was provided.")

        self.logger = logger
        self.merge_file = None
        self.final_file = None
        self.current_date = time.strftime("%B %d %Y", time.gmtime())  # Format = January 1 2018
        self.profile = os.path.join(self.profiles_path, profile)

        try:
            config_file = run_path(os.path.join(self.profile, "conf.py"))
        except Exception as err:
            self.logger.error(err, term=False)
            raise exceptions.MissingConfigFileForProfile(err)

        self.sources = config_file.get("sources", None)

        self._validate_sources()

        profile_options = config_file.get("options", {})

        profile_options.update(options_overrides)

        self.last_update_data = {}
        self.exclusions = []
        self.compressed_sources = []
        self.number_of_rules = 0
        self.number_of_ignores = 0

        # Customizable options.
        self.target_ip = profile_options.get("target_ip", "0.0.0.0")
        self.keep_domain_comments = profile_options.get("keep_domain_comments", False)
        self.skip_static_hosts = profile_options.get("skip_static_hosts", False)
        self.backup_old_generated_hosts = profile_options.get("backup_old_generated_hosts", True)
        self.backup_system_hosts = profile_options.get("backup_system_hosts", True)
        self.max_backups_to_keep = profile_options.get("max_backups_to_keep", 10)

        self._validate_keys()

        # Paths to files/folders.
        self.hosts_file = os.path.join(self.profile, "hosts")
        self.sources_storage = os.path.join(self.profile, "sources_storage")
        self.sources_storage_raw = os.path.join(self.sources_storage, "raw")
        self.sources_storage_compressed = os.path.join(self.sources_storage, "compressed")
        self.sources_last_updated = os.path.join(self.profile, "last_updated.json")
        self.backups_storage = os.path.join(self.profile, "backups_storage")
        self.whitelist = os.path.join(self.profile, "whitelist")
        self.global_whitelist = os.path.join(self.basedir_path, "global_whitelist")
        self.blacklist = os.path.join(self.profile, "blacklist")
        self.global_blacklist = os.path.join(self.basedir_path, "global_blacklist")

        self._ensure_paths()
        self._expand_local_sources_data()

    def _validate_sources(self):
        """Validate sources.

        Raises
        ------
        exceptions.MalformedSources
            See <class :any:`exceptions.MalformedSources`>.
        exceptions.MissingSourcesOnConfigFile
            See <class :any:`exceptions.MissingSourcesOnConfigFile`>.
        """
        if not self.sources:
            raise exceptions.MissingSourcesOnConfigFile(
                "The 'sources' variable is not declared or it's empty.")

        mandatory_keys = ["name", "url"]
        names = []
        errors = []

        for source in self.sources:
            source_name = source.get("name", False)
            report_source = source_name if source_name else source
            source_keys = source.keys()

            # Do not allow sources without mandatory keys.
            for key in mandatory_keys:
                if key not in source_keys:
                    errors.append("Missing mandatory <%s> key!!! Source: <%s>" %
                                  (key, report_source))

            if "unzip_prog" in source_keys and "unzip_target" not in source_keys:
                errors.append("Missing mandatory <%s> key!!! Source: <%s>" %
                              ("unzip_target", report_source))

            if "unzip_target" in source_keys and "unzip_prog" not in source_keys:
                errors.append("Missing mandatory <%s> key!!! Source: <%s>" %
                              ("unzip_prog", report_source))

            if source_name:
                # Do not allow more than one source with the same "name".
                if source_name in names:
                    errors.append("More than one source with the same name. <%s>" % source_name)
                else:
                    names.append(source_name)

        if errors:
            raise exceptions.MalformedSources(
                "Error/s found that must be fixed!!!\n%s" % "\n".join(errors))

    def _expand_local_sources_data(self):
        """Add additional data to the sources.
        """
        try:
            with open(self.sources_last_updated, "r", encoding="UTF-8") as json_file:
                self.last_update_data = json.loads(json_file.read())
        except Exception:
            self.last_update_data = {}

        for source in self.sources:
            # Generate and add "slugified_name".
            source["slugified_name"] = "hosts-%s" % slugify(source["name"])

            # Generate and add the path for the downloaded file.
            if source.get("unzip_prog", False):
                source["downloaded_filename"] = os.path.join(self.sources_storage_compressed,
                                                             source["slugified_name"],
                                                             source["slugified_name"])
            else:
                source["downloaded_filename"] = os.path.join(
                    self.sources_storage_raw, source["slugified_name"])

            # Insert the date in which the source was last updated.
            if self.last_update_data:
                source["last_updated"] = self.last_update_data.get(source["slugified_name"], None)

        # Lastly, sort dictionaries by source names.
        self.sources = sorted(self.sources, key=lambda name: name["name"])

    def _validate_keys(self):
        """Validate keys.

        Raises
        ------
        exceptions.WrongValueForOption
            See <class :any:`exceptions.WrongValueForOption`>.
        """
        if not is_valid_integer(self.max_backups_to_keep):
            raise exceptions.WrongValueForOption(
                "%s Option <max_backups_to_keep>." % INVALID_INTEGER_MSG)

        if not is_valid_ip(self.target_ip):
            raise exceptions.WrongValueForOption("%s Option <target_ip>." % INVALID_IP_MSG)

    def install_hosts_file(self):
        """Install the generated hosts file.
        """
        print(Ansi.PURPLE("Moving the hosts file requires administrative privileges.\n"
                          "You might need to enter your password."))

        if self.backup_system_hosts:
            try:
                self.logger.info("Backing up the system's hosts file...")
                backup_file_path = os.path.join(self.backups_storage, "system-hosts-{}".format(
                    time.strftime("%Y-%m-%d-%H-%M-%S")))

                copy2("/etc/hosts", backup_file_path)
                file_utils.remove_surplus_files(
                    self.backups_storage, "system-hosts-*", max_files_to_keep=10)
            except Exception as err:
                self.logger.error(err)

        self._move_hosts_file_into_place()

    def build_hosts_file(self):
        """Build the hosts file from the local sources.
        """
        self._create_initial_file()
        self._remove_old_hosts_file()
        self._populate_final_file()
        self._write_opening_header()
        self.logger.info("Hosts file building finished.")
        self.logger.info("It contains {:,} unique entries.".format(self.number_of_rules))

        if self.number_of_ignores:
            self.logger.warning(
                "A total of {:,} rules were ignored.".format(self.number_of_ignores))
            self.logger.warning("(Ignored rules are listed inside the log file)")

    def update_all_sources(self, force_update):
        """Update all host files, regardless of folder depth.

        Raises
        ------
        exceptions.KeyboardInterruption
            See <class :any:`exceptions.KeyboardInterruption`>.

        Parameters
        ----------
        force_update : bool
            Ignore source update frequency and update its file/s anyway.
        """
        try:
            for source in self.sources:
                if force_update or self._should_update_source(source):
                    self.logger.info("Updating source <" + source["name"] + ">")

                    try:
                        self._download_source(source)
                    except Exception as err:
                        self.logger.error("Error in updating source. URL: ", source["url"])
                        self.logger.error(err)
                        continue
                    except (KeyboardInterrupt, SystemExit):
                        raise exceptions.KeyboardInterruption()
                else:
                    self.logger.info("Source <" + source["name"] + "> doesn't need updating.")
        except (KeyboardInterrupt, SystemExit):
            raise exceptions.KeyboardInterruption()
        else:
            with open(self.sources_last_updated, "w", encoding="UTF-8") as data_file:
                data_file.write(json.dumps(self.last_update_data, indent=4, sort_keys=True))

        if self.compressed_sources:
            self.logger.info("Handling compressed sources.")
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
        frequency = source.get("frequency", "frequently")
        last_updated = source.get("last_updated", False)

        if frequency == "frequently" or not last_updated:
            return True

        downloaded_filename = source.get("downloaded_filename", False)
        downloaded_filename_exists = downloaded_filename and os.path.exists(downloaded_filename)

        # Check separated to avoid unnecessary file existence checks.
        if not downloaded_filename_exists:
            return True

        try:
            then = datetime.strptime(last_updated, "%B %d %Y")
            now = datetime.strptime(self.current_date, "%B %d %Y")

            if frequency == "occasionally":  # Weekly.
                return (now - then) > timedelta(days=6)
            elif frequency == "rarely":  # Monthly.
                return (now - then) > timedelta(days=29)
        except Exception:
            return True

    def _move_hosts_file_into_place(self):
        """Copy the newly-created hosts file into its correct location on the OS.

        The hosts file is located at "/etc/hosts".

        For the file copy to work, you must have administrator privileges.
        This means having "sudo" access.
        """
        if os.path.exists(self.hosts_file):
            if call(["/usr/bin/sudo", "cp", self.hosts_file, "/etc/hosts"]):
                self.logger.error("Moving the file failed.")
            else:
                self.logger.success("Hosts file successfully installed.")
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
        is_compressed_source = source.get("unzip_prog", False)

        if is_compressed_source:
            try:
                os.makedirs(os.path.dirname(source["downloaded_filename"]), exist_ok=True)
            except Exception as err:
                self.logger.error(err)

        try:
            tqdm_wget.download(source["url"], source["downloaded_filename"])
        except (KeyboardInterrupt, SystemExit):
            raise exceptions.KeyboardInterruption()
        except Exception as err:
            self.logger.error(err)
        else:
            self.last_update_data[source["slugified_name"]] = self.current_date

            if is_compressed_source:
                self.compressed_sources.append(source)

    def _handle_compressed_sources(self):
        """Handle the downloaded sources with compressed files.

        Raises
        ------
        exceptions.KeyboardInterruption
            See <class :any:`exceptions.KeyboardInterruption`>.
        """
        try:
            for source in self.compressed_sources:
                self.logger.info("Decompressing source <%s>." % source["name"])

                aborted_msg = "Extract operation for <%s> aborted." % source["name"]
                src_dir_path = os.path.dirname(source["downloaded_filename"])
                src_path = os.path.join(src_dir_path, source["unzip_target"])
                dst_path = os.path.join(self.sources_storage_raw,
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
                    if not source["unzip_args"]:
                        self.logger.error(
                            "The `tar` command requires arguments (unzip_args key).\n" + aborted_msg)
                        continue

                    cmd += ["tar", source["unzip_args"], source["downloaded_filename"]]

                if cmd:
                    p = Popen(
                        cmd,
                        stdout=PIPE,
                        stderr=STDOUT,
                        env=cmd_utils.get_environment(),
                        cwd=src_dir_path
                    )

                    while True:
                        # Without decoding output, the loop will run forever. ¬¬
                        output = p.stdout.read(1).decode("utf-8")

                        if output == "" and p.poll() is not None:
                            break

                        if output:
                            sys.stdout.write(output)
                            sys.stdout.flush()

                    if os.path.exists(dst_path):
                        os.remove(dst_path)

                    copy2(src_path, dst_path)
        except (KeyboardInterrupt, SystemExit):
            raise exceptions.KeyboardInterruption()

    def _write_opening_header(self):
        """Write the header information into the newly-created hosts file.
        """
        self.logger.info("Writing the opening header...")
        self.final_file.seek(0)  # Reset file pointer.
        file_contents = self.final_file.read()  # Save content.

        self.final_file.seek(0)  # Write at the top.

        header = self.header.format(
            date=self.current_date,
            number_of_rules="{:,}".format(self.number_of_rules)
        )

        if not self.skip_static_hosts:
            header += self.header_static_hosts.format(host_name=gethostname())

        self.final_file.write(bytes(header, "UTF-8"))
        self.final_file.write(file_contents)
        self.final_file.close()

    def _remove_old_hosts_file(self):
        """Remove the old generated hosts file.

        This is a hotfix because merging with an already existing hosts file leads
        to artifacts and duplicates.
        """
        self.logger.info("Removing old generated hosts file...")

        # Create if already removed, so remove won't raise an error.
        open(self.hosts_file, "a").close()

        if self.backup_old_generated_hosts:
            backup_file_path = os.path.join(self.backups_storage, "generated-hosts-{}".format(
                time.strftime("%Y-%m-%d-%H-%M-%S")))

            # Make a backup copy, marking the date in which the list was updated
            copy2(self.hosts_file, backup_file_path)
            self.logger.info("Old generated hosts file backed up...")
            file_utils.remove_surplus_files(
                self.backups_storage, "generated-hosts-*", max_files_to_keep=10)

        os.remove(self.hosts_file)
        self.logger.info("Old generated hosts file removed...")

        # Create new empty hosts file
        open(self.hosts_file, "a").close()

    def _ensure_paths(self):
        """Ensure the existence of some folders inside the profile folder.
        """
        if not os.path.exists(self.sources_storage_raw):
            os.makedirs(self.sources_storage_raw)

        if not os.path.exists(self.sources_storage_compressed):
            os.makedirs(self.sources_storage_compressed)

        if not os.path.exists(self.backups_storage):
            os.makedirs(self.backups_storage)

    def _create_initial_file(self):
        """Initialize the file in which we merge all host files for later pruning.
        """
        self.merge_file = NamedTemporaryFile()

        self.logger.info("Creating initial temporary file...")
        self.logger.info("Collecting data from local sources...")
        sources_paths = file_utils.recursive_glob(self.sources_storage_raw, "hosts-*")

        for s in tqdm(range(len(sources_paths))):
            source_path = sources_paths[s]
            source_path_rel = os.path.relpath(source_path, self.profiles_path)

            try:
                with open(source_path, "r", encoding="UTF-8") as curFile:
                    self.merge_file.write(bytes(curFile.read() + "\n", "UTF-8"))
            except UnicodeDecodeError:
                self.logger.warning("File <%s>" % source_path_rel)
                self.logger.warning("Attempt to read file with UTF-8 encoding failed.")

                try:
                    self.logger.warning("Trying to read file with cp1252 encoding.")

                    with open(source_path, "r", encoding="cp1252") as curFile:
                        self.merge_file.write(bytes(curFile.read() + "\n", "UTF-8"))
                except UnicodeDecodeError as err:
                    self.logger.warning("Attempt to open file with cp1252 encoding failed.")
                    self.logger.warning("File ignored.")
                    print(err)
                    continue

        self.logger.info("Collecting data from blacklist files...")
        for blacklist_file in [self.blacklist, self.global_blacklist]:
            if os.path.isfile(blacklist_file):
                self.logger.info("Adding data from <%s>" %
                                 os.path.relpath(blacklist_file, self.basedir_path))
                with open(blacklist_file, "r", encoding="UTF-8") as curFile:
                    self.merge_file.write(bytes(curFile.read(), "UTF-8"))

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

        self.logger.info("Populating the exclusions list...")
        for whitelist_file in [self.whitelist, self.global_whitelist]:
            if os.path.isfile(whitelist_file):
                self.logger.info("Adding data from <%s>..." %
                                 os.path.relpath(whitelist_file, self.basedir_path))
                with open(whitelist_file, "r", encoding="UTF-8") as ins:
                    for line in ins:
                        line = line.strip(" \t\n\r")

                        if line and line[0] is not "#":
                            self.exclusions.append(line)

        self.final_file = open(self.hosts_file, "w+b")

        self.merge_file.seek(0)  # reset file pointer
        hostnames = {
            "localhost",
            "localhost.localdomain",
            "local",
            "broadcasthost"
        }

        cache_size = 250000
        cache_storage = ""

        merge_file_lines = self.merge_file.readlines()
        processed_lines = len(merge_file_lines)

        self.logger.info("Adding rules to the final hosts file...")
        try:
            # DO NOT USE "continue" INSIDE THIS LOOP!!!
            for l in tqdm(range(len(merge_file_lines))):
                line = merge_file_lines[l]
                processed_lines -= 1
                write_line = True
                normalized_rule = ""

                # Explicit encoding.
                line = line.decode("UTF-8")

                line = line.strip()

                # Trim periods: See https://github.com/StevenBlack/hosts/issues/271
                # line = line.rstrip(".")

                # Set line to "" instead of using continue. This is to avoid exiting the loop
                # while there is still data stored inside cache_storage.
                if line and (line[0] == "#" or "::1" in line):
                    line = ""

                if line:
                    # Normalize rule.
                    target_ip, hostname, comment = self._normalize_rule(line)

                    if hostname in self.exclusions:
                        write_line = False

                    if write_line:
                        if comment and self.keep_domain_comments:
                            normalized_rule = "%s %s #%s" % (target_ip, hostname, comment)
                        else:
                            normalized_rule = "%s %s" % (target_ip, hostname)

                        if normalized_rule and (hostname not in hostnames):
                            cache_size -= 1
                            cache_storage += normalized_rule + "\n"
                            hostnames.add(hostname)
                            self.number_of_rules += 1

                if (cache_size == 1 and cache_storage) or processed_lines == 1:
                    self.final_file.write(bytes(cache_storage, "UTF-8"))
                    cache_storage = ""
                    cache_size = 250000
        except (KeyboardInterrupt, SystemExit):
            self.merge_file.close()
            raise exceptions.KeyboardInterruption()

        self.merge_file.close()

    def _normalize_rule(self, line):
        """Standardize and format the rule string provided.

        Parameters
        ----------
        line : str
            The line to be standardized.

        Returns
        -------
        The rules elements : tuple
            The rules elements.
        """
        try:
            stripped_rule, comment = [part.strip() for part in line.split("#", 1)]
        except Exception:
            stripped_rule, comment = line.strip(), ""

        rule_parts = stripped_rule.split()

        try:
            hostname = rule_parts[1].lower()
        except Exception:
            hostname = None

        if len(rule_parts) == 2 and hostname and is_valid_host(hostname):
            return self.target_ip, hostname, comment
        else:
            self.number_of_ignores += 1
            self.logger.warning("Ignored line: %s" % line, term=False, date=False)

        return self.invalid_rule


def is_valid_host(host):
    """IDN compatible domain validation.

    Based on answers from a
    `StackOverflow question <https://stackoverflow.com/questions/2532053/validate-a-hostname-string>`__

    Parameters
    ----------
    host : str
        The host name to check.

    Returns
    -------
    bool
        Whether the host name is valid or not.
    """
    host = host.rstrip(".")

    return all([len(host) > 1,
                len(host) < 253] + [HOSTNAME_REGEX.match(x) for x in host.split(".")])


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


def flush_dns_cache(logger):
    """Flush the DNS cache.

    Parameters
    ----------
    logger : object
        See <class :any:`LogSystem`>.
    """
    print(Ansi.PURPLE("""Flushing the DNS cache to utilize new hosts file...
Flushing the DNS cache requires administrative privileges.
You might need to enter your password.
"""))

    dns_cache_found = False

    nscd_prefixes = ["/etc", "/etc/rc.d"]
    nscd_msg = "Flushing the DNS cache by restarting nscd {result}."

    for nscd_prefix in nscd_prefixes:
        nscd_cache = nscd_prefix + "/init.d/nscd"

        if os.path.isfile(nscd_cache):
            dns_cache_found = True

            if call(["/usr/bin/sudo", nscd_cache, "restart"]):
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

                if call(["/usr/bin/sudo", systemctl, "restart", service]):
                    logger.error(service_msg.format(result="failed"))
                else:
                    logger.success(service_msg.format(result="succeeded"))

    dns_clean_file = "/etc/init.d/dns-clean"
    dns_clean_msg = "Flushing the DNS cache via dns-clean executable {result}."

    if os.path.isfile(dns_clean_file):
        dns_cache_found = True

        if call(["/usr/bin/sudo", dns_clean_file, "start"]):
            logger.error(dns_clean_msg.format(result="failed"))
        else:
            logger.success(dns_clean_msg.format(result="succeeded"))

    if not dns_cache_found:
        logger.warning("Unable to determine DNS management tool.")


def new_profile_generation(logger):
    """Generate a new profile.

    Parameters
    ----------
    logger : object
        See <class :any:`LogSystem`>.
    """
    from.python_utils import prompts, template_utils
    profiles_path = os.path.join(root_folder, "UserData", "profiles")
    config_template = os.path.join(root_folder, "AppData", "data", "templates", "conf.py")

    d = {
        "name": "default"
    }

    prompts.do_prompt(d, "name", "Enter a profile name", "default")

    new_profile_path = os.path.join(profiles_path, d["name"])

    if os.path.exists(new_profile_path):
        logger.warning("Profile seems to exists. Choose a different name.")
        new_profile_generation(logger)
    else:
        os.makedirs(new_profile_path, exist_ok=True)
        config_path = os.path.join(new_profile_path, "conf.py")
        template_utils.generate_from_template(config_template, config_path, logger=logger)
        logger.info("New profile generated.")


if __name__ == "__main__":
    pass
