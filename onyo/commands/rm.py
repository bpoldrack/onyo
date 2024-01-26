from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from onyo import OnyoRepo
from onyo.argparse_helpers import path
from onyo.lib.commands import onyo_rm
from onyo.lib.inventory import Inventory
from onyo.shared_arguments import shared_arg_message

if TYPE_CHECKING:
    import argparse

args_rm = {
    'path': dict(
        metavar='PATH',
        nargs='+',
        type=path,
        help='Asset(s) and/or directory(s) to delete'),

    'message': shared_arg_message,
}


def rm(args: argparse.Namespace) -> None:
    """
    Delete ``ASSET``\\(s) and ``DIRECTORY``\\(s).

    Directories and asset directories are deleted together with their contents.
    If any of the specified paths is invalid, Onyo will error and delete none of them.

    A list of all files and directories to delete will be presented, and the
    user prompted for confirmation.
    """
    inventory = Inventory(repo=OnyoRepo(Path.cwd(), find_root=True))
    paths = [Path(p).resolve() for p in args.path]
    onyo_rm(inventory,
            paths=paths,
            message='\n\n'.join(m for m in args.message) if args.message else None)
