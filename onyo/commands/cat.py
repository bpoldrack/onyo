import logging
import sys
from pathlib import Path

from onyo.commands.fsck import read_only_fsck

logging.basicConfig()
log = logging.getLogger('onyo')


def sanitize_paths(paths, onyo_root):
    """
    Check and normalize a list of paths. If paths do not exist or are not files,
    print paths and exit with error.
    """
    paths_to_cat = []
    error_path_absent = []
    error_path_not_file = []

    for p in paths:
        # TODO: This is wrong when an absolute path is provided
        full_path = Path(onyo_root, p).resolve()

        # path must exist
        if not full_path.exists():
            error_path_absent.append(p)
            continue

        # path must be a file
        if not full_path.is_file():
            error_path_not_file.append(p)
            continue

        paths_to_cat.append(full_path)

    if error_path_absent:
        log.error("The following paths do not exist:")
        log.error("\n".join(error_path_absent))
        log.error("\n Exiting.")
        sys.exit(1)

    if error_path_not_file:
        log.error("The following paths are not files:")
        log.error("\n".join(error_path_not_file))
        log.error("\n Exiting.")
        sys.exit(1)

    return paths_to_cat


def cat(args, onyo_root):
    """
    Print the contents of ``asset``\(s) to the terminal without parsing or
    validating the contents.
    """
    read_only_fsck(args, onyo_root, quiet=True)

    paths_to_cat = sanitize_paths(args.asset, onyo_root)

    # open file and print to stdout
    for path in paths_to_cat:
        print(path.read_text(), end='')
