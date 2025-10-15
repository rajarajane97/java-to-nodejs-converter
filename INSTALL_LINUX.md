## Install (Linux)

1. Install Python 3.11+
2. Create and activate venv:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and set keys if needed.

4. Run:

```bash
python -m ai2node.main /path/to/java/project --out ./Output
```

5. Tests:

```bash
python scripts/run_tests.py --suite unit
```

### Install and Run (Linux/macOS)

1. Install Python 3.11+
2. Open terminal in Java2NodeAI
3. Create venv and install deps:
   - python3 -m venv .venv
   - source .venv/bin/activate
   - python -m pip install -U pip
   - pip install -r requirements.txt
4. Copy .env.example to .env, set GOOGLE_API_KEY (or other keys)
5. Help:
   - python -m ai2node.main --help

