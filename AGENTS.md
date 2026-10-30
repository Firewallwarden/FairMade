
# FairMade - AI Agent Instructions

FairMade is an AI-powered marketplace and business
intelligence platform for independent sellers and buyers.

## Repository Structure

- backend/ - Python backend application
- frontend/ - Web frontend application
- docs/ - Project documentation
- scripts/ - Development utilities

## Development Guidelines

- Maintain clear separation between frontend and backend.
- Work on the backend only unless the user explicitly changes the scope.
- Expose backend functionality through APIs for the frontend developer to
  integrate. Keep API contracts and integration documentation clear; do not
  implement frontend interfaces or interactions.
- Do not introduce paid APIs or services without approval.
- Do not commit credentials, API keys, or secrets.
- Do not make major architectural changes without approval.
- Keep code modular, maintainable, and testable.
- Prefer incremental changes over large rewrites.
- Do not push changes to GitHub without approval.

## Git Worktree and Pull Request Workflow

- Use the main worktree only for `git fetch` and `git pull`. Do not edit files,
  implement features, or create commits in the main worktree.
- Create a separate branch and worktree outside the main worktree for each
  issue or feature, including documentation and repository instruction changes.
- Before starting work, fetch the latest remote changes and create the worktree
  from `origin/main`. For an existing issue or feature worktree, rebase its
  branch onto the latest `origin/main` before continuing.
- Complete and validate changes in the issue or feature worktree, then commit,
  push the branch when authorized, and open a pull request for review and merge.
- After rebasing an already-published issue or feature branch, update it with
  `git push --force-with-lease`. Never force-push `main`.
- Prefer squash merges to keep main history clean. Leave pull requests for
  review; do not merge without explicit authorization.
