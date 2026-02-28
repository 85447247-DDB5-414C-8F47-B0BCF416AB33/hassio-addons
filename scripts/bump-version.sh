#!/bin/bash
# Bump patch version for screenshot-frame addon

set -e

CONFIG_FILE="screenshot-frame/config.yaml"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: $CONFIG_FILE not found"
    exit 1
fi

# Extract current version
CURRENT_VERSION=$(grep "^version:" "$CONFIG_FILE" | sed 's/.*"\([^"]*\)".*/\1/')

if [ -z "$CURRENT_VERSION" ]; then
    echo "Error: Could not extract version from $CONFIG_FILE"
    exit 1
fi

# Parse version parts (e.g., "0.1.31" -> major=0, minor=1, patch=31)
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

# Increment patch version
NEW_PATCH=$((PATCH + 1))
NEW_VERSION="${MAJOR}.${MINOR}.${NEW_PATCH}"

# Update version in config.yaml
sed -i.bak "s/^version: \"$CURRENT_VERSION\"/version: \"$NEW_VERSION\"/" "$CONFIG_FILE"
rm -f "${CONFIG_FILE}.bak"

# Stage the updated file
git add "$CONFIG_FILE"

echo "Bumped version from $CURRENT_VERSION to $NEW_VERSION"
