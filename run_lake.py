"""Safe Spark entry point from repository root.

Avoids shadowing Python's stdlib inspect module with logistics/inspect.py.
"""
from logistics.lake_etl import main

if __name__ == "__main__":
    main()
