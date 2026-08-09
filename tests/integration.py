#!/usr/bin/env python3
"""
Manual integration test — requires Joplin running at localhost:41184.

Usage:
    JOPLIN_API_TOKEN=<your-token> python tests/integration.py

This is NOT run in CI. Run it manually to verify end-to-end connectivity.
"""
import os
import sys

# Allow importing server from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server

token = os.getenv("JOPLIN_API_TOKEN")
if not token:
    print("ERROR: JOPLIN_API_TOKEN env var is required")
    sys.exit(1)

print("=== Joplin MCP Server Integration Test ===\n")

# 1. List folders
print("1. Listing folders...")
folders = server.list_folders()
print(f"   Found {len(folders.get('items', []))} folder(s)")

# 2. Create a test folder
print("2. Creating test folder...")
folder = server.create_folder(title="MCP Integration Test")
folder_id = folder["id"]
print(f"   Created folder: {folder_id}")

# 3. Create a test note in that folder
print("3. Creating test note...")
note = server.create_note(
    title="Integration Test Note",
    body="Created by integration test",
    parent_id=folder_id,
)
note_id = note["id"]
print(f"   Created note: {note_id}")

# 4. Get the note back
print("4. Retrieving note...")
fetched = server.get_note(note_id=note_id)
assert fetched["title"] == "Integration Test Note", f"Unexpected title: {fetched['title']}"
print("   Title matches.")

# 5. Update the note
print("5. Updating note...")
server.update_note(note_id=note_id, title="Updated Integration Test Note")
updated = server.get_note(note_id=note_id)
assert updated["title"] == "Updated Integration Test Note"
print("   Update confirmed.")

# 6. Create and apply a tag
print("6. Creating and applying tag...")
tag = server.create_tag(title="integration-test")
tag_id = tag["id"]
server.tag_note(tag_id=tag_id, note_id=note_id)
print(f"   Tag {tag_id} applied to note.")

# 7. Search
print("7. Searching...")
results = server.search(query="Integration Test Note")
assert any(r["id"] == note_id for r in results.get("items", [])), "Note not found in search"
print("   Search found the note.")

# 8. Cleanup
print("8. Cleaning up...")
server.untag_note(tag_id=tag_id, note_id=note_id)
server.delete_tag(tag_id=tag_id)
server.delete_note(note_id=note_id)
server.delete_folder(folder_id=folder_id)
print("   Cleanup complete.")

print("\n=== All integration tests passed ===")
