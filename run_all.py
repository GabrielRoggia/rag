"""Reproduz todo o experimento em sequência:
ingestão -> EDA -> classificador de fonte -> avaliação da recuperação.

Uso:  python run_all.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from lgpd_rag import classifier, eda, evaluate, ingest  # noqa: E402

if __name__ == "__main__":
    for name, mod in [("ingestão", ingest), ("EDA", eda), ("classificador", classifier), ("avaliação RAG", evaluate)]:
        print(f"\n===== {name} =====")
        mod.main()
