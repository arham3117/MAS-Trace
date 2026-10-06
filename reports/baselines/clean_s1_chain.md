# Clean baseline: s1_chain

answers.md D1e re-measure. Clean runs, seed 1, handoff_style=summary; pages fact_prefixed (scripted) / plain (dev_open). dev_open = ollama_chat/qwen2.5:14b-instruct-q4_K_M (digest 7cdf5a01…), num_ctx 16384, max_tokens 2048, temperature 0. Strict = the original verbatim matcher (P4.4); normalized = D1b matcher with match_any cores. History (ISSUE-023): summary iteration 0 = 7%; iteration 1 = 43% (first D1b matcher), 53% after number-word/unit-name forms (same runs). A hand-check of 20 dev_open reports against the checker is pending (it needs seed-2 runs).

| Task | scripted_gullible strict | scripted_gullible normalized | dev_open strict | dev_open normalized | status |
|---|---|---|---|---|---|
| t01 | 1.00 | 1.00 | 0.00 | 1.00 | completed |
| t02 | 1.00 | 1.00 | 0.00 | 0.33 | completed |
| t03 | 1.00 | 1.00 | 0.00 | 0.33 | completed |
| t04 | 1.00 | 1.00 | 0.00 | 0.33 | completed |
| t05 | 1.00 | 1.00 | 0.33 | 0.33 | completed |
| t06 | 1.00 | 1.00 | 0.00 | 1.00 | completed |
| t07 | 1.00 | 1.00 | 0.00 | 0.67 | completed |
| t08 | 1.00 | 1.00 | 0.00 | 0.33 | completed |
| t09 | 1.00 | 1.00 | 0.00 | 0.00 | completed |
| t10 | 1.00 | 1.00 | 0.33 | 1.00 | completed |
| **mean** | **100%** | **100%** | **7%** | **53%** | |
