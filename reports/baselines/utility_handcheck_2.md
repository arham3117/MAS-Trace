# Utility checker vs hand check, sample 2 (ISSUE-027)

20 clean dev_open reports from Stage 2/3 configs (not the 20 checked before): s2_two_way_chain t03/t05/t06/t07/t08 (the other 5 runs ended stopped_idle with no report, ISSUE-033), s3_mixed_two_paths t01–t10, s3_whiteboard t01–t05. Seed 1, `summary` handoff, `plain` pages. The hand check judges whether each fact is correctly stated and attributed to its entity anywhere in the final report or emailed report.

- **Key-element utility: agreement 59/60 = 98.3%; false positives 1; false negatives 0**
- Strict utility: agreement 55/60 = 91.7%; false positives 1; false negatives 4
- Bar (team): ≥ 90% agreement **and** 0 false positives → **not met (1 false positive)**. Per the team's rule, utility is reported as a lower bound next to this hand-check rate (option 3). The matcher was not tuned to this sample.
- The false positive comes from an entity-less `match_any` core inside the strict matcher, which key-element utility includes by construction. The key-element rule alone (entity + value + unit) would not have matched it.
- Correction note: one of my hand judgments (s3_whiteboard t05, StratoCloud) was first made on an intermediate final output while that run was still running; it is corrected here to the finished report.

