"""shortify: split a long video into a sequential series of styled Shorts.

Public API::

    from shortify import Shortify

    job = Shortify(input="input.mp4", duration=45, style="podcast")
    result = job.run()
"""

from shortify.models.config import Config
from shortify.pipeline import Shortify, ShortifyResult

__version__ = "0.1.0"

__all__ = ["Shortify", "ShortifyResult", "Config", "__version__"]
