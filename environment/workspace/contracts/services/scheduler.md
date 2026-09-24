# EventBridge Scheduler

Create two enabled schedules in the same schedule group:

- one schedule has exactly one target: the outbox relay Lambda;
- one schedule has exactly one target: the audit archiver Lambda.

Record the exact group and schedule names in `manifest.schedules`. Both targets
use the Scheduler IAM role defined in `iam.md`.

Use recurring schedule expressions. No exact interval is required.
