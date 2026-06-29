"""Trinetra Capital AI — entrypoint.

    python main.py

Starts the interactive multi-agent trading CLI. Trading mode (paper/live),
Groww credentials and safety limits are all read from your .env via
trinetra.config. Run `python connect_groww.py` first to connect Groww.
"""

from trinetra.cli import run

if __name__ == "__main__":
    run()
