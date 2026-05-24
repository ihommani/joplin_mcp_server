#!/usr/bin/env python3
"""
One-time migration: read the yyyy-mm-dd date tag on each note in the docker
notebook, write that date into user_created_time, then remove the tag.

Usage (inside the MCP container, which can reach Joplin via host.containers.internal):
    podman run --rm --network host \\
        --secret joplin_token \\
        -v $(pwd)/tests:/app/tests:ro \\
        -e JOPLIN_BASE_URL=http://host.containers.internal:41184 \\
        --entrypoint python joplin-mcp-server \\
        /app/tests/migrate_docker_dates.py [--dry-run]

Or on the host if Joplin is reachable at localhost:41184:
    JOPLIN_TOKEN=<your-token> python tests/migrate_docker_dates.py [--dry-run]

Safe to re-run: notes whose date tag is already gone are skipped.
"""
import os
import re
import sys
from datetime import datetime, timezone

import httpx

DOCKER_FOLDER_ID = "19f09ae9a5e44a3caefd77faa579a1c7"
BASE_URL = os.getenv("JOPLIN_BASE_URL", "http://localhost:41184")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DRY_RUN = "--dry-run" in sys.argv


def client() -> httpx.Client:
    secret_path = "/run/secrets/joplin_token"
    if os.path.exists(secret_path):
        with open(secret_path) as f:
            token = f.read().strip()
    else:
        token = os.getenv("JOPLIN_TOKEN", "").strip()
    if not token:
        print("ERROR: JOPLIN_TOKEN env var or Podman secret required")
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
    if DRY_RUN:
        print("=== DRY RUN — no changes will be made ===\n")

    c = client()

    notes = list_all(c, f"/folders/{DOCKER_FOLDER_ID}/notes")
    print(f"Found {len(notes)} notes in docker folder\n")

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
        print(f"  {'DRY' if DRY_RUN else 'SET'}  {note['title'][:60]}")
        print(f"         {tag['title']} → user_created_time={ts}")

        if not DRY_RUN:
            c.put(f"/notes/{note_id}", json={"user_created_time": ts}).raise_for_status()
            c.delete(f"/tags/{tag['id']}/notes/{note_id}").raise_for_status()

        processed_tags.add(tag["id"])
        updated += 1

    print(f"\n{'Would update' if DRY_RUN else 'Updated'}: {updated}  skipped: {skipped}")

    # Delete tags that are now empty
    print(f"\nCleaning up {len(processed_tags)} date tag(s)...")
    deleted_tags = 0
    for tag_id in processed_tags:
        remaining = list_all(c, f"/tags/{tag_id}/notes")
        if remaining:
            print(f"  SKIP delete tag {tag_id} — still has {len(remaining)} note(s)")
            continue
        print(f"  {'DRY DELETE' if DRY_RUN else 'DELETE'} tag {tag_id}")
        if not DRY_RUN:
            c.delete(f"/tags/{tag_id}").raise_for_status()
        deleted_tags += 1

    print(f"\n{'Would delete' if DRY_RUN else 'Deleted'} {deleted_tags} tag(s)")
    print("\nDone.")


if __name__ == "__main__":
    main()
