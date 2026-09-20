# tracegraph
AI-assisted graph-based security investigation platform for SOC incident reconstruction.

cd backend

# Create a virtual environment (one time)
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
# .\.venv\Scripts\Activate.ps1

# Windows Command Prompt
# .venv\Scripts\activate.bat

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
