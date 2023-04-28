import subprocess
from pathlib import Path
from onyo.lib import OnyoRepo
from onyo.lib.commands import fsck


def test_config_set(repo: OnyoRepo) -> None:
    ret = subprocess.run(["onyo", "config", "onyo.test.set", "set-test"],
                         capture_output=True, text=True)
    assert ret.returncode == 0
    assert not ret.stdout
    assert not ret.stderr
    assert 'set =' in Path('.onyo/config').read_text()
    assert '= set-test' in Path('.onyo/config').read_text()
    fsck(repo)


def test_config_get_onyo(repo: OnyoRepo) -> None:
    # set
    ret = subprocess.run(["onyo", "config", "onyo.test.get-onyo",
                          "get-onyo-test"],
                         capture_output=True, text=True)
    assert ret.returncode == 0

    # get
    ret = subprocess.run(["onyo", "config", "--get", "onyo.test.get-onyo"],
                         capture_output=True, text=True)
    assert ret.returncode == 0
    assert ret.stdout == 'get-onyo-test\n'
    assert not ret.stderr
    fsck(repo)


def test_config_get_pristine(repo: OnyoRepo) -> None:
    """
    onyo should not alter git config's output (newline, etc)
    """
    ret = subprocess.run(["onyo", "config", "onyo.test.get-pristine",
                          "get-pristine-test"],
                         capture_output=True, text=True)
    assert ret.returncode == 0

    # git config's output
    ret = subprocess.run(["git", "config", "-f", ".onyo/config",
                          "onyo.test.get-pristine"],
                         capture_output=True, text=True)
    assert ret.returncode == 0
    assert ret.stdout == 'get-pristine-test\n'
    git_config_output = ret.stdout

    # onyo config's output
    ret = subprocess.run(["onyo", "config", "--get", "onyo.test.get-pristine"],
                         capture_output=True, text=True)
    assert ret.returncode == 0
    assert ret.stdout == 'get-pristine-test\n'

    assert ret.stdout == git_config_output
    fsck(repo)


def test_config_get_empty(repo: OnyoRepo) -> None:
    assert 'onyo.test.not-exist' not in Path('.onyo/config').read_text()

    ret = subprocess.run(["onyo", "config", "--get", "onyo.test.not-exist"],
                         capture_output=True, text=True)
    assert ret.returncode == 1
    assert not ret.stdout
    assert not ret.stderr
    fsck(repo)


def test_config_unset(repo: OnyoRepo) -> None:
    # set
    ret = subprocess.run(["onyo", "config", "onyo.test.unset", "unset-test"],
                         capture_output=True, text=True)
    assert ret.returncode == 0

    # unset
    ret = subprocess.run(["onyo", "config", "--unset", "onyo.test.unset"],
                         capture_output=True, text=True)
    assert ret.returncode == 0
    assert not ret.stdout
    assert not ret.stderr
    assert 'unset =' not in Path('.onyo/config').read_text()
    assert '= unset-test' not in Path('.onyo/config').read_text()

    # get
    ret = subprocess.run(["onyo", "config", "--get", "onyo.test.unset"],
                         capture_output=True, text=True)
    assert ret.returncode == 1
    assert not ret.stdout
    assert not ret.stderr
    fsck(repo)


def test_config_help(repo: OnyoRepo) -> None:
    """
    `onyo config --help` is shown and not `git config --help`.
    """
    for flag in ['-h', '--help']:
        ret = subprocess.run(["onyo", "config", flag],
                             capture_output=True, text=True)
        assert ret.returncode == 0
        assert 'onyo' in ret.stdout
        assert not ret.stderr
    fsck(repo)


def test_config_forbidden_flags(repo: OnyoRepo) -> None:
    """
    Flags that change the source of values are not allowed.
    """
    for flag in ['--system', '--global', '--local', '--worktree', '--file',
                 '--blob']:
        ret = subprocess.run(["onyo", "config", flag],
                             capture_output=True, text=True)
        assert ret.returncode == 1
        assert flag in ret.stderr
    fsck(repo)


def test_config_bubble_retcode(repo: OnyoRepo) -> None:
    """
    Bubble up git-config's retcodes.
    According to the git config manpage, attempting to unset an option which
    does not exist exits with "5".
    """
    assert 'onyo.test.not-exist' not in Path('.onyo/config').read_text()

    ret = subprocess.run(["onyo", "config", "--unset", "onyo.test.not-exist"],
                         capture_output=True, text=True)
    assert ret.returncode == 5
    fsck(repo)


def test_config_bubble_stderr(repo: OnyoRepo) -> None:
    """
    Bubble up git-config printing to stderr.
    """
    ret = subprocess.run(["onyo", "config", "--invalid-flag-oopsies",
                          "such-an-oops"],
                         capture_output=True, text=True)
    assert ret.returncode == 129
    assert not ret.stdout
    assert ret.stderr
    fsck(repo)
