"""Allow ``python -m test_tamper_guard``."""

import sys

from .cli import main

sys.exit(main())
