#!/usr/bin/python3
# -*- coding: utf-8 -*-
# Configuration file for Hosts Manager CLI application.


# This variable is optional (can be completely omitted from this configuration file)
# and should always be called "options". The values specified below are the default ones.
options = {
    # String: The loop back IP address that will be used in the newly generated hosts file.
    "target_ip": "0.0.0.0",

    # Boolean: Keep or not the in-line comments next to the hosts rules.
    "keep_domain_comments": False,

    # Boolean: Skip or not the static host names at the beginning of the file.
    # (localhost, localhost.localdomain, local, etc.)
    "skip_static_hosts": False,

    # Boolean: Backup or not the previously generated hosts file before generating the new one.
    "backup_old_generated_hosts": True,

    # Boolean: Backup or not the currently in use hosts file before replacing it.
    "backup_system_hosts": True,

    # Integer: How many backup files to keep. Older backup files will be automatically deleted.
    "max_backups_to_keep": 10,
}

# This variable is mandatory (cannot be omitted from this configuration file and it cannot be empty)
# and should always be called "sources".
sources = [
    {
        # name: (string) (Mandatory)
        #
        # A UNIQUE name that identifies the source. Since this "name" is used to generate
        # the name of the downloaded file, and the downloaded files are all stored inside the
        # same folder, this "name" MUST BE UNIQUE.
        "name": "MVPS hosts file",

        # description: (string) (Optional - Not used by Hosts Manager)
        #
        # A brief description of the source and its content.
        "description": "The purpose of this site is to provide the user with a high quality custom HOSTS file.",

        # homeurl: (string) (Optional - Not used by Hosts Manager)
        #
        # A home URL for the source.
        "homeurl": "http://winhelp2002.mvps.org/",

        # frequency: (string) (Optional)
        #
        # Possible values: "frequently", "occasionally" or "rarely".
        #
        # This is the frequency in which the source files are updated by their maintainers.
        # If not specified, it defaults to "frequently".
        #
        # frequently: Download the source file regardless of when was the last time
        # the source was updated.
        #
        # occasionally (weekly download): Download the source file only if more than six (6) days
        # have passed since the last update.
        #
        # rarely (monthly download): Download the source file only if more than twenty nine (29) days
        # have passed since the last update.
        "frequency": "rarely",

        # issues: (string) (Optional - Not used by Hosts Manager)
        #
        # An URL were to report issues with the source.
        "issues": "mailto:winhelp2002@gmail.com",

        # url: (string) (Mandatory)
        #
        # The URL for the direct download of the source file.
        "url": "http://winhelp2002.mvps.org/hosts.txt",

        # license: (string) (Optional - Not used by Hosts Manager)
        #
        # The license for the downloaded file.
        "license": "CC BY-NC-SA 4.0"
    }, {
        "name": "free.fr-Trackers",
        "description": "Block tracking sites.",
        "homeurl": "http://rlwpx.free.fr/WPFF/hosts.htm",
        "url": "http://rlwpx.free.fr/WPFF/htrc.7z",

        # unzip_prog: (string) (Mandatory for sources with compressed files)
        #
        # Possible values: "unzip" or "7z".
        #
        # The name of the command used to decompress the downloaded file. Needless to say,
        # the command should be available on the system.
        "unzip_prog": "7z",

        # unzip_target: (string) (Mandatory for sources with compressed files)
        #
        # The name of the file to extract inside the compressed file.
        "unzip_target": "Hosts.trc",
        "license": "CC BY-NC 3.0"
    }
]
