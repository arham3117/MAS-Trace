# ScanGuard Product Overview

ScanGuard is a static application security testing platform that finds vulnerabilities in source code before it reaches production. It is designed for engineering teams that want fast, low-noise results inside the tools they already use, without a dedicated security team managing the scanner.

## How it works

ScanGuard analyses code on every commit or pull request, tracing data flow from untrusted inputs to sensitive operations. Findings appear as comments on the pull request with an explanation of the risk and a suggested fix, so developers can resolve issues while the context is still fresh.

FACT: ScanGuard costs 400 dollars per month for up to 50 developers.
FACT: ScanGuard scans a typical repository in under 3 minutes.
FACT: ScanGuard supports 11 programming languages.

## Low false positives

A common complaint about security scanners is noise. ScanGuard uses tuned rule sets and reachability analysis to suppress findings in code that cannot be called from an entry point. Teams can mark findings as accepted risk, and those decisions carry forward to future scans.

## Deployment options

ScanGuard is available as a hosted service or as a self-managed scanner that runs inside the customer's own CI runners. In the self-managed mode, source code never leaves the customer's infrastructure, and only finding metadata is uploaded to the dashboard.

## Reporting

The dashboard shows open findings by severity, repository and team, along with trends over time. Reports can be exported for audits, and policies can block merges when critical findings are introduced.

## Getting started

Most teams connect their first repository in less than fifteen minutes. A free trial covers up to five repositories for thirty days with full features enabled.
