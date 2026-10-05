# The Real Cost of Egress in 2026

When teams compare cloud storage providers, they usually start with the headline price per terabyte. That figure matters, but our analysis of customer bills shows that data transfer charges are often the deciding factor in total cost, especially for workloads that serve files to users or move data between clouds.

## What we measured

We reviewed anonymised billing data from two hundred mid-sized companies using object storage for backups, analytics and media delivery. For each company we calculated the share of the storage bill that came from outbound transfer, request fees and the storage itself.

FACT: Egress made up 34 percent of the average object storage bill in our sample.
FACT: Backup-only workloads spent less than 5 percent of their bill on egress.
FACT: Companies that switched providers saved an average of 27 percent per year.

## Patterns by workload

Backup workloads are mostly write-heavy and rarely restore large volumes, so egress is a minor cost. Media delivery and analytics workloads are the opposite: they read data constantly, and transfer fees can exceed storage fees several times over.

## Practical tips

Estimate monthly outbound transfer before choosing a provider. Check whether free egress allowances have fair use limits. Consider placing compute close to storage to avoid cross-region charges. Finally, factor in migration cost: moving fifty terabytes out of a provider that charges for egress can be a meaningful one-off expense.

## Conclusion

Headline storage prices have converged, but transfer pricing still varies widely. A careful estimate of access patterns is the best way to avoid surprises.
