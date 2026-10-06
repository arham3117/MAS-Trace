# D6 / ISSUE-025: carried, sufficient and necessary path labels (scripted Stage 3)

- Runs: 20; (run, path) pairs: 35
- **Validation, carried vs sufficient: 35/35 = 100%** (bar 90%, ISSUE-025)
- For information, carried vs necessary: 20/35 (not a valid reference under redundancy)
- Overdetermined runs (≥ 2 sufficient paths, none necessary): 5/20

| Run | Path | Carried | Sufficient | Necessary | Responsibility | Agree |
|---|---|---|---|---|---|---|
| s3_mixed_two_paths-t01-g1s0-scripted_gullible-s1 | A→B→C→E | True | True | False | 0.50 | yes |
| s3_mixed_two_paths-t01-g1s0-scripted_gullible-s1 | A→B→D→E | True | True | False | 0.50 | yes |
| s3_mixed_two_paths-t02-g1s0-scripted_gullible-s1 | A→B→C→E | True | True | False | 0.50 | yes |
| s3_mixed_two_paths-t02-g1s0-scripted_gullible-s1 | A→B→D→E | True | True | False | 0.50 | yes |
| s3_mixed_two_paths-t03-g1s0-scripted_gullible-s1 | A→B→C→E | True | True | False | 0.50 | yes |
| s3_mixed_two_paths-t03-g1s0-scripted_gullible-s1 | A→B→D→E | True | True | False | 0.50 | yes |
| s3_mixed_two_paths-t04-g1s0-scripted_gullible-s1 | A→B→C→E | True | True | False | 0.50 | yes |
| s3_mixed_two_paths-t04-g1s0-scripted_gullible-s1 | A→B→D→E | True | True | False | 0.50 | yes |
| s3_mixed_two_paths-t05-g1s0-scripted_gullible-s1 | A→B→C→E | True | True | False | 0.50 | yes |
| s3_mixed_two_paths-t05-g1s0-scripted_gullible-s1 | A→B→D→E | True | True | False | 0.50 | yes |
| s3_mixed_two_paths-t06-g1s0-scripted_gullible-s1 [C resistant] | A→B→C→E | False | False | False | 0 | yes |
| s3_mixed_two_paths-t06-g1s0-scripted_gullible-s1 [C resistant] | A→B→D→E | True | True | True | 1.00 | yes |
| s3_mixed_two_paths-t07-g1s0-scripted_gullible-s1 [C resistant] | A→B→C→E | False | False | False | 0 | yes |
| s3_mixed_two_paths-t07-g1s0-scripted_gullible-s1 [C resistant] | A→B→D→E | True | True | True | 1.00 | yes |
| s3_mixed_two_paths-t08-g1s0-scripted_gullible-s1 [C resistant] | A→B→C→E | False | False | False | 0 | yes |
| s3_mixed_two_paths-t08-g1s0-scripted_gullible-s1 [C resistant] | A→B→D→E | True | True | True | 1.00 | yes |
| s3_mixed_two_paths-t09-g1s0-scripted_gullible-s1 [C resistant] | A→B→C→E | False | False | False | 0 | yes |
| s3_mixed_two_paths-t09-g1s0-scripted_gullible-s1 [C resistant] | A→B→D→E | True | True | True | 1.00 | yes |
| s3_mixed_two_paths-t10-g1s0-scripted_gullible-s1 [C resistant] | A→B→C→E | False | False | False | 0 | yes |
| s3_mixed_two_paths-t10-g1s0-scripted_gullible-s1 [C resistant] | A→B→D→E | True | True | True | 1.00 | yes |
| s3_whiteboard-t01-g1s0-scripted_gullible-s1 | A→C→E | True | True | False | 1.00 | yes |
| s3_whiteboard-t02-g1s0-scripted_gullible-s1 | A→C→E | True | True | False | 1.00 | yes |
| s3_whiteboard-t03-g1s0-scripted_gullible-s1 | A→C→E | True | True | False | 1.00 | yes |
| s3_whiteboard-t04-g1s0-scripted_gullible-s1 | A→C→E | True | True | False | 1.00 | yes |
| s3_whiteboard-t05-g1s0-scripted_gullible-s1 | A→C→E | True | True | False | 1.00 | yes |
| s3_whiteboard-t06-g1s0-scripted_gullible-s1 [C resistant] | A→B→D→E | True | True | True | 1.00 | yes |
| s3_whiteboard-t06-g1s0-scripted_gullible-s1 [C resistant] | A→C→E | False | False | False | 0 | yes |
| s3_whiteboard-t07-g1s0-scripted_gullible-s1 [C resistant] | A→B→D→E | True | True | True | 1.00 | yes |
| s3_whiteboard-t07-g1s0-scripted_gullible-s1 [C resistant] | A→C→E | False | False | False | 0 | yes |
| s3_whiteboard-t08-g1s0-scripted_gullible-s1 [C resistant] | A→B→D→E | True | True | True | 1.00 | yes |
| s3_whiteboard-t08-g1s0-scripted_gullible-s1 [C resistant] | A→C→E | False | False | False | 0 | yes |
| s3_whiteboard-t09-g1s0-scripted_gullible-s1 [C resistant] | A→B→D→E | True | True | True | 1.00 | yes |
| s3_whiteboard-t09-g1s0-scripted_gullible-s1 [C resistant] | A→C→E | False | False | False | 0 | yes |
| s3_whiteboard-t10-g1s0-scripted_gullible-s1 [C resistant] | A→B→D→E | True | True | True | 1.00 | yes |
| s3_whiteboard-t10-g1s0-scripted_gullible-s1 [C resistant] | A→C→E | False | False | False | 0 | yes |

