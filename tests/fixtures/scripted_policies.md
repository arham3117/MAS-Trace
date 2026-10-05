# ScriptedProvider policies

This file describes the deterministic stand-in model in `mastrace/mediation/providers/scripted.py`.
It implements plan.md §7.13, and `tests/unit/test_scripted_provider.py` pins its behaviour.

## Inputs it reads

The provider is stateless. Everything comes from the request's messages, using the text
contract in `mastrace/core/protocol.py`:

- **System prompt.** Ends with a `## Agent profile` block that gives the agent ID, role,
  out-neighbours, two-way neighbours, tools, sink flag and allowed recipients.
- **User items.** Each starts with a header: `[TASK from user]`, `[MESSAGE from <agent>]`,
  `[TOOL RESULT <tool>]` or `[NOTE]`. A task lists its URLs on `SOURCE: <url>` lines.
- **Assistant items.** The agent's own earlier JSON actions.

The **current turn** is everything after the agent's last `respond` action.

## Content units

A **unit** is one of two things:

- a `FACT:` line, or
- an **instruction paragraph**: a blank-line-separated paragraph that is not only
  `FACT:`/`FEEDBACK:` lines and that either matches `SCRIPTED_INSTRUCTION_PATTERNS` or
  contains an email address that is not an allowed recipient.

`gullible` agents handle both kinds of unit. `resistant` agents handle `FACT:` lines only.

## Role behaviour

| Role | Behaviour |
| --- | --- |
| `researcher`, `researcher_2` (turn with a task) | `web_fetch` each `SOURCE:` URL, one per call. Then respond to every out-neighbour with the units from the fetched pages. |
| `analyst`, `planner` | Forward the units received this turn to every out-neighbour except the sender. |
| `writer` | Same as the analyst, with `# Report` as the first block of each message. |
| `operator` (sink) | If the turn brings new units: (gullible only) for the first instruction paragraph that names `…credentials.txt` and a non-allowed address, `read_file` that path, then `send_email` its content to that address; then `send_email` the report to each allowed recipient; then respond with `final_output` = report. |

The **report** is `# Report`, then every `FACT:` line received so far, then (gullible only)
every instruction paragraph received so far, verbatim.

## Message rules

- **Forwarding.** Content never goes back to the agent it came from. A given unit is sent to
  a given neighbour at most once per run, so meshes cannot echo forever.
- **Feedback.** On a two-way link, an agent that receives a message from `S` replies
  `FEEDBACK: received (<round>)` to `S`, while `round ≤ feedback_rounds` (default 1).
  A feedback-only inbox therefore gets either one more feedback reply or nothing.
- **Message layout.** A message has an optional heading, then the `FACT:` lines (one block),
  then each instruction paragraph, then an optional `FEEDBACK:` line. Blocks are separated
  by blank lines.
- **Forced response.** If a `[NOTE]` says "You must respond now.", the agent responds instead
  of calling a tool.
- **Per-agent policy.** `policy_overrides={"C": "resistant"}` changes the policy of one agent
  only (used in P11.1).
