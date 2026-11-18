
import os
import re
from pathlib import Path
from collections import defaultdict

PROJECT_DIR = Path(__file__).resolve().parent

# Folders and files to ignore
IGNORE_DIRS = {
    ".venv", "venv", ".git", "__pycache__",
    "node_modules", "site-packages", "dist", "build"
}

# Possible database table references
PATTERNS = [
    ("CREATE TABLE", r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`]?([\w.]+)"),
    ("INSERT INTO", r"\bINSERT\s+INTO\s+[\"`]?([\w.]+)"),
    ("UPDATE", r"\bUPDATE\s+[\"`]?([\w.]+)\s+SET\b"),
    ("DELETE FROM", r"\bDELETE\s+FROM\s+[\"`]?([\w.]+)"),
    ("FROM", r"\bFROM\s+[\"`]?([\w.]+)"),
    ("JOIN", r"\bJOIN\s+[\"`]?([\w.]+)"),
    ("REFERENCES", r"\bREFERENCES\s+[\"`]?([\w.]+)")
]

EXCLUDED_WORDS = {
    "select", "where", "values", "set", "returning",
    "on", "using", "lateral", "only", "dual"
}

results = defaultdict(list)

def scan_project():
    print("\n========== RAB APPLICATION TABLE AUDIT ==========")
    print("Project:", PROJECT_DIR)

    for root, dirs, files in os.walk(PROJECT_DIR):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for filename in files:
            path = Path(root) / filename

            if path.suffix.lower() not in {".py", ".sql"}:
                continue

            try:
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            # Remove Python comments and SQL comments
            content = re.sub(r'(?m)^\s*#.*$', '', content)
            content = re.sub(r'--[^\n]*', '', content)
            content = re.sub(r'/\*.*?\*/', '', content, flags=re.S)

            for label, pattern in PATTERNS:
                for match in re.finditer(pattern, content, re.I):
                    table = match.group(1).strip('"`')
                    table = table.split(".")[-1]

                    if table.lower() in EXCLUDED_WORDS:
                        continue

                    line = content[:match.start()].count("\n") + 1

                    results[table].append(
                        (label, str(path.relative_to(PROJECT_DIR)), line)
                    )

    if not results:
        print("\nNo direct SQL table references detected.")

    for table in sorted(results):
        print(f"\nTABLE CANDIDATE: {table}")

        for operation, file, line in results[table]:
            print(f"  {operation:15} | {file} | Line {line}")

    print("\n========== AUDIT SUMMARY ==========")
    print("Unique table candidates:", len(results))
    print("Review each candidate before treating it as a confirmed table.")

    # Save evidence to a text file
    output = PROJECT_DIR / "daily_app_table_audit.txt"

    with output.open("w", encoding="utf-8") as f:
        f.write("RAB DAILY RENTAL APP - TABLE AUDIT\n\n")

        for table in sorted(results):
            f.write(f"\nTABLE: {table}\n")

            for operation, file, line in results[table]:
                f.write(f"{operation} | {file} | Line {line}\n")

    print("\nAudit saved to:", output)

if __name__ == "__main__":
    scan_project()