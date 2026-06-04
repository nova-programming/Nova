"""
Galaxy Package Manager for Nova
Backward-compat import shim — delegates to the canonical _galaxy module.
"""
from _galaxy import *  # noqa: F401, F403
from _galaxy import main  # noqa: F401

if __name__ == "__main__":
    main()
