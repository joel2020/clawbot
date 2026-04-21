# Contributing to Clawbot

## Commit Convention — Auto-close Linear & GitHub Issues

Every commit that ships a feature or fix should reference the relevant tickets.
GitHub will auto-close the linked issue when the commit lands on `main`.
Linear will auto-close the linked ticket when the GitHub issue closes (via the Linear ↔ GitHub integration below).

### Format

```
<type>: <short description>

<body>

Closes #<github-issue-number>
```

### Examples

```
feat: connect n8n HTTP Request node to control API

Added credential, tested webhook → POST /runs round-trip.

Closes #1
```

```
fix: suppress pydantic model_ namespace warnings in control-api

Closes #2
```

### Type prefixes
| Prefix | Use |
|--------|-----|
| `feat` | New feature |
| `fix`  | Bug fix |
| `chore`| Config / tooling / deps |
| `docs` | Documentation |
| `test` | Tests |

## Linear ↔ GitHub Auto-sync Setup

To make GitHub commits auto-close Linear tickets (ALI-5, ALI-6, ALI-7):

1. Go to Linear → Settings → Integrations → GitHub
2. Connect the `joel2020/clawbot` repository
3. Enable **"Close issue on merged PR"** and **"Auto-close on commit to default branch"**
4. In commit messages, include `Closes ALI-5` (or ALI-6 / ALI-7) alongside `Closes #1`

Both the GitHub issue and the Linear ticket will close automatically on merge to main.

## Branch Naming
```
feat/ali-5-n8n-integration
fix/ali-6-pipeline-test
feat/ali-7-lead-intake
```
