#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Schemas for JSON data validation.
"""
settings_schema = {
    "description": "Schema to validate the 'settings' property inside the UserData/conf.py file.",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "target_ip",
        "keep_domain_comments",
        "skip_static_hosts",
        "custom_static_hosts",
        "backup_old_generated_hosts",
        "backup_system_hosts",
        "max_backups_to_keep"
    ],
    "properties": {
        "target_ip": {
            "anyOf": [
                {"type": "string", "format": "ipv4"},
                {"type": "string", "format": "ipv6"}
            ],
            "default": "0.0.0.0",
            "description": "The loop back IP address that will be used in the newly generated hosts file.",
        },
        "keep_domain_comments": {
            "type": "boolean",
            "default": False,
            "description": "Keep or not the in-line comments next to the hosts rules.",
        },
        "skip_static_hosts": {
            "type": "boolean",
            "default": False,
            "description": "Skip or not the static host names at the beginning of the file (localhost, localhost.localdomain, local, etc.).",
        },
        "custom_static_hosts": {
            "type": "string",
            "default": "",
            "description": "Skip or not the static host names at the beginning of the file (localhost, localhost.localdomain, local, etc.).",
        },
        "backup_old_generated_hosts": {
            "type": "boolean",
            "default": True,
            "description": "Backup or not the previously generated hosts file before generating the new one.",
        },
        "backup_system_hosts": {
            "type": "boolean",
            "default": True,
            "description": "Backup or not the currently in use hosts file before replacing it.",
        },
        "max_backups_to_keep": {
            "type": "integer",
            "default": 10,
            "description": "How many backed up hosts files (system's and generated) to keep. Older backup files will be automatically deleted.",
        }
    }
}


sources_schema = {
    "description": "Schema to validate the 'sources' property inside the UserData/conf.py file.",
    "type": "array",
    "minItems": 1,
    "additionalItems": True,
    "items": {
        "type": "object",
        "additionalProperties": True,
        "required": {
            "name",
            "url"
        },
        "dependencies": {
            "unzip_prog": ["unzip_target"],
        },
        "properties": {
            "name": {
                "type": "string",
                "description": "A **unique** name that identifies the source. Since this *name* is used to generate the name of the downloaded file, and the downloaded files are all stored inside the same folder, this *name* **must be unique**."
            },
            "url": {
                "type": "string",
                "description": "The URL for the direct download of the source file."
            },
            "is_whitelist": {
                "type": "boolean",
                "description": "If set to **True**, all host names found in a source will be added to the exclusions list (will not be added to the final hosts file)."
            },
            "frequency": {
                "enum": [
                    "d",
                    "w",
                    "m",
                    "s"
                ],
                "description": "Frequency in which the source files should be downloaded."
            },
            "pre_processors": {
                "type": "array",
                "description": "Methods used to manipulate the data from the downloaded sources so the result of the manipulation can be processed by this application to generate a hosts file.",
                "items": {
                    "anyOf": [{
                        "enum": [
                            "url_parser",
                            "json_array"
                        ]
                    }, {
                        "type": "custom_callable"
                    }]
                }
            },
            "unzip_prog": {
                "enum": [
                    "unzip",
                    "gzip",
                    "7z",
                    "tar"
                ]
            },
            "untar_arg": {
                "enum": [
                    "--xz",
                    "-J",
                    "--gzip",
                    "-z",
                    "--bzip2",
                    "-j"
                ],
                "description": "The decompress argument used by the ``tar`` program."
            },
            "unzip_target": {
                "type": "string",
                "description": "The name of the file to extract inside the compressed file."
            }
        }
    }
}


if __name__ == "__main__":
    pass
