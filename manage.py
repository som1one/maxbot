#!/usr/bin/env python3
"""
Management script for KVT Service Bot
"""

import sys
import os
import subprocess
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def run_alembic_command(args):
    """Run alembic command with proper environment"""
    cmd = ["alembic"] + args
    return subprocess.run(cmd, cwd=project_root)

def main():
    if len(sys.argv) < 2:
        print("Usage: python manage.py <command>")
        print("Commands:")
        print("  migrate          - Run database migrations")
        print("  create-migration - Create a new migration")
        print("  downgrade        - Downgrade database")
        print("  history          - Show migration history")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "migrate":
        result = run_alembic_command(["upgrade", "head"])
        sys.exit(result.returncode)
    
    elif command == "create-migration":
        if len(sys.argv) < 3:
            print("Usage: python manage.py create-migration <message>")
            sys.exit(1)
        message = sys.argv[2]
        result = run_alembic_command(["revision", "--autogenerate", "-m", message])
        sys.exit(result.returncode)
    
    elif command == "downgrade":
        result = run_alembic_command(["downgrade", "-1"])
        sys.exit(result.returncode)
    
    elif command == "history":
        result = run_alembic_command(["history"])
        sys.exit(result.returncode)
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
