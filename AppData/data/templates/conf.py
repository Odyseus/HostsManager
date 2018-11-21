#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Practical example configuration file.

Attributes
----------
settings : dict, optional
    See documentation/manual for details.
sources : list, mandatory
    See documentation/manual for details.
"""

settings = {
    "target_ip": "0.0.0.0",
    "keep_domain_comments": False,
    "skip_static_hosts": False,
    "backup_old_generated_hosts": True,
    "backup_system_hosts": True,
    "max_backups_to_keep": 10,
}

sources = [
    {
        "name": "MVPS hosts file",
        "url": "http://winhelp2002.mvps.org/hosts.txt",
        "frequency": "m",
        "description": "The purpose of this site is to provide the user with a high quality custom HOSTS file.",
        "homeurl": "http://winhelp2002.mvps.org/",
        "issues": "mailto:winhelp2002@gmail.com",
        "license": "CC BY-NC-SA 4.0"
    }, {
        "name": "Malwarebytes hpHosts",
        "url": "http://hosts-file.net/download/hosts.zip",
        "unzip_prog": "unzip",
        "unzip_target": "hosts.txt",
        "frequency": "s",
        "description": "hpHosts is a community managed and maintained hosts file that allows an additional layer of protection against access to ad, tracking and malicious websites.",
        "homeurl": "https://hosts-file.net",
        "license": "Freeware"
    }
]

if __name__ == "__main__":
    pass
