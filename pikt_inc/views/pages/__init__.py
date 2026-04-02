from .blog import *
from .contact import *
from .quote import *

__all__ = [name for name in globals() if not name.startswith("_")]
