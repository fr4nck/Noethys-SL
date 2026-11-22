"""Temporary test compatibility wrapper for Q442 candidate source."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "noethys"))
from Utils.UTILS_Stats_qf_sites import *
