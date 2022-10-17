import subprocess
from pathlib import Path


def fully_populated_dot_onyo(directory=''):
    """
    Assert whether a .onyo dir is fully populated.
    """
    dot_onyo = Path(directory, '.onyo')

    if not Path(dot_onyo).is_dir() or \
       not Path(dot_onyo, "temp").is_dir() or \
       not Path(dot_onyo, "templates").is_dir() or \
       not Path(dot_onyo, "validation").is_dir() or \
       not Path(dot_onyo, "config").is_file() or \
       not Path(dot_onyo, ".anchor").is_file() or \
       not Path(dot_onyo, "temp/.anchor").is_file() or \
       not Path(dot_onyo, "templates/.anchor").is_file() or \
       not Path(dot_onyo, "validation/.anchor").is_file():
           return False  # noqa: E111, E117
    # TODO: assert that no unstaged or untracked under .onyo/

    return True


def test_cwd():
    ret = subprocess.run(["onyo", "init"])
    assert ret.returncode == 0
    assert fully_populated_dot_onyo()


def test_child_exist():
    Path('child_exist').mkdir()
    ret = subprocess.run(["onyo", "init", 'child_exist'])
    assert ret.returncode == 0
    assert fully_populated_dot_onyo('child_exist')


def test_child_not_exist():
    ret = subprocess.run(["onyo", "init", 'child_not_exist'])
    assert ret.returncode == 0
    assert fully_populated_dot_onyo('child_not_exist')


def test_child_with_spaces_not_exist():
    ret = subprocess.run(["onyo", "init", 'child with spaces not exist'])
    assert ret.returncode == 0
    assert fully_populated_dot_onyo('child with spaces not exist')


def test_child_with_spaces_exist():
    Path('child with spaces exist').mkdir()
    ret = subprocess.run(["onyo", "init", 'child with spaces exist'])
    assert ret.returncode == 0
    assert fully_populated_dot_onyo('child with spaces exist')


def test_fail_reinit_cwd():
    ret = subprocess.run(["onyo", "init"])
    assert ret.returncode == 1
    # and nothing should be lost
    assert fully_populated_dot_onyo()


def test_fail_reinit_child():
    ret = subprocess.run(["onyo", "init", 'reinit_child'])
    assert ret.returncode == 0
    ret = subprocess.run(["onyo", "init", 'reinit_child'])
    assert ret.returncode == 1
    # and nothing should be lost
    assert fully_populated_dot_onyo('reinit_child')


def test_fail_init_file():
    Path('file').touch()
    ret = subprocess.run(["onyo", "init", 'file'])
    assert ret.returncode == 1


# target dir that is too deep
def test_fail_missing_parent_dir():
    ret = subprocess.run(["onyo", "init", 'missing/parent/dir'])
    assert ret.returncode == 1
    assert not fully_populated_dot_onyo('missing/parent/dir')


# target dir that's already a git repo
def test_child_exist_with_git():
    # create git repo
    ret = subprocess.run(['git', 'init', 'child_exist_with_git'])
    assert ret.returncode == 0

    ret = subprocess.run(["onyo", "init", 'child_exist_with_git'])
    assert ret.returncode == 0
    assert fully_populated_dot_onyo('child_exist_with_git')


# target dir that contains non-git stuff
def test_child_with_cruft():
    Path('child_exist_with_cruft').mkdir()
    Path('child_exist_with_cruft/such_cruft.txt').touch()

    ret = subprocess.run(["onyo", "init", 'child_exist_with_cruft'])
    assert ret.returncode == 0
    assert fully_populated_dot_onyo('child_exist_with_cruft')
    # TODO: assert that child_exist_with_cruft/such_cruft.txt is not committed.
