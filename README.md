TRACK_ID=PS03
# StoreSense - Sales & Inventory Copilot

StoreSense is a retail decision-support application for PS03. It loads local store, product, sales, and inventory data, calculates deterministic retail signals, and uses Gemini to understand natural-language questions and explain evidence-backed results.

## Features
- Dashboard with revenue, units, products, stores and attention count.
- Likely stock-out detection.
- Slow-moving inventory detection.
- Sales spike/drop detection.
- Recommended manager actions with figures and assumptions.
- Natural-language copilot.
- Explicit refusal when the available data cannot answer a question.
- Evidence view for alerts.

## Run
Python 3.11:
    pip install -r requirements.txt
    python app.py

Open http://localhost:8000

Optional Gemini configuration:
Linux/macOS:
    export GEMINI_API_KEY="your-key"
Windows PowerShell:
    $env:GEMINI_API_KEY="your-key"

The dashboard works without Gemini. If Gemini is unavailable, the copilot falls back to safe local responses.

## Data
Generated sample data includes 3 stores, 20 products, 90 days of daily sales and current inventory. The data deliberately contains stock-out risk, slow-moving stock, sales spikes, sales drops and normal products.

## Architecture
- src/database.py: local CSV data access
- src/analytics.py: deterministic retail calculations/rules
- src/copilot.py: Gemini interpretation/explanation
- frontend/: single-page dashboard
- app.py: FastAPI entry point

## Demo video
Replace this line with the final demo URL before submission.

## Engineering principle
Business metrics are calculated locally. Gemini receives application evidence and explains it; it is not trusted to invent business numbers. Recommendations state assumptions and unsupported questions are not guessed.
