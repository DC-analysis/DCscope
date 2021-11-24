import collections
import functools
import pathlib
import shutil

from dclab.util import hashfile
from dclab.rtdc_dataset.feat_anc_plugin import plugin_feature


SUPPORTED_FORMATS = [
    ".py",
    ".modc"
]


class ExtensionManager:
    def __init__(self, store_path):
        self.store_path = pathlib.Path(store_path)
        self.store_path.mkdir(exist_ok=True, parents=True)
        self.extension_hash_dict = collections.OrderedDict()
        self.load_extensions_from_store()

    def __getitem__(self, key):
        return self.get_extension_or_bust(key)

    def __iter__(self):
        for ahash in self.extension_hash_dict:
            yield self.extension_hash_dict[ahash]

    def __len__(self):
        return len(self.extension_hash_dict)

    def get_extension_or_bust(self, ext):
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
        ext = Extension(path)
        if ext.hash not in self.extension_hash_dict:
            new_name = f"ext_{ext.type}_{ext.hash}{ext.suffix}"
            new_path = self.store_path / new_name
            shutil.copy2(path, new_path)
            ext.path = new_path
            self.extension_load(ext)
        return ext

    def load_extensions_from_store(self):
        # load all (enabled) extensions
        for pp in self.store_path.glob("ext_*"):
            if pp.suffix in SUPPORTED_FORMATS:
                ext = Extension(pp)
                self.extension_load(ext)

    def extension_load(self, ext):
        ext.load()
        self.extension_hash_dict[ext.hash] = ext

    def extension_remove(self, ext):
        ext = self.get_extension_or_bust(ext)
        self.extension_hash_dict.pop(ext.hash)
        # reinstantiate ext to get the path right
        ext.destroy()

    def extension_set_enabled(self, ext, enabled):
        ext = self.get_extension_or_bust(ext)
        ext.set_enabled(enabled)


class Extension:
    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.suffix = self.path.suffix
        self.path_lock_disabled = self.path.with_name(
            self.path.name + "_disabled")

    @property
    @functools.lru_cache()
    def description(self):
        description = "No description provided."
        if self.loaded:
            if self.type == "feat_anc_plugin":
                pfinst = self.get_plugin_feature_instances()[0]
                info = pfinst.plugin_feature_info
                description = info['long description']
        return description

    @property
    def enabled(self):
        return not self.path_lock_disabled.exists()

    @property
    @functools.lru_cache()
    def hash(self):
        return hashfile(self.path)

    @property
    def loaded(self):
        return bool(self.get_plugin_feature_instances())

    @property
    @functools.lru_cache()
    def title(self):
        title = self.path.name  # fallback
        if self.loaded:
            if self.type == "feat_anc_plugin":
                pfinst = self.get_plugin_feature_instances()[0]
                info = pfinst.plugin_feature_info
                title = f"{info['description']} ({info['version']})"
        return title

    @property
    @functools.lru_cache()
    def type(self):
        if self.path.suffix == ".py":
            return "feat_anc_plugin"
        else:
            raise ValueError(f"Cannot determine extension type: {self.path}!")

    def get_plugin_feature_instances(self):
        pf_instances = []
        for inst in plugin_feature.PlugInFeature.features:
            if (isinstance(inst, plugin_feature.PlugInFeature)
                    and self.path.samefile(inst.plugin_path)):
                pf_instances.append(inst)
        return pf_instances

    def set_enabled(self, enabled):
        if enabled:
            self.path_lock_disabled.unlink(missing_ok=True)
        else:
            self.path_lock_disabled.touch()

    def load(self):
        if not self.enabled or self.loaded:
            # do not load disabled extensions or extensions already loaded
            return

        if self.type == "feat_anc_plugin":
            plugin_feature.load_plugin_feature(self.path)

    def unload(self):
        if self.type == "feat_anc_plugin":
            for inst in self.get_plugin_feature_instances():
                plugin_feature.remove_plugin_feature(inst)

    def destroy(self):
        self.unload()
        self.path_lock_disabled.unlink(missing_ok=True)
        self.path.unlink(missing_ok=True)
