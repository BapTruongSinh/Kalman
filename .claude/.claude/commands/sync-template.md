Sync the `.claude/` directory from the upstream orchestrated-project-template repository into this project. Follow these steps exactly:

## Steps

### 1. Fetch the upstream template

Run:
```bash
SYNC_TMP=$(mktemp -d /tmp/template-sync-XXXXXX)
git clone --filter=blob:none --sparse https://github.com/josipjelic/orchestrated-project-template "$SYNC_TMP" 2>&1
cd "$SYNC_TMP" && git sparse-checkout set .claude
```

If the clone fails (no internet, repo moved, etc.) stop immediately and report the error.

### 2. Build file lists

```bash
# All relative paths in upstream .claude/ (excluding .DS_Store)
UPSTREAM_FILES=$(find "$SYNC_TMP/.claude" -type f | sed "s|$SYNC_TMP/.claude/||" | grep -v '\.DS_Store' | sort)

# Read existing manifest (empty on first sync)
MANIFEST_PATH=".claude/.template-manifest"
MANIFEST_FILES=$([ -f "$MANIFEST_PATH" ] && cat "$MANIFEST_PATH" || echo "")
```

### 3. Show a diff summary

Compare upstream against the project's `.claude/` directory and report:

- **New files** — in upstream, not locally
- **Modified files** — in both but content differs
- **To delete** — in `.template-manifest` but no longer in upstream (template remnants that moved or were removed). If no manifest exists yet, this list will be empty.
- **Local-only (kept)** — locally present, not in manifest, not in upstream (project-specific customisations — never touched)

If there are no changes at all, say so and skip to clean-up.

### 4. Ask for confirmation

Present the full diff summary — including the deletion list — and ask the user: "Apply these changes? (yes/no)"

Do not proceed until the user confirms.

### 5. Apply the changes

```bash
# Delete template remnants (in manifest but gone from upstream)
while IFS= read -r f; do
  [ -z "$f" ] && continue
  if ! echo "$UPSTREAM_FILES" | grep -qx "$f"; then
    rm -f ".claude/$f"
  fi
done <<< "$MANIFEST_FILES"

# Add/overwrite all upstream files
cp -r "$SYNC_TMP/.claude/." .claude/

# Rewrite the manifest with the current upstream file list
echo "$UPSTREAM_FILES" > "$MANIFEST_PATH"
```

### 6. Report

List each file that was added, updated, or deleted.

### 7. Clean up

Remove the temp directory: `rm -rf "$SYNC_TMP"`