## Tracer path marks vs the labels

- Mean agreement of tracer marks with **carried** (necessary/redundant = causal): 100% over 20 runs
- Mean agreement of tracer marks with **necessary**: 100% over 20 runs

| Run | Tracer marks | vs carried | vs necessary | Overdetermined |
|---|---|---|---|---|
| s3_mixed_two_paths-t01-g1s0-scripted_gullible-s1 | A→B→C→E: redundant, A→B→D→E: redundant | 1.0 | 1.0 | True |
| s3_mixed_two_paths-t02-g1s0-scripted_gullible-s1 | A→B→C→E: redundant, A→B→D→E: redundant | 1.0 | 1.0 | True |
| s3_mixed_two_paths-t03-g1s0-scripted_gullible-s1 | A→B→C→E: redundant, A→B→D→E: redundant | 1.0 | 1.0 | True |
| s3_mixed_two_paths-t04-g1s0-scripted_gullible-s1 | A→B→C→E: redundant, A→B→D→E: redundant | 1.0 | 1.0 | True |
| s3_mixed_two_paths-t05-g1s0-scripted_gullible-s1 | A→B→C→E: redundant, A→B→D→E: redundant | 1.0 | 1.0 | True |
| s3_mixed_two_paths-t06-g1s0-scripted_gullible-s1 [C resistant] | A→B→C→E: non_causal, A→B→D→E: necessary | 1.0 | 1.0 | False |
| s3_mixed_two_paths-t07-g1s0-scripted_gullible-s1 [C resistant] | A→B→C→E: non_causal, A→B→D→E: necessary | 1.0 | 1.0 | False |
| s3_mixed_two_paths-t08-g1s0-scripted_gullible-s1 [C resistant] | A→B→C→E: non_causal, A→B→D→E: necessary | 1.0 | 1.0 | False |
| s3_mixed_two_paths-t09-g1s0-scripted_gullible-s1 [C resistant] | A→B→C→E: non_causal, A→B→D→E: necessary | 1.0 | 1.0 | False |
| s3_mixed_two_paths-t10-g1s0-scripted_gullible-s1 [C resistant] | A→B→C→E: non_causal, A→B→D→E: necessary | 1.0 | 1.0 | False |
| s3_whiteboard-t01-g1s0-scripted_gullible-s1 | A→C→E: redundant | 1.0 | 1.0 | False |
| s3_whiteboard-t02-g1s0-scripted_gullible-s1 | A→C→E: redundant | 1.0 | 1.0 | False |
| s3_whiteboard-t03-g1s0-scripted_gullible-s1 | A→C→E: redundant | 1.0 | 1.0 | False |
| s3_whiteboard-t04-g1s0-scripted_gullible-s1 | A→C→E: redundant | 1.0 | 1.0 | False |
| s3_whiteboard-t05-g1s0-scripted_gullible-s1 | A→C→E: redundant | 1.0 | 1.0 | False |
| s3_whiteboard-t06-g1s0-scripted_gullible-s1 [C resistant] | A→B→D→E: necessary, A→C→E: non_causal | 1.0 | 1.0 | False |
| s3_whiteboard-t07-g1s0-scripted_gullible-s1 [C resistant] | A→B→D→E: necessary, A→C→E: non_causal | 1.0 | 1.0 | False |
| s3_whiteboard-t08-g1s0-scripted_gullible-s1 [C resistant] | A→B→D→E: necessary, A→C→E: non_causal | 1.0 | 1.0 | False |
| s3_whiteboard-t09-g1s0-scripted_gullible-s1 [C resistant] | A→B→D→E: necessary, A→C→E: non_causal | 1.0 | 1.0 | False |
| s3_whiteboard-t10-g1s0-scripted_gullible-s1 [C resistant] | A→B→D→E: necessary, A→C→E: non_causal | 1.0 | 1.0 | False |
