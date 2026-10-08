import sys
sys.dont_write_bytecode = True
from pathlib import Path
import importlib.util
source = Path(__file__).resolve().parents[4] / 'skills/sdd-apply/tests/conftest.py'
spec = importlib.util.spec_from_file_location('original_fixtures', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
project, basis, driver = module.project, module.basis, module.driver
