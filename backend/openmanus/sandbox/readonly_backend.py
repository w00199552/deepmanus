from __future__ import annotations

from deepagents.backends.filesystem import FilesystemBackend

class ReadOnlyFilesystemBackend(FilesystemBackend):

    def __init__(self, root_dir, **kwargs):
        kwargs["virtual_mode"] = True
        super().__init__(root_dir=root_dir, **kwargs)

    def write(self, *args, **kwargs):
        raise PermissionError("skills directory is read-only")

    def edit(self, *args, **kwargs):
        raise PermissionError("skills directory is read-only")

    def delete(self, *args, **kwargs):
        raise PermissionError("skills directory is read-only")
