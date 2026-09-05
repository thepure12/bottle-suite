"""Shared helpers for mutating-test isolation, so the committed
tests/resources.db and tests/bottle_suite.toml fixtures never change
across test runs.
"""
import os
import shutil
import tempfile


def temp_sqlite_copy(src="resources.db"):
    """Copy the committed sqlite fixture to a throwaway temp file. Caller
    must remove the returned path in tearDown."""
    fd, path = tempfile.mkstemp(suffix=".db", dir=os.getcwd())
    os.close(fd)
    shutil.copy(src, path)
    return path


def temp_cfg_copy(src="bottle_suite.toml"):
    """Copy the committed toml fixture into a fresh temp directory, so
    saveConfig()/toml-writing tests never touch the shared fixture file.
    Returns the (dir, absolute cfg path) pair; caller must shutil.rmtree(dir)
    in tearDown. An absolute path is used since BottleSuite may already have
    chdir'd into tests/.

    NOTE: the committed bottle_suite.toml itself contains
    `sqlite = "resources.db"` -- since toml values always override
    constructor args (see BottleSuite.__init__), a BottleSuite built from
    a copy of this file still points at the real, shared resources.db
    unless the caller also overrides "sqlite" via the resulting cfg. Any
    test that both writes config AND mutates DB rows/schema should use
    temp_cfg_pointing_at() instead."""
    cfg_dir = tempfile.mkdtemp()
    cfg_path = os.path.join(cfg_dir, "bottle_suite.toml")
    shutil.copy(src, cfg_path)
    return cfg_dir, cfg_path


def temp_cfg_pointing_at(sqlite_path):
    """Write a fresh, isolated toml file whose only setting is
    `sqlite = "<sqlite_path>"`, so both the cfg file and the db it points
    at are throwaway copies -- safe for tests that mutate DB schema/rows
    AND call saveConfig()/updateRoles()/updatePaths()/etc. Returns the
    (dir, absolute cfg path) pair; caller must shutil.rmtree(dir) in
    tearDown."""
    cfg_dir = tempfile.mkdtemp()
    cfg_path = os.path.join(cfg_dir, "bottle_suite.toml")
    with open(cfg_path, "w") as f:
        f.write(f'sqlite = "{sqlite_path}"\n')
    return cfg_dir, cfg_path
