
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
- Follow the standing authorization and approval requirements in the Git
  workflow below when publishing changes to GitHub.

## Git Worktree and Pull Request Workflow

- Require a separate feature branch and dedicated Git worktree outside the
  primary worktree for every issue or feature, including documentation and
  repository instruction changes.
- Reserve the primary worktree for maintaining the local `main` branch. Update
  `main` using `git pull --ff-only` to ensure it remains aligned with
  `origin/main` without introducing merge commits or rewriting local history.
- Perform all development, commits, testing, and rebasing within the
  corresponding feature worktree.
- Standing approval covers `git add`, `git commit`, normal `git push` to the
  corresponding feature or issue branch, and `gh pr create` / `gh pr edit`
  from its dedicated worktree, provided all changes and PR operations remain
  within the scope of the user's request. Automate these steps without asking
  for repeated approval.
- This authorization does not cover unrelated changes, direct pushes to
  `main`, merging pull requests, or rewriting remote branch history.
- Before opening or updating a pull request, run `git fetch origin` followed by
  `git rebase origin/main` from the feature worktree.
- If rebasing requires updating an already-published feature branch, use
  `git push --force-with-lease` only after explicit approval.
- Never force-push to `main`. All changes to `main` must go through reviewed
  pull requests, with squash merges preferred. Merging pull requests and
  rewriting remote branch history require explicit approval; pushes outside
  the standing authorization above also require explicit approval.
