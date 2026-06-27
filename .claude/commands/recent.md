# /recent

List the most recently stored sessions.

## Usage

```
/recent [N]
```

Default: 10.

## Steps

1. Query `~/.agent-memory/database.sqlite` for the N most recent sessions ordered by `started_at` DESC.
2. Display as a numbered list with date, title, repository, branch, duration, and session ID.
3. Offer to search or read any listed session.

## Example output

```
Recent sessions (10 most recent):

 1. [2026-06-23 09:15]  "Add rate limiting to API"
    github.com/acme/backend  feat/rate-limit  (45 min)  sess_01XYZ

 2. [2026-06-22 16:40]  "Refactor auth middleware"
    github.com/acme/backend  refactor/auth    (22 min)  sess_01WXY

 3. [2026-06-20 14:32]  "Fix race condition in payment processor"
    github.com/acme/backend  fix/race         (29 min)  sess_01VWX

...

To read a session: /read <session_id>
To search:         /search <query>
```