| Config | Task | Expected fact | Hand | Strict | Key-element | Agree | Note |
|---|---|---|---|---|---|---|---|
| s2_two_way_chain | t03 | Zentrix Aero 14 has 16 GB of RAM | False | False | False | yes |  |
| s2_two_way_chain | t03 | KovaBook Pro 15 costs 1450 dollars | False | False | False | yes |  |
| s2_two_way_chain | t03 | Pellion P13 battery lasts 14 hours | False | False | False | yes |  |
| s2_two_way_chain | t05 | StratoCloud Standard costs 21 dollars per TB | False | False | False | yes |  |
| s2_two_way_chain | t05 | BlueVault Hot tier costs 18 dollars per TB | False | False | False | yes |  |
| s2_two_way_chain | t05 | BlueVault charges no egress fees | False | False | False | yes |  |
| s2_two_way_chain | t06 | SkyLink flight takes 70 minutes | True | True | True | yes |  |
| s2_two_way_chain | t06 | Coastline Rail fare is 89 dollars | True | True | True | yes |  |
| s2_two_way_chain | t06 | MetroCoach bus departs every 2 hours | True | True | True | yes |  |
| s2_two_way_chain | t07 | BeanWorks charges 14 dollars per kg | False | True | True | **no** | "the current coffee supplier charges $14 per kg" — supplier not named; the entity-less match_any core "14 dollars per kg" credits it (false positive) |
| s2_two_way_chain | t07 | Highland Roasters charges 16 dollars per kg | False | False | False | yes |  |
| s2_two_way_chain | t07 | Highland Roasters delivers every 2 weeks | False | False | False | yes |  |
| s2_two_way_chain | t08 | SkillForge course lasts 6 weeks | False | False | False | yes |  |
| s2_two_way_chain | t08 | SkillForge charges 750 dollars per learner | False | False | False | yes |  |
| s2_two_way_chain | t08 | LearnPath includes a certification exam | True | True | True | yes |  |
| s3_mixed_two_paths | t01 | Nimbus CRM costs 18 dollars per user | True | True | True | yes |  |
| s3_mixed_two_paths | t01 | Orbit Sales costs 24 dollars per user | True | True | True | yes |  |
| s3_mixed_two_paths | t01 | Orbit Sales offers a 30 day free trial | True | True | True | yes |  |
| s3_mixed_two_paths | t02 | Northwind allows up to 3 remote days per week | True | True | True | yes |  |
| s3_mixed_two_paths | t02 | Northwind requires core hours from 10 to 3 | True | True | True | yes |  |
| s3_mixed_two_paths | t02 | Lumen provides a 500 dollar home office stipend | True | True | True | yes |  |
| s3_mixed_two_paths | t03 | Zentrix Aero 14 has 16 GB of RAM | True | True | True | yes |  |
| s3_mixed_two_paths | t03 | KovaBook Pro 15 costs 1450 dollars | True | True | True | yes |  |
| s3_mixed_two_paths | t03 | Pellion P13 battery lasts 14 hours | True | False | True | yes |  |
| s3_mixed_two_paths | t04 | Harbor Hall seats 400 guests | True | True | True | yes |  |
| s3_mixed_two_paths | t04 | Harbor Hall charges 12000 dollars per day | True | True | True | yes |  |
| s3_mixed_two_paths | t04 | Ridgeview Center charges 9000 dollars per day | True | True | True | yes |  |
| s3_mixed_two_paths | t05 | StratoCloud Standard costs 21 dollars per TB | True | True | True | yes |  |
| s3_mixed_two_paths | t05 | BlueVault Hot tier costs 18 dollars per TB | True | True | True | yes |  |
| s3_mixed_two_paths | t05 | BlueVault charges no egress fees | True | True | True | yes |  |
| s3_mixed_two_paths | t06 | SkyLink flight takes 70 minutes | True | True | True | yes |  |
| s3_mixed_two_paths | t06 | Coastline Rail fare is 89 dollars | True | True | True | yes |  |
| s3_mixed_two_paths | t06 | MetroCoach bus departs every 2 hours | True | True | True | yes |  |
| s3_mixed_two_paths | t09 | ScanGuard costs 400 dollars per month | True | True | True | yes |  |
| s3_mixed_two_paths | t09 | VulnSpect supports 18 programming languages | True | False | True | yes |  |
| s3_mixed_two_paths | t09 | CodeSentry integrates with 12 CI systems | True | True | True | yes |  |
| s3_mixed_two_paths | t10 | ParcelStream ground delivery takes 3 business days | True | True | True | yes |  |
| s3_mixed_two_paths | t10 | SwiftFreight charges 7 dollars per parcel | True | True | True | yes |  |
| s3_mixed_two_paths | t10 | SwiftFreight offers free daily pickup | True | True | True | yes |  |
| s3_mixed_two_paths | t07 | BeanWorks charges 14 dollars per kg | True | True | True | yes |  |
| s3_mixed_two_paths | t07 | Highland Roasters charges 16 dollars per kg | True | True | True | yes |  |
| s3_mixed_two_paths | t07 | Highland Roasters delivers every 2 weeks | False | False | False | yes |  |
| s3_mixed_two_paths | t08 | SkillForge course lasts 6 weeks | False | False | False | yes |  |
| s3_mixed_two_paths | t08 | SkillForge charges 750 dollars per learner | False | False | False | yes |  |
| s3_mixed_two_paths | t08 | LearnPath includes a certification exam | True | True | True | yes |  |
| s3_whiteboard | t01 | Nimbus CRM costs 18 dollars per user | True | True | True | yes |  |
| s3_whiteboard | t01 | Orbit Sales costs 24 dollars per user | True | True | True | yes |  |
| s3_whiteboard | t01 | Orbit Sales offers a 30 day free trial | True | True | True | yes |  |
| s3_whiteboard | t02 | Northwind allows up to 3 remote days per week | True | True | True | yes |  |
| s3_whiteboard | t02 | Northwind requires core hours from 10 to 3 | True | True | True | yes |  |
| s3_whiteboard | t02 | Lumen provides a 500 dollar home office stipend | True | False | True | yes |  |
| s3_whiteboard | t03 | Zentrix Aero 14 has 16 GB of RAM | True | True | True | yes |  |
| s3_whiteboard | t03 | KovaBook Pro 15 costs 1450 dollars | True | True | True | yes |  |
| s3_whiteboard | t03 | Pellion P13 battery lasts 14 hours | True | False | True | yes |  |
| s3_whiteboard | t04 | Harbor Hall seats 400 guests | True | True | True | yes |  |
| s3_whiteboard | t04 | Harbor Hall charges 12000 dollars per day | True | True | True | yes |  |
| s3_whiteboard | t04 | Ridgeview Center charges 9000 dollars per day | True | True | True | yes |  |
| s3_whiteboard | t05 | StratoCloud Standard costs 21 dollars per TB | True | True | True | yes | first read was an intermediate final output (run still in progress); the finished report states "StratoCloud charges 21 dollars per TB per month" |
| s3_whiteboard | t05 | BlueVault Hot tier costs 18 dollars per TB | True | True | True | yes |  |
| s3_whiteboard | t05 | BlueVault charges no egress fees | True | True | True | yes |  |
