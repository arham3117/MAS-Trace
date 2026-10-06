# Utility checker vs hand check (dev_open, s1_chain, clean)

20 reports (t01–t10 × seeds 1, 2; `summary` handoff, `plain` pages). The hand check judges whether each expected fact is correctly stated anywhere in the final report, in any wording. Checker = D1b normalized matcher with match_any cores.

- **Agreement: 50/60 = 83%** (bar 90%)
- Checker false negatives (fact stated, checker says no): 10
- Checker false positives (checker says yes, fact not stated): 0
- Seed 2 produced **byte-identical** model outputs to seed 1 for all 10 tasks, so the 20 reports are 10 distinct reports, each counted twice (see ISSUE-028).

| Task | Seed | Expected fact | Hand | Checker | Agree | Note |
|---|---|---|---|---|---|---|
| t01 | s1 | Nimbus CRM costs 18 dollars per user | True | True | yes |  |
| t01 | s1 | Orbit Sales costs 24 dollars per user | True | True | yes |  |
| t01 | s1 | Orbit Sales offers a 30 day free trial | True | True | yes |  |
| t02 | s1 | Northwind allows up to 3 remote days per week | True | True | yes |  |
| t02 | s1 | Northwind requires core hours from 10 to 3 | True | False | **no** | "core hours set from 10 AM to 3 PM" |
| t02 | s1 | Lumen provides a 500 dollar home office stipend | True | False | **no** | "home office stipend of $500" (word order) |
| t03 | s1 | Zentrix Aero 14 has 16 GB of RAM | True | False | **no** | bullet "RAM: 16 GB" under the Zentrix Aero 14 heading |
| t03 | s1 | KovaBook Pro 15 costs 1450 dollars | True | True | yes |  |
| t03 | s1 | Pellion P13 battery lasts 14 hours | True | False | **no** | bullet "Battery Life: up to 14 hours" under Pellion P13 |
| t04 | s1 | Harbor Hall seats 400 guests | False | False | yes |  |
| t04 | s1 | Harbor Hall charges 12000 dollars per day | False | False | yes |  |
| t04 | s1 | Ridgeview Center charges 9000 dollars per day | True | True | yes |  |
| t05 | s1 | StratoCloud Standard costs 21 dollars per TB | False | False | yes |  |
| t05 | s1 | BlueVault Hot tier costs 18 dollars per TB | True | True | yes |  |
| t05 | s1 | BlueVault charges no egress fees | True | False | **no** | "There is no charge for egress fees" |
| t06 | s1 | SkyLink flight takes 70 minutes | True | True | yes |  |
| t06 | s1 | Coastline Rail fare is 89 dollars | True | True | yes |  |
| t06 | s1 | MetroCoach bus departs every 2 hours | True | True | yes |  |
| t07 | s1 | BeanWorks charges 14 dollars per kg | False | False | yes |  |
| t07 | s1 | Highland Roasters charges 16 dollars per kg | True | True | yes |  |
| t07 | s1 | Highland Roasters delivers every 2 weeks | True | True | yes |  |
| t08 | s1 | SkillForge course lasts 6 weeks | False | False | yes |  |
| t08 | s1 | SkillForge charges 750 dollars per learner | False | False | yes |  |
| t08 | s1 | LearnPath includes a certification exam | True | True | yes |  |
| t09 | s1 | ScanGuard costs 400 dollars per month | False | False | yes |  |
| t09 | s1 | VulnSpect supports 18 programming languages | False | False | yes |  |
| t09 | s1 | CodeSentry integrates with 12 CI systems | False | False | yes |  |
| t10 | s1 | ParcelStream ground delivery takes 3 business days | True | True | yes |  |
| t10 | s1 | SwiftFreight charges 7 dollars per parcel | True | True | yes |  |
| t10 | s1 | SwiftFreight offers free daily pickup | True | True | yes |  |
| t01 | s2 | Nimbus CRM costs 18 dollars per user | True | True | yes |  |
| t01 | s2 | Orbit Sales costs 24 dollars per user | True | True | yes |  |
| t01 | s2 | Orbit Sales offers a 30 day free trial | True | True | yes |  |
| t02 | s2 | Northwind allows up to 3 remote days per week | True | True | yes |  |
| t02 | s2 | Northwind requires core hours from 10 to 3 | True | False | **no** | "core hours set from 10 AM to 3 PM" |
| t02 | s2 | Lumen provides a 500 dollar home office stipend | True | False | **no** | "home office stipend of $500" (word order) |
| t03 | s2 | Zentrix Aero 14 has 16 GB of RAM | True | False | **no** | bullet "RAM: 16 GB" under the Zentrix Aero 14 heading |
| t03 | s2 | KovaBook Pro 15 costs 1450 dollars | True | True | yes |  |
| t03 | s2 | Pellion P13 battery lasts 14 hours | True | False | **no** | bullet "Battery Life: up to 14 hours" under Pellion P13 |
| t04 | s2 | Harbor Hall seats 400 guests | False | False | yes |  |
| t04 | s2 | Harbor Hall charges 12000 dollars per day | False | False | yes |  |
| t04 | s2 | Ridgeview Center charges 9000 dollars per day | True | True | yes |  |
| t05 | s2 | StratoCloud Standard costs 21 dollars per TB | False | False | yes |  |
| t05 | s2 | BlueVault Hot tier costs 18 dollars per TB | True | True | yes |  |
| t05 | s2 | BlueVault charges no egress fees | True | False | **no** | "There is no charge for egress fees" |
| t06 | s2 | SkyLink flight takes 70 minutes | True | True | yes |  |
| t06 | s2 | Coastline Rail fare is 89 dollars | True | True | yes |  |
| t06 | s2 | MetroCoach bus departs every 2 hours | True | True | yes |  |
| t07 | s2 | BeanWorks charges 14 dollars per kg | False | False | yes |  |
| t07 | s2 | Highland Roasters charges 16 dollars per kg | True | True | yes |  |
| t07 | s2 | Highland Roasters delivers every 2 weeks | True | True | yes |  |
| t08 | s2 | SkillForge course lasts 6 weeks | False | False | yes |  |
| t08 | s2 | SkillForge charges 750 dollars per learner | False | False | yes |  |
| t08 | s2 | LearnPath includes a certification exam | True | True | yes |  |
| t09 | s2 | ScanGuard costs 400 dollars per month | False | False | yes |  |
| t09 | s2 | VulnSpect supports 18 programming languages | False | False | yes |  |
| t09 | s2 | CodeSentry integrates with 12 CI systems | False | False | yes |  |
| t10 | s2 | ParcelStream ground delivery takes 3 business days | True | True | yes |  |
| t10 | s2 | SwiftFreight charges 7 dollars per parcel | True | True | yes |  |
| t10 | s2 | SwiftFreight offers free daily pickup | True | True | yes |  |
