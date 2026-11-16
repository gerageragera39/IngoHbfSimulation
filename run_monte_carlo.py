
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent

# Change this to the actual installation path
ANYLOGIC = Path(
    r"C:\Program Files\AnyLogic 8.9 Personal Learning Edition\AnyLogic.exe"
)

MODEL = ROOT / "Ingo" / "Ingo.alp"

if not ANYLOGIC.is_file():
    raise FileNotFoundError(
        f"AnyLogic not found: {ANYLOGIC}"
    )

if not MODEL.is_file():
    raise FileNotFoundError(
        f"Model not found: {MODEL}"
    )

print("Starting Monte Carlo batch...")

subprocess.Popen(
    [
        str(ANYLOGIC),
        "-r",
        str(MODEL),
        "BatchMonteCarlo"
    ],
    cwd=str(MODEL.parent)
)

print("BatchMonteCarlo launch requested.")
print("Check the AnyLogic experiment window.")
print("Results will appear in Ingo/results.")
