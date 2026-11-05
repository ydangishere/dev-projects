"""Run: python -m triage_agent.cli --mode mock --output reports"""
import argparse
import os
from pathlib import Path
from .connectors import load_items
from .engine import triage
from .report import report


def main():
    parser = argparse.ArgumentParser(description="Jira/Gmail bug report triage (read-only)")
    parser.add_argument("--mode", choices=["mock","jira","gmail","both"],
                        default=os.getenv("SOURCE_MODE", "mock"))
    parser.add_argument("--fixture", type=Path, default=Path("fixtures/issues.json"))
    parser.add_argument("--output", type=Path, default=Path("reports"))
    parser.add_argument("--max-items", type=int, default=100)
    args = parser.parse_args()
    if args.max_items < 1 or args.max_items > 500:
        parser.error("--max-items must be between 1 and 500")
    items = load_items(args.mode,args.fixture,args.max_items)
    detected = triage(items, ai_enabled=os.getenv("ENABLE_AI", "false").lower() == "true")
    md,js = report(detected,args.output,args.mode)
    print(f"Mode={args.mode.upper()} | items={len(items)} | classified={sum(x['scenario_id'] is not None for x in detected)}")
    print(f"Reports: {md} | {js}")
    print("Advisory only. No ticket, email, code or database modifications made.")

if __name__ == "__main__":
    main()
