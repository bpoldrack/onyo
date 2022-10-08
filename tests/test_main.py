from itertools import product

from onyo import main


def test_get_subcmd_index_missing(helpers):
    """
    All combinations of flags for onyo, without any subcommand.
    """
    for i in helpers.powerset(helpers.onyo_flags()):
        for k in product(*i):
            args = list(helpers.flatten(k))
            full_cmd = ['onyo'] + args
            idx = main.get_subcmd_index(full_cmd)
            assert idx is None


def test_get_subcmd_index_valid(helpers):
    """
    All combinations of flags for onyo, with a subcommand.
    """
    for i in helpers.powerset(helpers.onyo_flags()):
        for k in product(*i):
            args = list(helpers.flatten(k))
            full_cmd = ['onyo'] + args + ['config', '--get', 'onyo.core.editor']
            idx = main.get_subcmd_index(full_cmd)
            assert idx == full_cmd.index('config')


def test_get_subcmd_index_overlap(helpers):
    """
    Arg values overlap with onyo or its subcommands. Borderline pathological.
    """
    full_cmd = ['onyo', '-C', 'onyo', '-d', 'mv', 'onyo', 'mv']
    idx = main.get_subcmd_index(full_cmd)
    assert idx == 4

    full_cmd = ['onyo', '-C', 'mv', 'mv', 'mv', 'onyo']
    idx = main.get_subcmd_index(full_cmd)
    assert idx == 3
