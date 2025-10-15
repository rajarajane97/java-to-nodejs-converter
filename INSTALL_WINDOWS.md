## Install (Windows)

1. Install Python 3.11+
2. Open PowerShell and create a venv:

```powershell
py -3.11 -m venv .venv
. .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and set API keys if using cloud LLMs.

4. Run:

```powershell
python -m ai2node.main C:\path\to\java\project --out .\Output
```

5. Run tests:

```powershell
python scripts\run_tests.py --suite unit
```

### Install and Run (Windows)

1. Install Python 3.11+
2. Open PowerShell in Java2NodeAI
3. Create venv and install deps:
   - python -m venv .venv
   - .venv\Scripts\Activate.ps1
   - python -m pip install -U pip
   - pip install -r requirements.txt
4. Copy .env.example to .env, set GOOGLE_API_KEY (or other keys)
5. Help:
   - python -m ai2node.main --help

