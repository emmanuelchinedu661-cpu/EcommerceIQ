import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / "src"))

import model
import pipeline
import seed
from config import DB_PATH

reset = "--reset" in sys.argv

if reset or not DB_PATH.exists():
    print("== 1. Seed (fresh demo data) ==")
    seed.run()

else:
    print("== 1. Seed skipped: keeping your existing data ==")

print("== 2. Pipeline ==")
pipeline.run()
print("== 3. Model ==")
model.train()
print("\nDone. launch the dashboard with: streamlit run app.py")