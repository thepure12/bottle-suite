"""WSGI entrypoint for running a Bottler project under an external server.

Point gunicorn, mod_wsgi, uwsgi, waitress, etc. at ``bottler.wsgi:application``
instead of using the ``bottler`` CLI's ``app.run()`` -- the server owns
process/worker lifecycle and restarts, so there is no argparse layer here.

Like the CLI, all configuration comes from ``bottler.toml`` (cors, rest,
jwt, sqlite/sql, dashboard, openapi -- see Bottler's config precedence),
resolved relative to the process's *working directory*, along with the
project's ``resources/`` folder. Set the server's working directory to the
project root (gunicorn's ``--chdir``, mod_wsgi's ``WSGIDaemonProcess
python-path=...`` plus an ``os.chdir()`` in the ``.wsgi`` file, systemd's
``WorkingDirectory=``, etc.) -- or point BOTTLER_CFG at an absolute path
and keep ``resources/`` alongside it.

Examples:
    gunicorn --chdir /path/to/project bottler.wsgi:application
    uwsgi --chdir /path/to/project --module bottler.wsgi:application
"""

import os

from .core import Bottler

application = Bottler(cfg_file=os.environ.get("BOTTLER_CFG", "bottler.toml"))
