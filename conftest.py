"""Empty on purpose: its presence makes pytest add the repo root to
sys.path (prepend import mode), so tests/test_api.py can `import api`
and `import engine` without a src-layout or installed package."""
