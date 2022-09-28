import os
import shutil
from pathlib import Path
import pytest


@pytest.fixture(scope="function", autouse=True)
def change_cwd_to_sandbox(request, monkeypatch):
    """
    Change the working directory to a "sandbox" that allows tests to run in
    isolation, and not conflict with other tests.

    The directory is named "sandbox/<test-file-name>/".
    For example: "sandbox/test_mkdir.py/"

    If the directory does not exist, it will be created.
    """
    parent = request.path.parent
    sandbox_test_dir = parent.joinpath('sandbox', request.path.name)

    # create the dir
    sandbox_test_dir.mkdir(parents=True, exist_ok=True)
    # cd
    monkeypatch.chdir(sandbox_test_dir)


@pytest.fixture(scope="function", autouse=True)
def clean_env(request):
    """
    Ensure that $EDITOR is not inherited from the environment or other tests.
    """
    try:
        del os.environ['EDITOR']
    except KeyError:
        pass


@pytest.fixture(scope="session", autouse=True)
def clean_sandboxes(request):
    """
    Ensure that 'tests/sandbox' is clean, and doesn't have remnants from
    previous runs.
    """
    for s in sorted(Path('tests/').glob('**/sandbox')):
        try:
            shutil.rmtree(s)
        except FileNotFoundError:
            pass


@pytest.fixture
def helpers():
    return Helpers


class Helpers:
    @staticmethod
    def string_in_file(string, file):
        """
        Test whether a string is in a file.
        """
        with open(file) as f:
            if string in f.read():
                return True

        return False