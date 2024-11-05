import collections
import functools
import pathlib
import shutil

from dclab.util import hashfile
from dclab.rtdc_dataset.feat_anc_plugin import plugin_feature


SUPPORTED_FORMATS = [
    ".py",
]


class ExtensionManager:
    def __init__(self, store_path):
        """Extension manager

        This class can be used to maintain a set of extensions
        (plugin features or machine-learning features) at a
        specific location `store_path` on the file system.

        All extensions are loaded during instantiation. It is
        possible to disable individual extensions (without
        deleting them) on-the-fly.
        """
        self.store_path = pathlib.Path(store_path)
        self.store_path.mkdir(exist_ok=True, parents=True)
        self.extension_hash_dict = collections.OrderedDict()
        self.load_extensions_from_store()

    def __contains__(self, key):
        if isinstance(key, Extension):
            key = key.hash
        return key in self.extension_hash_dict

    def __getitem__(self, key):
        return self.get_extension_or_bust(key)

    def __iter__(self):
        for ahash in self.extension_hash_dict:
            yield self.extension_hash_dict[ahash]

    def __len__(self):
        return len(self.extension_hash_dict)

    def get_extension_or_bust(self, ext):
        """Return an Extension instance or raise ValueError

        Parameter `ext` can be an instance of Extension, an
        extension hash, or an index. If an Extension or a
        hash is provided, this function checks whether the
        extension is maintained by this manager and returns
        the correct instance.

        Parameters
        ----------
        ext: Extension
            Extension instance
        """
        if isinstance(ext, Extension):
            the_hash = ext.hash
        elif isinstance(ext, int):
            the_hash = list(self.extension_hash_dict.keys())[ext]
        else:
            the_hash = ext
        if the_hash in self.extension_hash_dict:
            return self.extension_hash_dict[the_hash]
        else:
            raise ValueError(f"Extension not in {self.store_path}: {the_hash}")

    def import_extension_from_path(self, path):
        """Import an extension file to `self.store_path`"""
        ext = Extension(path)
        if ext.hash not in self.extension_hash_dict:
            new_name = f"ext_{ext.type}_{ext.hash}{ext.suffix}"
            new_path = self.store_path / new_name
            shutil.copy2(path, new_path)
            ext.path = new_path
            self.extension_load(ext)
        return ext

    def load_extensions_from_store(self):
        """Load all extensions from `self.store_path`

        This function is called during initialization.
        """
        failed = []
        # load all (enabled) extensions
        for pp in self.store_path.glob("ext_*"):
            if pp.suffix in SUPPORTED_FORMATS:
                ext = Extension(pp)
                try:
                    self.extension_load(ext)
                except BaseException:
                    failed.append(ext)
        if failed:
            raise ValueError(f"Could not load these extensions: {failed}")

    def extension_load(self, ext):
        """Load a single extension

        Parameters
        ----------
        ext: Extension
            Extension instance
        """
        # add to hash dict first in case it gets disabled
        self.extension_hash_dict[ext.hash] = ext
        ext.load()

    def extension_remove(self, ext):
        """Remove an extension from `self.store_path` and unload it

        Parameters
        ----------
        ext: Extension or str or int
            Extension instance, its hash or its index in
            ExtensionManager
        """
        ext = self.get_extension_or_bust(ext)
        self.extension_hash_dict.pop(ext.hash)
        # re-instantiate ext to get the path right
        ext.destroy()

    def extension_set_enabled(self, ext, enabled):
        """Enable or disable an extension

        Parameters
        ----------
        ext: Extension or str or int
            Extension instance, its hash or its index in
            ExtensionManager
        enabled: bool
            Whether to enable the extension.
        """
        ext = self.get_extension_or_bust(ext)
        ext.set_enabled(enabled)


class Extension:
    def __init__(self, path):
        """Helper class for managing individual extensions"""
        self.path = pathlib.Path(path)
        self.suffix = self.path.suffix

    def __repr__(self):
        return f"<Shape-Out Extension {self.path} at {hex(id(self))}>"

    @property
    def description(self):
        """Description of the extension"""
        description = "No description provided."
        if self.loaded:
            if self.type == "feat_anc_plugin":
                pfinst = self.get_plugin_feature_instances()[0]
                info = pfinst.plugin_feature_info
                description = info['long description']
        return description

    @property
    def enabled(self):
        """Whether the extension is enabled"""
        return not self.path_lock_disabled.exists()

    @property
    @functools.lru_cache()
    def hash(self):
        """MD5 hash of the extension"""
        return hashfile(self.path)

    @property
    def loaded(self):
        """Whether the extension is currently loaded"""
        if self.type == "feat_anc_plugin":
            return bool(self.get_plugin_feature_instances())

    @property
    def path_lock_disabled(self):
        return self.path.with_name(self.path.name + "_disabled")

    @property
    def title(self):
        """Descriptive title including version of the extension"""
        title = self.path.name  # fallback
        if self.loaded:
            if self.type == "feat_anc_plugin":
                pfinst = self.get_plugin_feature_instances()[0]
                info = pfinst.plugin_feature_info
                title = f"{info['description']} " \
                    + f"({info['version']}-{info['identifier'][:4]})"
        return title

    @property
    @functools.lru_cache()
    def type(self):
        """Type of the extension (e.g. "feat_anc_plugin")"""
        if self.path.suffix == ".py":
            return "feat_anc_plugin"
        else:
            raise ValueError(f"Cannot determine extension type: {self.path}!")

    def get_plugin_feature_instances(self):
        """Return a list of all PlugInFeature instances for this extension"""
        pf_instances = []
        for inst in plugin_feature.PlugInFeature.features:
            if (isinstance(inst, plugin_feature.PlugInFeature)
                    and self.path.samefile(inst.plugin_path)):
                pf_instances.append(inst)
        return pf_instances

    def set_enabled(self, enabled):
        """Set this extension to enabled (True) or disabled (False)

        The extension is also loaded (True) or unloaded (False).
        """
        if enabled:
            # set enabled so that `load` works
            self.path_lock_disabled.unlink(missing_ok=True)
            self.load()
        else:
            self.unload()
            self.path_lock_disabled.touch()

    def load(self):
        """Load the extension if it is enabled and not loaded"""
        if not self.enabled or self.loaded:
            # do not load disabled extensions or extensions already loaded
            return

        try:
            if self.type == "feat_anc_plugin":
                plugin_feature.load_plugin_feature(self.path)
        except BaseException:
            # If loading the extension fails, disable it and only then
            # raise the exception.
            self.set_enabled(False)
            raise

    def unload(self):
        """Unload the extension"""
        if self.type == "feat_anc_plugin":
            for inst in self.get_plugin_feature_instances():
                plugin_feature.remove_plugin_feature(inst)

    def destroy(self):
        """Unload and remove the extension"""
        self.unload()
        self.path_lock_disabled.unlink(missing_ok=True)
        self.path.unlink(missing_ok=True)
