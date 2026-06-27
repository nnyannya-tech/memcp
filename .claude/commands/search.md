# /search

Search past sessions in Agent Memory using natural language.

## Usage

```
/search <query> [--limit N]
```

Default limit: 5.

## Steps

1. Run SQLite FTS against messages, tool calls, and repository metadata using the provided query.
2. Rank results by recency (most recent first within the same relevance tier).
3. Display each matching session as a summary card.
4. Offer to call `read_session` on any result for the full transcript.

## Example output

```
Found 3 sessions matching "JWT authentication":

1. [2026-06-20] "Add JWT middleware to API gateway"   (sess_01ABC)
   Repository: github.com/acme/backend  branch: feat/auth
   Snippet: "...using RS256 signing, refresh token stored in httpOnly cookie..."

2. [2026-06-15] "Debug token expiry issue"            (sess_01DEF)
   Repository: github.com/acme/backend  branch: fix/token-exp
   Snippet: "...leankTime mismatch between issuer and verifier clocks..."

3. [2026-06-10] "Spike: evaluate JWT vs session cookies" (sess_01GHI)
   Repository: github.com/acme/backend  branch: spike/auth
   Snippet: "...stateless preferred for horizontal scaling..."

To read full transcript: /read <session_id>
```
