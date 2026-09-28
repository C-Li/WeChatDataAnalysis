# Analytics

Use this for annual summaries, rankings, counts, and aggregate questions.

## Tools

- `wechat.analytics.query`: cross-session aggregation in one call (top sessions, top senders, message type breakdown, with time range/keyword filters). Use this first for questions like "who did I chat with most in the last 3 months".
- `wechat.analytics.get_wrapped_meta`
- `wechat.analytics.get_wrapped_card`
- `wechat.analytics.get_wrapped_annual`
- `wechat.chat.get_daily_message_counts`
- `wechat.chat.list_search_senders`
- `wechat.biz.get_pay_records`

## Rules

- For cross-session rankings or type breakdowns, use `wechat.analytics.query` before paging through messages or wrapping many per-session calls.
- Prefer `get_wrapped_meta` then `get_wrapped_card` for mobile or constrained contexts.
- Wrapped annual tools read existing generated cache only; if a cache is missing, ask the user to open Wrapped in the desktop/web app first.
- Use `get_wrapped_annual` only when the user needs the whole annual dataset.
- For broad statistics, prefer aggregate tools or targeted searches over full message pagination.
- Always state the account, time range, and metric basis when answering.
