import os

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if os.getcwd() != _TESTS_DIR:
    os.chdir(_TESTS_DIR)
