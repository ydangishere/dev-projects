"""Run the expert API regression against disposable knowledge and indexes.

The shipped knowledge can contain real expert cases. Test fixtures must not
overwrite them or assume their IDs are available in the live store.
"""
import runpy
import shutil
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def run_isolated():
    sys.path.insert(0, str(ROOT))
    import dxa
    import expert
    import gemini_client
    import rag

    with TemporaryDirectory(prefix="dxa-expert-test-") as directory:
        base = Path(directory)
        data, index = base / "data", base / "index"
        data.mkdir()
        for name in ["videos.tsv", "raw_stats.tsv"]:
            shutil.copy2(dxa.DATA / name, data / name)
        for path in dxa.DATA.glob("knowledge*.json"):
            if path.name != "knowledge_expert.json":
                shutil.copy2(path, data / path.name)
        shutil.copytree(dxa.DATA / "clean", data / "clean")
        try:
            with patch.multiple(dxa, DATA=data, OUT=index), patch.multiple(
                expert,
                EXPERT_FILE=data / "knowledge_expert.json",
                HISTORY_FILE=data / "knowledge_expert_history.jsonl",
                UNANSWERED_FILE=data / "unanswered.jsonl",
            ), patch.object(gemini_client, "available", return_value=False):
                rag.reset()
                dxa.build()
                try:
                    runpy.run_path(str(ROOT / "test_expert.py"), run_name="__main__")
                except SystemExit as exc:
                    return exc.code or 0
                return 0
        finally:
            rag.reset()


if __name__ == "__main__":
    raise SystemExit(run_isolated())
