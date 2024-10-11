from __future__ import annotations

import copy
import os
from collections import UserDict
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING

from ruamel.yaml import CommentedMap, scanner, YAML  # pyre-ignore[21]
from ruamel.yaml.error import YAMLError  # pyre-ignore[21]
from ruamel.yaml.representer import RoundTripRepresenter  # pyre-ignore[21]
from ruamel.yaml.dumper import RoundTripDumper  # pyre-ignore[21]

from onyo.lib.consts import PSEUDO_KEYS, RESERVED_KEYS
from onyo.lib.exceptions import NotAnAssetError
from onyo.lib.ui import ui

if TYPE_CHECKING:
    from typing import (
        Dict,
        Generator,
        Hashable,
        Mapping,
        Set,
        TypeVar,
    )

    _KT = TypeVar("_KT")  # Key type.
    _VT = TypeVar("_VT")  # Value type.


class DotNotationWrapper(UserDict):
    """Dictionary wrapper for providing access to nested dictionaries within via hierarchical keys.

    This class wraps a dictionary (available from the attribute .data) to allow traversing
    multidimensional dictionaries using a dot as the delimiter. In other words, it provides a view on the
    flattened dictionary:

    > d = {'key': 'value', 'nested': {'key': 'another value'}}
    > wrapper = DotNotationWrapper(d)
    > wrapper['nested.key']
    'another value'
    > list(wrapper.keys())
    ['key', 'nested.key']

    Iteration only considers the flattened view, and keys that contain dictionaries will not be yielded when using
    `wrapper.keys()`, `wrapper.values()`, and `wrapper.items()`. Whenever the python standard behavior is needed, the
    underlying dictionary is available from the `.data` attribute.
    """

    def __init__(self, __dict: Mapping[_KT, _VT] | None = None, **kwargs: _VT) -> None:
        if __dict and isinstance(__dict, dict):
            super().__init__()
            # If we have any sort of existing dict, we want to wrap it, maintaining the original object (and class).
            # Note: Currently would modify wrapped dict w/ kwargs if both are given.
            #       Would need deepcopy to prevent this, but this kinda contradicts the idea of wrapping.
            self.data = __dict
            self.update(**kwargs)
        else:
            # Resort to `UserDict` behavior if we have any sort of sequence or just `kwargs`.
            super().__init__(__dict, **kwargs)

    def _keys(self) -> Generator[str, None, None]:
        """Recursively yield all keys from nested dicts in dot notation.

        Note, that this forces the returned keys to be strings no matter their original type.
        """
        def recursive_keys(d: dict):
            for k in d.keys():
                if hasattr(d[k], "keys"):
                    yield from (k + "." + sk for sk in recursive_keys(d[k]))
                else:
                    # For the purpose of dot notation access, key types other than string don't make sense.
                    # One can't have a key 'some.1.more', where 1 remains an integer.
                    yield str(k)
        yield from recursive_keys(self.data)

    def __getitem__(self, key):
        if isinstance(key, str):
            parts = key.split('.')
            effective_dict = self.data
            if len(parts) > 1:
                for lvl in range(len(parts) - 1):
                    try:
                        effective_dict = effective_dict[parts[lvl]]
                    except KeyError as e:
                        raise KeyError(f"'{'.'.join(parts[:lvl + 1])}'") from e
                    except TypeError as e:
                        raise TypeError(f"'{'.'.join(parts[:lvl])}' is not a dictionary.") from e
            try:
                return effective_dict[parts[-1]]
            except KeyError as e:
                raise KeyError(f"'{key}'") from e
            except TypeError as e:
                raise TypeError(f"'{'.'.join(parts[:-1])}' is not a dictionary.") from e
        return super().__getitem__(key)

    def __setitem__(self, key, item):
        if isinstance(key, str):
            parts = key.split('.')
            effective_dict = self.data
            if len(parts) > 1:
                for lvl in range(len(parts) - 1):
                    try:
                        effective_dict = effective_dict[parts[lvl]]
                    except KeyError:
                        # nested dict doesn't exist yet
                        effective_dict[parts[lvl]] = dict()
                        effective_dict = effective_dict[parts[lvl]]

            effective_dict[parts[-1]] = item
        else:
            super().__setitem__(key, item)

    def __delitem__(self, key):
        if isinstance(key, str):
            parts = key.split('.')
            effective_dict = self.data
            if len(parts) > 1:
                for lvl in range(len(parts) - 1):
                    try:
                        effective_dict = effective_dict[parts[lvl]]
                    except KeyError as e:
                        raise KeyError(f"'{'.'.join(parts[:lvl + 1])}'") from e
            del effective_dict[parts[-1]]
        else:
            super().__delitem__(key)

    def __contains__(self, key):
        """Whether `key` is in self.

        Note, that this is `True` for intermediate keys (dicts), although `self.__iter__` wouldn't yield them.
        """
        return key in self._keys() or key in self.data

    def __iter__(self):
        return self._keys()

    def __len__(self):
        return len(list(self._keys()))


