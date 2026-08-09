#!/usr/bin/env python3
"""
Migration: read the yyyy-mm-dd date tag on each note in a given notebook,
write that date into user_created_time, then remove the tag.

Usage (inside the MCP container):
    podman run --rm --network host \\
        --secret joplin_token \\
        -v $(pwd)/tests:/app/tests:ro,z \\
        --entrypoint python joplin-mcp-server \\
        /app/tests/migrate_docker_dates.py --folder-id <id> [--dry-run]

Or on the host if Joplin is reachable at localhost:41184:
    JOPLIN_API_TOKEN=<your-token> python tests/migrate_docker_dates.py --folder-id <id> [--dry-run]

Safe to re-run: notes whose date tag is already gone are skipped.
"""
import argparse
import os
import re
import sys
from datetime import datetime, timezone

import httpx

BASE_URL = os.getenv("JOPLIN_BASE_URL", "http://localhost:41184")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--folder-id", required=True, help="Joplin folder ID to migrate")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def client() -> httpx.Client:
    secret_path = "/run/secrets/joplin_token"
    if os.path.exists(secret_path):
        with open(secret_path) as f:
            token = f.read().strip()
    else:
        token = os.getenv("JOPLIN_API_TOKEN", "").strip()
    if not token:
        print("ERROR: JOPLIN_API_TOKEN env var or Podman secret required")
        sys.exit(1)
    return httpx.Client(base_url=BASE_URL, params={"token": token})


def date_to_ms(date_str: str) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def list_all(c: httpx.Client, path: str, **params) -> list:
    items, page = [], 1
    while True:
        r = c.get(path, params={"page": page, "limit": 100, **params})
        r.raise_for_status()
        data = r.json()
        items.extend(data.get("items", []))
        if not data.get("has_more"):
            break
        page += 1
    return items


def main() -> None:
    args = parse_args()
    folder_id = args.folder_id
    dry_run = args.dry_run

    if dry_run:
        print("=== DRY RUN — no changes will be made ===\n")

    c = client()

    notes = list_all(c, f"/folders/{folder_id}/notes")
    print(f"Found {len(notes)} notes in folder {folder_id}\n")

    processed_tags: set[str] = set()
    skipped = updated = 0

    for note in notes:
        note_id = note["id"]
        tags = list_all(c, f"/notes/{note_id}/tags")
        date_tags = [t for t in tags if DATE_RE.match(t["title"])]

        if not date_tags:
            print(f"  SKIP  {note['title'][:60]}  (no date tag)")
            skipped += 1
            continue

        if len(date_tags) > 1:
            titles = [t["title"] for t in date_tags]
            print(f"  WARN  {note['title'][:60]}  multiple date tags: {titles} — using first")

        tag = date_tags[0]
        ts = date_to_ms(tag["title"])
        print(f"  {'DRY' if dry_run else 'SET'}  {note['title'][:60]}")
        print(f"         {tag['title']} → user_created_time={ts}")

        if not dry_run:
            c.put(f"/notes/{note_id}", json={"user_created_time": ts}).raise_for_status()
            c.delete(f"/tags/{tag['id']}/notes/{note_id}").raise_for_status()

        processed_tags.add(tag["id"])
        updated += 1

    print(f"\n{'Would update' if dry_run else 'Updated'}: {updated}  skipped: {skipped}")

    # Delete tags that are now empty
    print(f"\nCleaning up {len(processed_tags)} date tag(s)...")
    deleted_tags = 0
    for tag_id in processed_tags:
        remaining = list_all(c, f"/tags/{tag_id}/notes")
        if remaining:
            print(f"  SKIP delete tag {tag_id} — still has {len(remaining)} note(s)")
            continue
        print(f"  {'DRY DELETE' if dry_run else 'DELETE'} tag {tag_id}")
        if not dry_run:
            c.delete(f"/tags/{tag_id}").raise_for_status()
        deleted_tags += 1

    print(f"\n{'Would delete' if dry_run else 'Deleted'} {deleted_tags} tag(s)")
    print("\nDone.")


if __name__ == "__main__":
    main()
