"""wcwidth module, https://github.com/jquast/wcwidth."""
from .wcwidth import (
    wcwidth, wcswidth,
    _get_package_version,
    get_supported_unicode_versions,
)  # noqa

__all__ = ('wcwidth', 'wcswidth', 'get_supported_unicode_versions')
__version__ = _get_package_version()
