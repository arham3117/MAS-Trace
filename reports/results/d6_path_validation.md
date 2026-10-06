# D6 validation: anchor-based vs replay-based true paths (scripted Stage 3)

- Runs: 20; (run, path) pairs: 35; compared: 35; inseparable: 0
- **Agreement with replay necessity (answers.md D6 rule): 20/35 = 57%** (threshold 90%)
- Agreement with replay sufficiency (alternative, for information): 35/35 = 100%

Necessity: dropping this path's distinguishing edge removes the symptom. Sufficiency: with every other path's distinguishing edge dropped, the symptom still occurs.

| Run | Path | Anchor-true | Necessary (replay) | Agree | Sufficient (replay) |
|---|---|---|---|---|---|
| s3_mixed_two_paths-t01-g1s0-scripted_gullible-s1 | A→B→C→E | True | False | **no** | True |
| s3_mixed_two_paths-t01-g1s0-scripted_gullible-s1 | A→B→D→E | True | False | **no** | True |
| s3_mixed_two_paths-t02-g1s0-scripted_gullible-s1 | A→B→C→E | True | False | **no** | True |
| s3_mixed_two_paths-t02-g1s0-scripted_gullible-s1 | A→B→D→E | True | False | **no** | True |
| s3_mixed_two_paths-t03-g1s0-scripted_gullible-s1 | A→B→C→E | True | False | **no** | True |
| s3_mixed_two_paths-t03-g1s0-scripted_gullible-s1 | A→B→D→E | True | False | **no** | True |
| s3_mixed_two_paths-t04-g1s0-scripted_gullible-s1 | A→B→C→E | True | False | **no** | True |
| s3_mixed_two_paths-t04-g1s0-scripted_gullible-s1 | A→B→D→E | True | False | **no** | True |
| s3_mixed_two_paths-t05-g1s0-scripted_gullible-s1 | A→B→C→E | True | False | **no** | True |
| s3_mixed_two_paths-t05-g1s0-scripted_gullible-s1 | A→B→D→E | True | False | **no** | True |
| s3_mixed_two_paths-t06-g1s0-scripted_gullible-s1 [C resistant] | A→B→C→E | False | False | yes | False |
| s3_mixed_two_paths-t06-g1s0-scripted_gullible-s1 [C resistant] | A→B→D→E | True | True | yes | True |
| s3_mixed_two_paths-t07-g1s0-scripted_gullible-s1 [C resistant] | A→B→C→E | False | False | yes | False |
| s3_mixed_two_paths-t07-g1s0-scripted_gullible-s1 [C resistant] | A→B→D→E | True | True | yes | True |
| s3_mixed_two_paths-t08-g1s0-scripted_gullible-s1 [C resistant] | A→B→C→E | False | False | yes | False |
| s3_mixed_two_paths-t08-g1s0-scripted_gullible-s1 [C resistant] | A→B→D→E | True | True | yes | True |
| s3_mixed_two_paths-t09-g1s0-scripted_gullible-s1 [C resistant] | A→B→C→E | False | False | yes | False |
| s3_mixed_two_paths-t09-g1s0-scripted_gullible-s1 [C resistant] | A→B→D→E | True | True | yes | True |
| s3_mixed_two_paths-t10-g1s0-scripted_gullible-s1 [C resistant] | A→B→C→E | False | False | yes | False |
| s3_mixed_two_paths-t10-g1s0-scripted_gullible-s1 [C resistant] | A→B→D→E | True | True | yes | True |
| s3_whiteboard-t01-g1s0-scripted_gullible-s1 | A→C→E | True | False | **no** | True |
| s3_whiteboard-t02-g1s0-scripted_gullible-s1 | A→C→E | True | False | **no** | True |
| s3_whiteboard-t03-g1s0-scripted_gullible-s1 | A→C→E | True | False | **no** | True |
| s3_whiteboard-t04-g1s0-scripted_gullible-s1 | A→C→E | True | False | **no** | True |
| s3_whiteboard-t05-g1s0-scripted_gullible-s1 | A→C→E | True | False | **no** | True |
| s3_whiteboard-t06-g1s0-scripted_gullible-s1 [C resistant] | A→B→D→E | True | True | yes | True |
| s3_whiteboard-t06-g1s0-scripted_gullible-s1 [C resistant] | A→C→E | False | False | yes | False |
| s3_whiteboard-t07-g1s0-scripted_gullible-s1 [C resistant] | A→B→D→E | True | True | yes | True |
| s3_whiteboard-t07-g1s0-scripted_gullible-s1 [C resistant] | A→C→E | False | False | yes | False |
| s3_whiteboard-t08-g1s0-scripted_gullible-s1 [C resistant] | A→B→D→E | True | True | yes | True |
| s3_whiteboard-t08-g1s0-scripted_gullible-s1 [C resistant] | A→C→E | False | False | yes | False |
| s3_whiteboard-t09-g1s0-scripted_gullible-s1 [C resistant] | A→B→D→E | True | True | yes | True |
| s3_whiteboard-t09-g1s0-scripted_gullible-s1 [C resistant] | A→C→E | False | False | yes | False |
| s3_whiteboard-t10-g1s0-scripted_gullible-s1 [C resistant] | A→B→D→E | True | True | yes | True |
| s3_whiteboard-t10-g1s0-scripted_gullible-s1 [C resistant] | A→C→E | False | False | yes | False |
