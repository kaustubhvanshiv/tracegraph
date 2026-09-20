# tracegraph
AI-assisted graph-based security investigation platform for SOC incident reconstruction.

cd "c:\codes\PBL sem 7\tracegraph\backend"

# Create a virtual environment (one time)
python -m venv .venv

# Activate it
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
