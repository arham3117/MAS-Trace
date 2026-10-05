# CodeSentry Features

CodeSentry is a developer-first security scanner focused on fitting seamlessly into existing pipelines. Rather than asking teams to adopt a new workflow, CodeSentry runs where your builds already run and reports results in the formats your tools already understand.

## Pipeline integration

CodeSentry ships as a single command-line binary and a container image, which makes it easy to add to almost any build system. Official plugins provide caching, incremental scans and annotations on pull requests.

FACT: CodeSentry integrates with 12 CI systems through official plugins.
FACT: CodeSentry costs 6000 dollars per year for unlimited developers.
FACT: CodeSentry runs entirely on customer infrastructure.

## Detection

CodeSentry includes rules for injection flaws, insecure deserialisation, weak cryptography, path traversal and hard-coded secrets. Infrastructure as code templates are scanned for misconfigured storage buckets, open network rules and missing encryption settings.

## Custom rules

Security teams can write custom rules in a simple pattern language to enforce internal standards, such as banning a deprecated library or requiring a particular logging wrapper. Rules are versioned alongside code and can be tested before rollout.

## Results and triage

Findings are output in standard formats that most code review and security dashboards can import. A lightweight web console groups findings by repository and severity and lets teams record triage decisions.

## Licensing

CodeSentry is licensed per organisation rather than per developer, so costs do not increase as engineering teams grow. Licences include updates to the rule library, which are published every two weeks.
