#!/usr/bin/env python3
import sys

sys.path.insert(0, "/app/src")

try:
    print("Importing config...")
    from backend.config import settings

    print("Config imported")

    print("Importing database...")
    from backend.database import engine

    print("Database imported")

    print("Creating FastAPI app...")
    from fastapi import FastAPI

    app = FastAPI()
    print("FastAPI app created")

    print("All imports successful!")

except Exception as e:
    print(f"Import failed: {e}")
    import traceback

    traceback.print_exc()
