from __future__ import annotations
from typing import TYPE_CHECKING
from pathlib import Path
import logging

from onyo import OnyoRepo
from onyo.lib.commands import fsck, get as get_cmd

if TYPE_CHECKING:
    import argparse


logging.basicConfig()
log = logging.getLogger('onyo')


def get(args: argparse.Namespace) -> None:
    """
    Return matching asset(s) and values corresponding to the requested key(s).
    If no key(s) are given, the pseudo-keys are returned instead.

    Filters can make use of pseudo-keys (i.e., keys for which the values are
    only stored in the asset name). Values of the dictionary or list type, as
    well as assets missing a value can be referenced as '<dict>', '<list>',
    or '<unset>' instead of their contents, respectively. If a requested key
    does not exist, its output is displayed as '<unset>'.

    By default, the returned assets are sorted by their paths.
    """

    repo = OnyoRepo(Path.cwd(), find_root=True)
    fsck(repo, ['asset-yaml'])

    paths = [Path(p).resolve() for p in args.path]
    get_cmd(repo,
            args.sort_ascending,
            args.sort_descending,
            paths,
            args.depth,
            args.machine_readable,
            args.filter,
            args.keys)