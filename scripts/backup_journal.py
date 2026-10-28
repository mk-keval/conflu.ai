"""Back up the paper-trade journal (D-74).

`data/` is gitignored, so the journal of record is not in version control.
This uses SQLite's online backup API (safe under WAL) and keeps the last N
dated copies.

    python scripts/backup_journal.py
    python scripts/backup_journal.py --keep 60
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.domain.workflow import journal_store  # noqa: E402


def backup(db_path: Path, out_dir: Path, keep: int) -> Path:
    if not db_path.exists():
        raise FileNotFoundError(f"journal DB not found: {db_path}")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = out_dir / f"{db_path.stem}_{stamp}.db"

    source = sqlite3.connect(db_path, timeout=30.0)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()

    copies = sorted(out_dir.glob(f"{db_path.stem}_*.db"))
    for old in copies[:-keep] if keep > 0 else []:
        old.unlink(missing_ok=True)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", help="Journal DB path (default: configured journal)")
    parser.add_argument("--out-dir", help="Backup directory (default: data/backups)")
    parser.add_argument("--keep", type=int, default=30, help="Copies to retain")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else journal_store.get_db_path()
    out_dir = Path(args.out_dir) if args.out_dir else REPO_ROOT / "data" / "backups"
    target = backup(db_path, out_dir, args.keep)
    print(f"Backed up {db_path} -> {target} ({target.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