def deduplicate(sequence: list | None) -> list | None:
    r"""Deduplicate a list and preserve its order.

    The first occurrence of a value is kept. All later occurrences are
    discarded.

    For convenience, also accepts ``None`` and returns ``None`` in that case.

    Parameters
    ----------
    sequence
        List to deduplicate.
    """
    if not sequence:
        return sequence
    seen = set()
    return [x for x in sequence if not (x in seen or seen.add(x))]


def dict_to_asset_yaml(d: Dict) -> str:
    r"""Convert a dictionary to a YAML string, stripped of reserved-keys.

    Dictionaries that contain a map of comments (ruamel, etc) will have those
    comments included in the string.

    See Also
    --------
    onyo.lib.consts.RESERVED_KEYS

    Parameters
    ----------
    d
        Dictionary to strip of reserved-keys and convert to a YAML string.
    """
    # deepcopy to keep comments when `d` is `ruamel.yaml.comments.CommentedMap`.
    content = copy.deepcopy(d)
    for k in PSEUDO_KEYS + RESERVED_KEYS:
        if k in content.keys():
            del content[k]

    # Empty dicts are serialized to '{}', and I was unable to find any input
    # ('', None, etc) that would serialize to nothing. Hardcoding, though ugly,
    # seems to be the only option.
    if not content:
        return '---\n'

    from io import StringIO
    yaml = YAML(typ='rt')
    yaml.explicit_start = True
    s = StringIO()
    yaml.dump(content,
              s)
    return s.getvalue()


def get_asset_content(asset_file: Path) -> dict[str, bool | float | int | str | Path]:
    r"""Get the contents of an asset as a dictionary.

    If the asset file's contents are not valid YAML, an error is printed.

    Parameters
    ----------
    asset_file
        The Path of the asset file to get the contents of.
    """
    yaml = YAML(typ='rt', pure=True)
    contents = dict()
    try:
        contents = yaml.load(asset_file)
    except YAMLError as e:  # pyre-ignore[66]
        # Remove ruaml usage pointer (see github issue 436)
        if hasattr(e, 'note') and isinstance(e.note, str) and "suppress this check" in e.note:
            e.note = ""
        raise NotAnAssetError(f"Invalid YAML in {asset_file}:{os.linesep}{str(e)}") from e
    if contents is None:
        return dict()
    if not isinstance(contents, (dict, CommentedMap)):
        # For example: a simple text file may technically be valid YAML,
        # but we may get a string instead of dict.
        raise NotAnAssetError(f"{asset_file} does not appear to be an asset.")
    return contents


def get_temp_file() -> Path:
    r"""Create and return the Path of a new temporary file.
    """
    from tempfile import mkstemp
    fd, tmp_path = mkstemp(prefix='onyo_', suffix='.yaml', text=True)
    return Path(tmp_path)


def has_unique_names(asset_files: Set[Path]) -> bool:
    r"""Check files for unique file names.

    If duplicates are found, an error is printed listing them.

    Parameters
    ----------
    asset_files
        A set of files to check for the uniqueness of their file names.
    """
    asset_names = [a.name for a in asset_files]
    duplicates = [a for a in asset_files if asset_names.count(a.name) > 1]
    duplicates.sort(key=lambda x: x.name)

    if duplicates:
        ui.error('The following file names are not unique:\n{}'.format(
            '\n'.join(map(str, duplicates))))
        return False

    return True


