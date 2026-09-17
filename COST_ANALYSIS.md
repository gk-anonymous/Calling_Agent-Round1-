# Round 1 Cost Analysis

These are estimates for the challenge's synthetic profile, not a billing quote. I use the reference ap-south-1 rates of approximately `$0.046/vCPU-hour` and `$0.0051/GB-hour`, 30 days/month, and assume the campaign windows total four hours per day. ALB is estimated at `$0.025/hour` and NAT at `$0.05/hour`, before NAT data processing.

## Configuration A: 1 vCPU / 2 GB, 1 to 5 tasks

The baseline is 20 hours/day at one task: `20 task-hours/day`. The two campaign windows total four hours/day; using the reference's average of three tasks during the ramp and hold gives `4 x 3 = 12 task-hours/day`. Total is `32 task-hours/day`.

Per task-hour: `(1 x 0.046) + (2 x 0.0051) = $0.0562`. Monthly compute is `32 x 0.0562 x 30 = $53.95`. Add approximately `$18` ALB and `$36` NAT gateway hourly charge: **about `$108/month` before NAT data processing and other AWS charges**.

## Configuration B: 0.5 vCPU / 1 GB, 1 to 10 tasks

The baseline remains `20 task-hours/day`. For the campaign, six smaller tasks is a comparable half-capacity granularity assumption, so campaign usage is `4 x 6 = 24 task-hours/day`. Total is `44 task-hours/day`.

Per task-hour: `(0.5 x 0.046) + (1 x 0.0051) = $0.0281`. Monthly compute is `44 x 0.0281 x 30 = $37.09`. With the same fixed ALB/NAT estimate, **about `$91/month` before NAT data processing and other AWS charges**.

## Recommendation

Configuration B has finer scale-out granularity and a lower baseline floor, which is useful when calls arrive unevenly. Configuration A is simpler to operate and gives each task more concurrency and memory headroom, reducing scheduling pressure and potentially improving tail latency. For the profile as stated I would start with B only after measuring per-task concurrency; otherwise A is the conservative production choice. ALB and NAT are fixed overheads and do not fall when task count falls. Private-subnet NAT also deserves a later architecture review because it can dominate the compute bill.
