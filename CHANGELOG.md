# Changelog

## 0.3.1

- Added portable JSON export and import for personal settings, keyword rules, and known-user customizations.
- Added merge and replace modes when importing a settings backup.
- Added automatic GitHub release checks at startup and an on-demand **Check for Updates** action.
- Added platform- and architecture-aware release asset selection, update download prompts, and a clickable Releases-page fallback.
- Added native TapestriesMuck application naming and custom Windows, macOS, and Linux icons.
- Added a styled macOS Apple Silicon DMG with a drag-to-Applications layout.
- Corrected the Finder icon alignment in the macOS installer artwork.
- Added automated tests for backup round trips, merge behavior, version comparison, and update asset selection.

## 0.2.2

- Limit the command input bar to 1000 characters to avoid server-side truncation of long messages.

## 0.2.1

- Recognize received `page-pose to you` messages as received pages for highlighting.
- Added a parser regression test for received page-pose output.

## 0.2.0

- Initial compiled release with PySide6 desktop UI, SSL connection support, highlighting rules, command history, Tab completion, clickable URLs, and SQLite persistence.
