"""Allow python -m galaxy to work."""
try:
    from _galaxy import main
except ImportError:
    from galaxy import main
main()
