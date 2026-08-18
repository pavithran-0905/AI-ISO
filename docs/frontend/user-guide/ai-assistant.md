# AI Assistant

Where to ask AI-IOS questions, review what it found, and act on what it
recommends. Everything here is grounded in your platform's own data —
the assistant never invents an answer without saying where it came
from, and never changes anything without your explicit say-so.

## Intelligence Overview

Open **Intelligence** from the sidebar (or `/intelligence` directly).

- **Summary** — real usage, cost, and feedback statistics, with a
  clear "Computed" timestamp and a **Recompute** button since AI-IOS
  does not refresh these automatically.
- **Recent conversations** — your own most recent conversations with
  the assistant, click one to reopen it.
- **Pending recommendations** — recommendations the assistant has
  generated that haven't been accepted or rejected yet.
- **Memory** — facts the assistant has chosen to remember, read-only.

## AI Assistant (the conversation workspace)

Open **AI Assistant** from the tab bar, or `/intelligence/assistant`.
A conversation list on the left, the active conversation on the right.

- **New conversation** — starts fresh. You can optionally pick an
  agent (a specialization like "infrastructure" or "security") before
  your first message; once a conversation exists, every following
  message stays with it.
- **My conversations only** — on by default. Turn it off to see every
  conversation across your organization.
- Type your message and press **Enter** to send, or **Shift+Enter** for
  a new line within the same message.
- While the assistant is answering, the Send button shows it's busy.
  There's no partial answer that streams in as it's written — you see
  the whole response once it's ready (see Known limitations).
- If a send fails, your typed message stays in the box — just press
  Send again.

## Reading a response

- **Sources** — when the assistant's answer drew on ingested
  documentation, each source is listed underneath with a relevance
  percentage. No sources shown means the answer wasn't grounded in
  anything retrievable.
- **Helpful / Not helpful** — rate any assistant response. "Not
  helpful" lets you add an optional comment.
- **Tool activity** — if the assistant used a tool during the
  conversation, it's shown as its own section (Pending / Running /
  Succeeded / Failed / Denied), never mixed into the assistant's own
  words. AI-IOS never shows you the tool's raw internal input/output —
  only its outcome.
- If part of a response was filtered for safety, you'll see a plain
  notice saying so — AI-IOS doesn't expose the internal reason.

## Letting the assistant take action

Off by default. Turn on **"Allow this assistant to take actions that
change infrastructure"** below the message box before sending if you
want the assistant able to use tools that change something for that
message. It resets to off for your next message — there's no
"remember my choice."

## Knowledge

Open **Knowledge** from the tab bar, or `/intelligence/knowledge`.

- **Search preview** — try a real query to see what the assistant
  would find for it, with a strategy picker (vector / keyword /
  hybrid).
- **Documents** — everything ingested for retrieval so far.
- **Ingest a document** — add a document by pasting its text directly
  (title + source type + text). There's no file upload yet.

## Recommendations

Open **Recommendations** from the tab bar, or
`/intelligence/recommendations`. Generate one by picking a type and
describing the subject; **Accept**/**Reject** any recommendation
that's still awaiting a decision. Recommendations aren't shown in any
particular order — there's no "most recent" to sort by.

## AI Reports

Open **AI Reports** from the tab bar, or `/intelligence/reports`.
These are narrative reports the assistant writes — a different thing
from the Reporting module's own scheduled/templated reports. Generate
one by picking a type and a subject; every report is shown in full
(title, body, and sources) right in the list, sortable by when it was
generated.

## Analytics

Open **Analytics** from the tab bar, or `/intelligence/analytics`.
Usage, tokens, latency, feedback, and an estimated cost (a rough
figure — see Known limitations), plus a breakdown of which tools,
providers, and models were used. Press **Recompute** for fresh
numbers.

## Prompts

Open **Prompts** from the tab bar, or `/intelligence/prompts` — only
shown if your role has administrative access. These are the templates
the assistant's own agents draw on: create one, add new versions,
approve a version, roll back to an earlier approved one, or render a
version with real values to preview it.

## Asking AI from elsewhere

You'll see an **Ask AI** button on alert detail, automation detail,
report detail, asset detail, and the Dashboard itself. It opens a new
conversation with a message already typed in referencing what you were
looking at — nothing is sent until you press Send yourself.

## Troubleshooting

- **A section says "Access denied."** Your account doesn't have
  permission to view that specific data — contact your administrator.
- **A section shows an error with a Retry button.** That data is
  temporarily unavailable; the rest of the page keeps working
  normally.
- **I don't see the "allow actions" toggle, or generate/ingest
  buttons.** Your role doesn't currently allow that action.
- **I don't see the Prompts tab.** It's limited to administrative
  roles.
- **A message failed to send.** The message tells you why; your
  typed text is still there — just try again.

## Known limitations

- **No live, word-by-word streaming.** A response appears all at once
  once it's ready, not as it's generated.
- **No per-tool-call confirmation dialog.** The "allow actions" toggle
  applies to the whole message you're about to send, not a pop-up per
  action.
- **No document upload.** Knowledge ingestion is paste-in text only.
- **No memory delete.** The Memory list is read-only.
- **Estimated cost is directional, not a bill.** It's based on a
  built-in price table that doesn't cover every model.
- **The assistant that actually answered isn't shown after the fact.**
  You can pick an agent when starting a new conversation, but AI-IOS
  doesn't report back which one handled it.
