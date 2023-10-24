from __future__ import annotations

from pathlib import Path
from typing import Union, Iterable, Optional, Set, Generator
from dataclasses import dataclass
from typing import Callable

from onyo.lib.assets import Asset
from onyo.lib.onyo import OnyoRepo
from onyo.lib.filters import Filter
from onyo.lib.executors import (
    exec_new_assets,
    exec_new_directories,
    exec_modify_assets,
    exec_remove_assets,
    exec_move_assets,
    exec_rename_assets,
    exec_remove_directories,
    exec_rename_directories,
    exec_move_directories
)
from onyo.lib.recorders import (
    record_new_assets,
    record_new_directories,
    record_rename_assets,
    record_modify_assets,
    record_move_assets,
    record_remove_assets,
    record_remove_directories,
    record_rename_directories,
    record_move_directories
)
from onyo.lib.differs import (
    differ_new_assets,
    differ_new_directories,
    differ_rename_directories,
    differ_modify_assets,
    differ_move_assets,
    differ_remove_assets,
    differ_rename_assets,
    differ_remove_directories,
    differ_move_directories,
)
from onyo.lib.exceptions import (
    NotAnAssetError,
    NoopError,
    InvalidInventoryOperation,
)

# The following keys have functional meaning for onyo and must not be part of user-defined asset content
RESERVED_KEYS = ['directory', 'is_asset_directory', 'template']


@dataclass
class InventoryOperator:
    executor: Callable
    differ: Callable
    recorder: Callable


@dataclass
class InventoryOperation(object):
    operator: InventoryOperator
    operands: tuple
    repo: OnyoRepo

    def diff(self) -> Generator[str, None, None]:
        yield from self.operator.differ(repo=self.repo, operands=self.operands)

    def execute(self) -> tuple[list[Path], list[Path]]:
        return self.operator.executor(repo=self.repo, operands=self.operands)


# NOTE: Order of keys in this mapping matters! It's the order of execution during `Inventory.commit`.
#       We'd need new directories before new assets for example. Or remove something before putting something else in
#       its place.
#       Solution may be to change implementation and really register a single list of operations so call-order is
#       preserved.  -> speaks for class InventoryOperation?
OPERATIONS_MAPPING: dict = {'new_directories': InventoryOperator(executor=exec_new_directories,
                                                                 differ=differ_new_directories,
                                                                 recorder=record_new_directories),
                            'new_assets': InventoryOperator(executor=exec_new_assets,
                                                            differ=differ_new_assets,
                                                            recorder=record_new_assets),
                            'remove_assets': InventoryOperator(executor=exec_remove_assets,
                                                               differ=differ_remove_assets,
                                                               recorder=record_remove_assets),
                            'modify_assets': InventoryOperator(executor=exec_modify_assets,
                                                               differ=differ_modify_assets,
                                                               recorder=record_modify_assets),
                            'rename_assets': InventoryOperator(executor=exec_rename_assets,
                                                               differ=differ_rename_assets,
                                                               recorder=record_rename_assets),
                            'remove_directories': InventoryOperator(executor=exec_remove_directories,
                                                                    differ=differ_remove_directories,
                                                                    recorder=record_remove_directories),
                            'move_directories': InventoryOperator(executor=exec_move_directories,
                                                                  differ=differ_move_directories,
                                                                  recorder=record_move_directories),
                            'rename_directories': InventoryOperator(executor=exec_rename_directories,
                                                                    differ=differ_rename_directories,
                                                                    recorder=record_rename_directories),
                            'move_assets': InventoryOperator(executor=exec_move_assets,
                                                             differ=differ_move_assets,
                                                             recorder=record_move_assets),
                            }


