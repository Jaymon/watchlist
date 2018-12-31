# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import os


SUCCESS_PATH = os.environ.get("WATCHLIST_SUCCESS_PATH", "")
"""The success email's body will be dumped to this path if it exists"""

ERROR_PATH = os.environ.get("WATCHLIST_ERROR_PATH", "")
"""The error email's body will be dumped to this path if it exists"""

