"""wcwidth module, https://github.com/jquast/wcwidth."""
from .wcwidth import (
    wcwidth, wcswidth,
    get_version as __get_version,
    get_supported_unicode_versions,
)  # noqa

__all__ = ('wcwidth', 'wcswidth', 'get_supported_unicode_versions')
__version__ = __get_version()
