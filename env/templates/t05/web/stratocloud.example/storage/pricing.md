# StratoCloud Object Storage Pricing

StratoCloud Object Storage gives teams durable, scalable storage for backups, media files, logs and application data. You pay only for what you use, with no upfront commitment and no minimum term. Prices below apply to all regions in North America and Europe.

## Storage classes

StratoCloud offers three storage classes. Standard is designed for frequently accessed data and serves requests with low latency. Infrequent Access reduces the storage price for data that is read less than once a month. Archive is the lowest-cost class for long-term retention, with retrieval times measured in hours.

FACT: StratoCloud Standard costs 21 dollars per TB per month.
FACT: StratoCloud charges 80 dollars per TB for data transfer out to the internet.
FACT: StratoCloud stores Standard data across 3 availability zones by default.

## Requests

Write and list requests are billed per thousand operations, and read requests are billed at a lower rate. For most backup and archive workloads, request charges are a small fraction of the monthly bill, but applications that read many small objects should estimate request volume carefully.

## Free allowance

New accounts receive a free allowance of storage and outbound transfer during the first twelve months. Transfer into StratoCloud is always free, as is transfer between services in the same region.

## Durability and security

All objects are encrypted at rest using provider-managed keys, and customers can supply their own keys if required. Versioning, object lock and lifecycle rules are available on every bucket at no extra charge, making it straightforward to move older data into cheaper classes automatically.

## Billing

Usage is metered hourly and billed monthly. Committed use discounts are available for customers who reserve capacity for one or three years.
