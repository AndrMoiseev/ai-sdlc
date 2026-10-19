"""Compatibility namespace for the SDD shared document API."""
from shared import locate
__path__ = [str(locate() / "scripts/sdd_shared")]