def validate_yaml(asset_files: list[Path] | None) -> bool:
    r"""Check files for valid YAML.

    If files with invalid YAML are detected, an error is printed listing them.

    Parameters
    ----------
    asset_files
        A list of files to check for valid YAML.
    """
    # Note: Does not (and cannot) account for asset dirs automatically in this form.
    #       Thus needs to be done by caller.
    # Note: assumes absolute paths!
    invalid_yaml = []
    asset_files = asset_files or []
    for asset in asset_files:
        # TODO: use valid_yaml()
        try:
            YAML(typ='rt').load(asset)
        except scanner.ScannerError:  # pyre-ignore[66]
            invalid_yaml.append(str(asset))

    if invalid_yaml:
        ui.error('The following files fail YAML validation:\n{}'.format(
            '\n'.join(invalid_yaml)))
        return False

    return True


def write_asset_file(path: Path,
                     asset: Dict) -> None:
    r"""Write content to an asset file.

    All ``RESERVED_KEYS`` will be stripped from the content before writing.

    Parameters
    ----------
    path
        The Path to write content to.
    asset
        A dictionary of content to write to the path.
    """
    path.open('w').write(dict_to_asset_yaml(asset))


class YAMLDumpWrapper(UserDict):
    r"""Wrapper class for asset dicts accessing ruamel's representation of data rather than the provided object.

    This works around the issue that something like `serial: 001234` yields a `{'serial': 1234}` but is dumped as
    `serial: 001234`, which messes up onyo's comparisons for whether there's a modification of an asset.
    """
    def __init__(self, d: dict):
        super().__init__(d)

    def __getitem__(self, item: Hashable):
        if item not in self.keys():
            raise KeyError(item)
        if isinstance(self.data[item], (dict, list)):
            return YAMLDumpWrapper(self.data[item])
        if isinstance(self.data[item], Path):
            return self.data[item]  # no representer for this
        return RoundTripRepresenter(dumper=RoundTripDumper(stream=StringIO())).represent_data(self.data[item]).value


def is_equal_assets_dict(a: Dict | UserDict, b: Dict | UserDict) -> bool:
    r"""Whether two asset dictionaries have the same content.

    This accounts for comments in YAML.
    For this to return `True`, both assets need to
    be equal not only in terms of their key-value pairs,
    but also in terms of annotated comments.

    This also accounts for nested dicts recursively.
    """
    # TODO: This may become part of (thin) Asset class instead,
    # if there are more reasons to have such a class.
    if isinstance(a, DotNotationWrapper):
        a = a.data
    if isinstance(b, DotNotationWrapper):
        b = b.data

    # Need to recurse into nested dicts!
    for k, v in a.items():
        if isinstance(v, (dict, UserDict)):
            try:
                eq_ = is_equal_assets_dict(a[k], b[k])
            except (KeyError, TypeError):
                eq_ = False
            if not eq_:
                return False

    if not isinstance(a, CommentedMap) and not isinstance(b, CommentedMap):
        return a == b

    if YAMLDumpWrapper(a) != YAMLDumpWrapper(b):
        # not accounting for comments yet
        return False

    # Note, that ruamel does appear to implement `__eq__` and `__contains__` for the relevant objects.
    # However, it all breaks when comparing across files, b/c the `start_mark` attribute of a `CommentToken`
    # is a `FileMark` (when the YAML was read from file, ofc) which holds the path. So, comparison is only
    # ever equal if both `CommentedMap` are pointing to the same file.
    # Hence, we need our own comparison, that ignores the path.
    from ruamel.yaml.comments import Comment, comment_attrib  # pyre-ignore[21] pyre doesn't find a comments module
    from ruamel.yaml import CommentToken
    a_comment = getattr(a, comment_attrib, Comment())
    b_comment = getattr(b, comment_attrib, Comment())

    def contains_all_comments(container: Comment, comment: Comment) -> bool:  # pyre-ignore[11] - see `Comment` import
        for a_key, a_values in comment.items.items():
            try:
                b_values = container.items.get(a_key)
            except KeyError:
                # `a` has an annotation at a key that's not in `b`'s annotations
                return False
            if not b_values:
                return False
            if len(a_values) != len(b_values):
                # Not sure whether this is necessary (may be a defined, fixed length),
                # but better be safe.
                return False
            for a_v, b_v in zip(a_values, b_values):
                if type(a_v) is not type(b_v):
                    return False
                if isinstance(a_v, CommentToken) and \
                        (a_v.value, a_v.start_mark.line, a_v.start_mark.column) != \
                        (b_v.value, b_v.start_mark.line, b_v.start_mark.column):
                    return False
        return True
    return contains_all_comments(b_comment, a_comment) and contains_all_comments(a_comment, b_comment)