# TODO: Conflict w/ existing operations?
#       operations: raise InvalidInventoryOperationError on conflicts with pending operations,
#       like removing something that is to be created. -> reset() or commit()
# TODO: clear_caches from within commit? What about operations?
class Inventory(object):
    """"""

    def __init__(self, repo: OnyoRepo):
        self.repo: OnyoRepo = repo
        self.operations: list[InventoryOperation] = []

    @property
    def root(self):
        """Path to root inventory directory"""
        return self.repo.git.root

    def reset(self):
        """throw away pending operations"""
        self.operations = []

    def commit(self, message: str):
        """Execute and git-commit pending operations"""
        # get user message + generate appendix from operations
        # does order matter for execution? Prob.
        # ^  Nope. Fail on conflicts.
        from os import linesep
        paths_to_commit = []
        paths_to_stage = []
        commit_msg = message + f"{linesep}{linesep}--- Inventory Operations ---{linesep}"
        operations_record = dict()

        for operation in self.operations:
            to_commit, to_stage = operation.execute()
            paths_to_commit.extend(to_commit)
            paths_to_stage.extend(to_stage)
            record_snippets = operation.operator.recorder(repo=self.repo, operands=operation.operands)
            for k, v in record_snippets.items():
                if k not in operations_record:
                    operations_record[k] = v
                else:
                    operations_record[k].extend(v)

        for title, snippets in operations_record.items():
            commit_msg += title + ''.join(line for line in set(snippets))

        # TODO: Actually: staging (only new) should be done in execute. committing is then unified
        self.repo.git.stage_and_commit(set(paths_to_commit + paths_to_stage), commit_msg)
        self.reset()

    def diff(self) -> Generator[str, None, None]:
        for operation in self.operations:
            yield from operation.diff()

    def operations_pending(self) -> bool:
        """Returns whether there's something to commit"""
        # Note: Seems superfluous now (operations is a list rather than dict of lists)
        return bool(self.operations)

    #
    # Operations
    #

    def _add_operation(self, name: str, operands: tuple) -> None:
        """Internal convenience helper to register an operation"""
        self.operations.append(InventoryOperation(operator=OPERATIONS_MAPPING[name],
                                                  operands=operands,
                                                  repo=self.repo)
                               )

    def add_asset(self, asset: Asset) -> None:
        # TODO: This could actually contain a lot of what's in `new`. directory, template, validation, faux-serials, ...
        #       Except this does not work because of --edit, which requires things being written to disc already.
        #       Could use a temp file, but kinda weird for users seeing that path in their editor.
        #       However, chat decision: temp path in editor is fine

        # what if I call this with a modified (possibly moved) asset?

        # validation (of path, name, etc) required! (Otherwise it would be delayed until execution!)
        # TODO: Just like the validation should be included (see above), we also want to pass `directory` instead of
        #       `path` since filename needs to be generated.
        path = asset.get('path', None)
        if not path:
            raise ValueError("Unknown asset path")
        if self.repo.is_asset_path(path):
            raise ValueError(f"Asset {path} already exists.")
            # Note: We may want to reconsider this case.
            # Shouldn't there be a way to write files (or asset dirs) directly and then add them as new assets?
        if not self.repo.is_inventory_path(path):
            raise ValueError(f"{path} is not a valid inventory path.")

        if asset.get('is_asset_directory', False):
            if self.repo.is_inventory_dir(path):
                # We want to turn an existing dir into an asset dir.
                self.rename_directory(path, self.generate_asset_name(asset))
                # Temporary hack: Adjust the asset's path to the renamed one.
                # TODO: Actual solution: This entire method must not be based on the dict's 'path', but 'directory' +
                #       generated name. This ties in with pulling parts of `onyo_new` in here.
                asset['path'] = path.parent / self.generate_asset_name(asset)
            else:
                # The directory does not yet exist.
                self.add_directory(path)
        elif not self.repo.is_inventory_dir(path.parent):
            self.add_directory(path.parent)

        # record operation
        self._add_operation('new_assets', (asset,))

    def add_directory(self, path: Path) -> None:
        if not self.repo.is_inventory_path(path):
            raise ValueError(f"{path} is not a valid inventory path.")
        if path.exists():
            raise ValueError(f"{path} already exists.")

        self._add_operation('new_directories', (path,))
        [self._add_operation('new_directories', (p,)) for p in path.parents if not p.exists()]

    def remove_asset(self, asset: Union[Asset, Path]) -> None:
        path = asset if isinstance(asset, Path) else asset.get('path')
        if not self.repo.is_asset_path(path):
            raise NotAnAssetError(f"No such asset: {path}")
        self._add_operation('remove_assets', (asset,))

    def move_asset(self, src: Union[Path, Asset], dst: Path) -> None:
        if isinstance(src, Asset):
            src = Path(src.get('path'))
        if not self.repo.is_asset_path(src):
            raise NotAnAssetError(f"No such asset: {src}.")
        if src.parent == dst:
            # TODO: Instead of raise could be a silent noop.
            raise ValueError(f"Cannot move {src}: Destination {dst} is the current location.")
        if not self.repo.is_inventory_dir(dst):
            raise ValueError(f"Cannot move {src}: Destination {dst} is not in inventory directory.")

        self._add_operation('move_assets', (src, dst))

    def rename_asset(self, asset: Union[Asset, Path], name: Optional[str] = None) -> None:
        # ??? Do we need that? On the command level it's only accessible via modify_asset.
        # But: A config change is sufficient to make it not actually an asset modification.
        # Also: If we later on want to allow it under some circumstances, it would be good have it as a formally
        #       separate operation already.

        path = Path(asset.get('path')) if isinstance(asset, Asset) else asset
        if not self.repo.is_asset_path(path):
            raise ValueError(f"No such asset: {path}")

        # Note: For now we force the asset name (via config) from its content. Hence, `name` is optional and when it's
        #       given it needs to match.
        #       TODO: This may, however, need to go. When rename is implicit, it would need to account for already
        #             registered modify operations. It's easier to not force compliance here, but simply let
        #             modify_asset generate the name and pass it.
        generated_name = self.generate_asset_name(
            asset if isinstance(asset, Asset)
            else self.repo.get_asset_content(path)
        )
        if name and name != generated_name:
            raise ValueError(f"Renaming asset {path.name} to {name} is invalid."
                             f"Config 'onyo.assets.filename' suggests '{generated_name}' as its name")
        if not name:
            name = generated_name
        if path.name == name:
            # TODO: This should be a different exception, so that callers can decide on their failure paradigm:
            #       "Result oriented already-fine-no-failure" vs "Task oriented can't-do-failure".
            raise NoopError(f"Cannot rename asset {name}: This is already its name.")

        destination = path.parent / name
        if destination.exists():
            raise ValueError(f"Cannot rename asset {path.name} to {destination}. Already exists.")
        # TODO: Do we need to update asset['path'] here? See also modify_asset!
        self._add_operation('rename_assets', (path, destination))

    def modify_asset(self, asset: Union[Asset, Path], content: Asset) -> None:
        # TODO: Straight-up dict for `content`?

        path = Path(asset.get('path')) if isinstance(asset, Asset) else asset
        if not self.repo.is_asset_path(path):
            raise ValueError(f"No such asset: {path}")
        asset = Asset(self.repo.get_asset_content(path)) if isinstance(asset, Path) else asset
        new_asset = asset.copy()
        new_asset.update(content)

        self._add_operation('modify_assets', (asset, new_asset))
        # Abuse the fact that new_asset has the same 'path' at this point, regardless of potential renaming and let
        # rename handle it. Note, that this way the rename operation MUST come after the modification during execution.
        # Otherwise, we'd move the old asset and write the modified one to the old place.
        try:
            self.rename_asset(new_asset)
        except NoopError:
            # Modification did not imply a rename
            pass

    def remove_directory(self, directory: Path) -> None:
        if not self.repo.is_inventory_dir(directory):
            raise ValueError(f"Not an inventory directory: {directory}")
        # TODO: `force` for removing non-empty??? (-> implicit remove_asset OPs)
        #       But: What about non-asset files (.onyoignore)
        if [p for p in directory.iterdir()
                if p.name != self.repo.ANCHOR_FILE and not self.repo.is_onyo_path(p)]:
            raise InvalidInventoryOperation(f"Cannot remove inventory directory {directory}: Not empty.")
        self._add_operation('remove_directories', (directory,))

    def move_directory(self, src: Path, dst: Path) -> None:
        if not self.repo.is_inventory_dir(src):
            raise ValueError(f"Not an inventory directory: {src}")
        if not self.repo.is_inventory_dir(dst):
            raise ValueError(f"Destination is not an inventory directory: {dst}")
        if src.parent == dst:
            raise InvalidInventoryOperation(f"Cannot move {src} -> {dst}. Consider renaming instead.")
        self._add_operation('move_directories', (src, dst))

    def rename_directory(self, src: Path, dst: Union[str, Path]) -> None:
        if not self.repo.is_inventory_dir(src):
            raise ValueError(f"Not an inventory directory: {src}")
        if self.repo.is_asset_dir(src):
            raise ValueError("Renaming an asset directory must be done via `rename_asset`.")
        if isinstance(dst, str):
            dst = src.parent / dst
        if src.parent != dst.parent:
            raise InvalidInventoryOperation(f"Cannot rename {src} -> {dst}. Consider moving instead.")
        if not self.repo.is_inventory_path(dst) or dst.exists():
            raise ValueError(f"Not a valid destination: {dst}")

        self._add_operation('rename_directories', (src, dst))

    #
    # non-operation methods
    #

    def get_asset(self, path: Path):
        # read and return Asset
        if self.repo.is_asset_path(path):
            return Asset(**self.repo.get_asset_content(path))
        else:
            raise ValueError(f"{path} is not an asset.")

    def get_assets(self):
        # plural/query/property?
        # git ls-files?
        # Redirect to get_assets_by_query (making paths optional)
        pass

    def get_asset_from_template(self, template: str) -> Asset:
        # TODO: Possibly join with get_asset (path optional)
        return Asset(self.repo.get_template(template))

    def get_assets_by_query(self,
                            keys: Optional[Set[str]],
                            paths: Iterable[Path],
                            depth: Union[int, None] = None,
                            filters: Union[list[Filter], None] = None) -> Generator:
        # filters + path/depth limit (TODO: turn into filters as well)
        # self.repo.get_asset_paths(subtrees=, depth=)

        # Note: This is interested in the key-value pairs of assets, not their paths exactly.
        #       But tries to not read a file when pseudo keys are considered only.
        #       This is outdated but also requires adjustment of Filters.

        """
        Get keys from assets matching paths and filters.
        """
        # TODO: This won't be necessary anymore
        from .filters import asset_name_to_keys
        from .assets import PSEUDO_KEYS, get_asset_content

        # filter assets by path and depth relative to paths
        asset_paths = self.repo.get_asset_paths(subtrees=paths, depth=depth)

        if filters:
            # Filters that do not require loading an asset are applied first
            filters.sort(key=lambda x: x.is_pseudo, reverse=True)

            # Remove assets that do not match all filters
            for f in filters:
                asset_paths[:] = filter(f.match, asset_paths)

        # Obtain keys from remaining assets
        if keys:
            assets = ((a, {
                k: v
                for k, v in (get_asset_content(a) | asset_name_to_keys(a, PSEUDO_KEYS)).items()
                if k in keys}) for a in asset_paths)
        else:
            assets = ((a, {
                k: v
                for k, v in (get_asset_content(a) | asset_name_to_keys(a, PSEUDO_KEYS)).items()}) for a in asset_paths)

        return assets

    def asset_paths_available(self, assets: Union[Asset, list[Asset]]) -> None:
        """Test whether path(s) used by `assets` are available in the inventory.

        Availability not only requires the path to not yet exist, but also the filename to be unique.

        Raises
        ------
        ValueError
          if any of the paths can not be used for a new asset
        """

        # TODO: Used to test valid asset name first. Do we need that?
        #       Not in context of `new`, because the name is generated.
        paths_to_test = [a.get('path') for a in assets]
        for path in paths_to_test:
            if not path:
                continue  # TODO: raise or ignore?
            if path.exists():
                raise ValueError(f"{str(path)} already exists in inventory")
            if len([p.name for p in paths_to_test if p.name == path.name]) > 1:
                raise ValueError(f"Multiple {path.name} given. Asset names must be unique.")
            if not self.repo.is_inventory_path(path):
                raise ValueError(f"{str(path)} is not a valid asset path.")
            if path.name in [p.name for p in self.repo.asset_paths]:
                raise ValueError(f"Asset name '{path.name}' already exists in inventory.")

    def generate_asset_name(self, asset: Asset) -> str:

        config_str = self.repo.get_config("onyo.assets.filename")
        if not config_str:
            raise ValueError("Missing config 'onyo.assets.filename'.")
        # TODO: Problem: Empty string could be a valid value for some keys. But not for the required name fields?!
        #       -> doesn't raise, because that's not something `format` would stumble upon.
        try:
            name = config_str.format(**asset)  # TODO: Only pass non-pseudo keys?! What if there is no config?
        except KeyError as e:
            raise ValueError(f"Asset missing value for required field {str(e)}.") from e
        return name

    def get_faux_serials(self,
                         length: int = 6,
                         num: int = 1) -> set[str]:
        """
        Generate a unique faux serial and verify that it is not used by any
        other asset in the repository. The length of the faux serial must be 4
        or greater.

        Returns a set of unique faux serials.
        """
        import random
        import string

        if length < 4:
            # 62^4 is ~14.7 million combinations. Which is the lowest acceptable
            # risk of collisions between independent checkouts of a repo.
            raise ValueError('The length of faux serial numbers must be >= 4.')

        if num < 1:
            raise ValueError('The length of faux serial numbers must be >= 1.')

        alphanum = string.ascii_letters + string.digits
        faux_serials = set()
        # TODO: This split actually puts the entire filename in the set if there's no "faux".
        repo_faux_serials = {str(x.name).split('faux')[-1] for x in self.repo.asset_paths}

        while len(faux_serials) < num:
            serial = ''.join(random.choices(alphanum, k=length))
            if serial not in repo_faux_serials:
                faux_serials.add(f'faux{serial}')

        return faux_serials