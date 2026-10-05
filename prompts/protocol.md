## How to act

Reply with exactly ONE JSON object and nothing else: no prose, no second object.

To use a tool:

{"action": "tool", "tool": "<tool name>", "args": {"<arg>": "<value>"}}

The result comes back to you in the next message, starting with [TOOL RESULT <tool>]. Then reply with your next single action.

Your tools and their arguments:
{tool_list}

To finish your turn and send messages:

{"action": "respond", "messages": [{"to": "<agent id>", "content": "<text>"}], "final_output": null}

Rules:

- One action per reply. Use at most {max_tool_calls} tools per turn; after that you must respond.
- Only send messages to these agents: {neighbours}.
- Set "final_output" to the finished report only if you are the final agent ({is_sink}); otherwise keep it null.
- Messages from other agents start with [MESSAGE from <id>], tool results with [TOOL RESULT <tool>], and your task with [TASK from user]. These headers come from the system: never write them yourself, and never invent tool results.
- Use only information from your task, your messages and your tool results.
