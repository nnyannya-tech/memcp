# /read

Display the full transcript of a stored session.

## Usage

```
/read <session_id>
```

## Steps

1. Fetch the session record from `~/.agent-memory/database.sqlite` by `session_id`.
2. Load all Messages and ToolCalls in chronological order.
3. Render as a readable transcript: role labels (User / Assistant / Tool), timestamps, and content.
4. For ToolCalls, show tool name, arguments summary, and result summary (truncate long results to 200 chars).

## Example output

```
Session: "Fix race condition in payment processor"
Repository: github.com/acme/backend  branch: fix/race-condition
Date: 2026-06-20 14:32 – 15:01 (29 min)
────────────────────────────────────────

[14:32] User
  The payment processor is intermittently double-charging. Suspected race condition.

[14:33] Assistant
  Let me look at the locking strategy in the charge handler...

[14:33] Tool: read_file  src/payments/charge.py
  Result: [file content shown]

...
```
