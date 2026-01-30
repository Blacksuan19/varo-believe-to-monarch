
try:
    from varo_to_monarch.gui import main
except ImportError:
    # Fallback if running from source without installation
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from varo_to_monarch.gui import main

if __name__ == "__main__":
    main()
