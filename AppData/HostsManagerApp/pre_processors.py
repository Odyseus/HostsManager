# -*- coding: utf-8 -*-
"""Module with utility functions to process data.

Attributes
----------
pre_processors : dict
    Available pre-processors.
"""
import json

from urllib.parse import urlparse


def url_parser(source_data, logger):
    """URL parser processor.

    Parameters
    ----------
    source_data : str
        A list of URLs separated by new lines.
    logger : object
        See <class :any:`LogSystem`>.

    Returns
    -------
    str
        A string containing only host names separated by new lines.
    """
    temp_source_data = ""

    for line in source_data.split("\n"):
        hostname = None

        try:
            hostname = urlparse(line.strip()).hostname
        except Exception:
            continue
        else:
            if hostname:
                temp_source_data += urlparse(line).hostname + "\n"

    return temp_source_data


def json_array(source_data, logger):
    """JSON array processor.

    Parameters
    ----------
    source_data : str
        A JSON array of strings.
    logger : object
        See <class :any:`LogSystem`>.

    Returns
    -------
    str
        A string containing each element from the passed JSON array separated by new lines.
    """
    try:
        return "\n".join(json.loads(source_data))
    except Exception as err:
        logger.error(err)
        return source_data


pre_processors = {
    "url_parser": url_parser,
    "json_array": json_array
}


if __name__ == "__main__":
    pass
