#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status.
set -e
# Treat unset variables as an error when substituting.
# set -u
# Pipestatus: return value of a pipeline is the status of the last command to exit with a non-zero status.
set -o pipefail

PYPROJECT_TOML="pyproject.toml"

# --- Helper Functions ---
get_current_version() {
    grep '^version = ' "$PYPROJECT_TOML" | awk -F'"' '{print $2}'
}

increment_patch_version() {
    local current_version=$1
    local major minor patch
    major=$(echo "$current_version" | cut -d. -f1)
    minor=$(echo "$current_version" | cut -d. -f2)
    patch=$(echo "$current_version" | cut -d. -f3)
    patch=$((patch + 1))
    echo "${major}.${minor}.${patch}"
}

prompt_yes_no() {
    local prompt_message=$1
    local default_answer=${2:-N} # Default to No if not specified
    local answer

    while true; do
        read -r -p "$prompt_message [y/N]: " answer
        answer=${answer:-$default_answer} # Set to default if user just hits Enter
        case "$answer" in
            [Yy]* ) return 0;; # Yes
            [Nn]* ) return 1;; # No
            * ) echo "Please answer yes (y) or no (n).";;
        esac
    done
}

# --- Main Script ---

echo "🚀 Interactive PyPI Release Process for codesum 🚀"
echo "----------------------------------------------------"

# 0. Check if pyproject.toml exists
if [ ! -f "$PYPROJECT_TOML" ]; then
    echo "❌ Error: $PYPROJECT_TOML not found in the current directory."
    echo "Please run this script from the project root."
    exit 1
fi

# 1. Clean previous build artifacts
if prompt_yes_no "🧹 Would you like to clean previous build artifacts?"; then
    echo "   Cleaning previous build artifacts..."
    rm -rf dist build src/*.egg-info .summary_files # Add other project-specific temp dirs if needed
    echo "   ✅ Cleaned."
else
    echo "   Skipping cleaning."
fi
echo "----------------------------------------------------"

# 2. Version Increment
current_version=$(get_current_version)
if [ -z "$current_version" ]; then
    echo "❌ Error: Could not extract current version from $PYPROJECT_TOML."
    exit 1
fi
echo "🔎 Current version: $current_version"

new_version=$current_version # Start with current version

if prompt_yes_no "⬆️  Would you like to increment the patch version number from $current_version?"; then
    new_version=$(increment_patch_version "$current_version")
    echo "   📝 Updating $PYPROJECT_TOML with new version $new_version..."
    # Using sed -i.bak for portability (creates a backup pyproject.toml.bak)
    sed -i.bak "s/^version = \"$current_version\"/version = \"$new_version\"/" "$PYPROJECT_TOML"
    rm -f "${PYPROJECT_TOML}.bak" # Remove backup if sed was successful
    echo "   ✅ $PYPROJECT_TOML updated to $new_version."
else
    echo "   Skipping version increment. Using version $current_version for this release."
fi
echo "   ➡️  Version for this release will be: $new_version"
echo "----------------------------------------------------"


# 3. Git commit and tag (Optional but Recommended)
if command -v git &> /dev/null; then
    if prompt_yes_no "🐙 Would you like to perform Git operations (commit, tag, push)?"; then
        echo "   Git operations..."
        # Check if pyproject.toml was actually changed (if version was incremented)
        if [[ "$new_version" != "$current_version" ]]; then
            if git diff --quiet "$PYPROJECT_TOML" && git diff --staged --quiet "$PYPROJECT_TOML"; then
                 # This case should not happen if sed worked and version changed, but good to check.
                echo "   🤔 $PYPROJECT_TOML was supposed to be modified but no changes detected by Git. Staging anyway."
            fi
            git add "$PYPROJECT_TOML"
            echo "   ➕ Staged $PYPROJECT_TOML."
        else
            echo "   ℹ️  $PYPROJECT_TOML was not modified (version not incremented). No specific Git add for it."
        fi
        
        # Check for other unstaged changes
        if ! git diff --quiet || ! git diff --staged --quiet; then
            echo "   ⚠️ You have other uncommitted changes. Please review them."
            git status -s # Show short status
            if ! prompt_yes_no "   ❓ Do you want to proceed with commit including these changes?"; then
                echo "   🛑 Aborting Git operations due to uncommitted changes."
                echo "----------------------------------------------------"
                echo "Build and upload steps can still proceed if you choose."
                goto_build=true # Flag to jump past Git push logic
            fi
        fi

        if [ -z "$goto_build" ]; then # Only if not aborting due to uncommitted changes
            commit_default_message="Release version $new_version"
            if [[ "$new_version" == "$current_version" ]]; then
                commit_default_message="Build version $new_version" # Or some other message for re-release
            fi

            read -r -p "   💬 Enter commit message (default: '$commit_default_message'): " commit_message
            commit_message=${commit_message:-"$commit_default_message"}
            
            git commit -m "$commit_message"
            echo "   ✅ Changes committed."

            if prompt_yes_no "   🏷  Tag this release as v$new_version?"; then
                git tag "v$new_version"
                echo "   ✅ Tagged as v$new_version."
            else
                echo "   Skipped tagging."
            fi
            
            if prompt_yes_no "   ⏫ Push changes and tags to remote?"; then
                git push
                if git rev-parse -q --verify "v$new_version" >/dev/null; then # Check if tag exists locally
                   git push --tags
                else
                   echo "   Skipped pushing tags as v$new_version was not created."
                fi
                echo "   ✅ Pushed to remote."
            else
                echo "   Skipped pushing to remote. Remember to push manually if needed."
            fi
        fi
    else
        echo "   Skipping Git operations."
    fi
else
    echo "⚠️ Git not found or not in a git repository. Skipping Git operations."
fi
unset goto_build # Clear the flag
echo "----------------------------------------------------"

# 4. Build the package
if prompt_yes_no "📦 Would you like to build the package for version $new_version?"; then
    echo "   Building the package..."
    python -m build
    echo "   ✅ Package built."
    
    # 5. Upload to PyPI
    echo "   ------------------------------------------------"
    echo "   ⬆️  Files to be uploaded from dist/:"
    ls -l dist/
    echo "   ------------------------------------------------"

    if prompt_yes_no "🚀 Would you like to upload version $new_version to LIVE PyPI?"; then
        echo "   Uploading to PyPI..."
        python -m twine upload dist/*
        echo "   🎉 Successfully uploaded version $new_version to PyPI!"
    else
        echo "   🛑 Upload aborted by user."
        echo "      You can manually upload later using: python -m twine upload dist/*"
    fi
else
    echo "   Skipping build and upload."
    echo "   No package was built or uploaded."
fi

echo "----------------------------------------------------"
echo "✅ Process finished! ✨"