"""Print a video's key facts as JSON.

Usage: python scripts/probe.py <video>
"""
import sys

from common import print_json, probe

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print_json(probe(sys.argv[1]))
