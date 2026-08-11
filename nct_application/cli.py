"""Command-line interface for NCT"""

import sys
from .application import NCTApplication
from .config import NCTConfig


def main():
    """Main CLI entry point"""
    print("NeuroSynthesis NCT - Network Correspondence Toolbox")
    print("Run 'python nct_desktop_app.py' for GUI version")


if __name__ == '__main__':
    main()
