import shutil
import pytest


@pytest.fixture(scope="session", autouse=True)
def clean_sandbox(request):
    """
    Ensure that 'tests/sandbox' is clean, and doesn't have remnants from
    previous runs.
    """
    sandbox_dir = 'tests/sandbox/'
    try:
        shutil.rmtree(sandbox_dir)
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
