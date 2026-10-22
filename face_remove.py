"""Safely remove an identity from the face recognition datastore."""

from __future__ import annotations

import argparse
import sys
from core_engine import FaceEngine


def remove_identity(name: str, model_name: str = "facenet") -> None:
    engine = FaceEngine(model_name=model_name)
    ok, msg = engine.remove_identity(name)
    if ok:
        print(f"[SUCCESS] {msg}")
    else:
        print(f"[ERROR] {msg}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Remove an identity from the face recognition datastore")
    parser.add_argument("--name", type=str, default=None, help="Identity name to remove")
    parser.add_argument("--model", type=str, default="facenet", choices=["facenet", "mobile_facenet"], help="Model name (default: facenet)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    name = args.name
    if not name:
        name = input("Enter identity name to remove: ").strip()
    if not name:
        print("Error: Name cannot be empty.")
        sys.exit(1)

    remove_identity(name, model_name=args.model)