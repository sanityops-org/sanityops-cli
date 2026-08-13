#!/usr/bin/env bash
# Release script for sanityops-cli
# Usage: ./release.sh [patch|minor|major|<version>]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

CURRENT_VERSION=$(sed -n 's/^version = "\([^"]*\)"/\1/p' pyproject.toml)
echo "Current version: $CURRENT_VERSION"

if [ -z "${1:-}" ]; then
    echo "Usage: $0 [patch|minor|major|<version>]"
    echo "  patch: 0.0.1 -> 0.0.2"
    echo "  minor: 0.0.1 -> 0.1.0"
    echo "  major: 0.0.1 -> 1.0.0"
    echo "  <version>: specific version like 0.2.0"
    exit 1
fi

BUMP_TYPE="$1"

# Calculate new version
if [[ "$BUMP_TYPE" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    NEW_VERSION="$BUMP_TYPE"
else
    IFS='.' read -ra PARTS <<< "$CURRENT_VERSION"
    case "$BUMP_TYPE" in
        patch)
            NEW_VERSION="${PARTS[0]}.${PARTS[1]}.$((PARTS[2] + 1))"
            ;;
        minor)
            NEW_VERSION="${PARTS[0]}.$((PARTS[1] + 1)).0"
            ;;
        major)
            NEW_VERSION="$((PARTS[0] + 1)).0.0"
            ;;
        *)
            echo "Unknown bump type: $BUMP_TYPE"
            exit 1
            ;;
    esac
fi

echo "New version: $NEW_VERSION"

# Update pyproject.toml
sed -i '' "s/^version = \"[^\"]*\"/version = \"$NEW_VERSION\"/" pyproject.toml

# Update __init__.py
sed -i '' "s/^__version__ = \"[^\"]*\"/__version__ = \"$NEW_VERSION\"/" src/sanityops_cli/__init__.py

echo "Updated version to $NEW_VERSION in pyproject.toml and __init__.py"

# Check for uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    echo "Committing version bump..."
    git add pyproject.toml src/sanityops_cli/__init__.py
    git commit -m "Bump version to $NEW_VERSION"
fi

echo ""
echo "Ready to release v$NEW_VERSION"
echo ""
echo "Next steps:"
echo "  1. Review changes: git show"
echo "  2. Create and push tag: git tag v$NEW_VERSION && git push origin v$NEW_VERSION"
echo "  3. GitHub Actions will build and deploy automatically"
echo ""
read -p "Create and push tag now? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    git tag "v$NEW_VERSION"
    git push origin main --tags 
    echo "Tag v$NEW_VERSION pushed. Check progress at:"
    echo "  https://github.com/sanityops-org/sanityops-cli/actions"
fi