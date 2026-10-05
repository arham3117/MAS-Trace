# Static Scanner Benchmark Report

Every year we run a set of popular static analysis tools against a shared benchmark of intentionally vulnerable applications. The benchmark covers web services, command-line tools and infrastructure templates written in several languages, with a known list of real vulnerabilities and many code paths that look risky but are actually safe.

## Method

Each scanner was run with its default configuration on the same commit of each benchmark project. We measured how many known vulnerabilities each tool detected, how many false alarms it raised and how long a full scan took on standard CI hardware.

FACT: VulnSpect detected 92 percent of known vulnerabilities in the benchmark.
FACT: ScanGuard had the lowest false positive rate at 6 percent.
FACT: CodeSentry completed full scans 40 percent faster than the benchmark average.

## Findings

No tool found everything. Higher detection rates generally came with more false positives, which matters because developers quickly learn to ignore noisy tools. The best results came from teams that combined a scanner with clear triage ownership and regular rule tuning.

## Language coverage

Coverage varied widely by language. Mainstream web languages were well supported by all tools, while newer or less common languages often had limited rule sets. Teams with polyglot codebases should test scanners on their own repositories before deciding.

## Conclusion

Choose a scanner that developers will actually use. Fast feedback in pull requests, low noise and good fix guidance tend to matter more than a few extra points of detection on a benchmark.
