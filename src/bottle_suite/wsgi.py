"""WSGI entrypoint for running a BottleSuite project under an external server.

Point gunicorn, mod_wsgi, uwsgi, waitress, etc. at ``bottle_suite.wsgi:application``
instead of using the ``bottle-suite`` CLI's ``app.run()`` -- the server owns
process/worker lifecycle and restarts, so there is no argparse layer here.

Like the CLI, all configuration comes from ``bottle_suite.toml`` (cors, rest,
jwt, sqlite/sql, dashboard, openapi -- see BottleSuite's config precedence),
resolved relative to the process's *working directory*, along with the
project's ``resources/`` folder. Set the server's working directory to the
project root (gunicorn's ``--chdir``, mod_wsgi's ``WSGIDaemonProcess
python-path=...`` plus an ``os.chdir()`` in the ``.wsgi`` file, systemd's
``WorkingDirectory=``, etc.) -- or point BOTTLE_SUITE_CFG at an absolute path
and keep ``resources/`` alongside it.

Examples:
    gunicorn --chdir /path/to/project bottle_suite.wsgi:application
    uwsgi --chdir /path/to/project --module bottle_suite.wsgi:application
"""

import os

from .bottle_suite import BottleSuite

application = BottleSuite(cfg_file=os.environ.get("BOTTLE_SUITE_CFG", "bottle_suite.toml"))
