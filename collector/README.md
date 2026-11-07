# Collector (AWS Lambda) - RETIRED

> **Status: retired on Nov 6, 2026.** The EventBridge rule `trigger-market` is disabled, so this Lambda no longer runs. It was disabled, not deleted, so it can be turned back on if needed.

## Why it was retired

The team decided to use the Steam Community Market as the only price source for CS2 and Dota 2. This Lambda pulled from Skinport, so it no longer fits the project.

Steam collection now runs on EC2 with `backend/steam_sync.py` on a systemd timer. See `deploy/aws/install-steam-sync.sh`.

## What is kept

- The Lambda function and the `trigger-market` rule are kept in AWS (disabled).
- The Skinport snapshots already in S3 are kept. `loader/load_snapshot.py` can still read them.
- This code stays in the repo as a record of the first collector.

## How it worked

Pulled the full Skinport catalog for CS2 and Dota 2 once an hour and saved each snapshot to S3.

    EventBridge (hourly)  ->  Lambda  ->  Skinport /v1/items  ->  S3

| Game | Steam app id | S3 folder |
| --- | --- | --- |
| CS2 | 730 | `cs2/YYYY/MM/DD/HHMMSS.json.br` |
| Dota 2 | 570 | `dota2/YYYY/MM/DD/HHMMSS.json.br` |

Snapshots are stored exactly as Skinport sends them (Brotli compressed JSON).

## Settings (if it is ever turned back on)

- Runtime: Python 3.12, handler `lambda_function.lambda_handler`
- Environment variable `BUCKET`: the S3 bucket name
- Timeout: at least 2 minutes (two requests per run)
- IAM: `s3:PutObject` on the bucket
- To turn it back on: EventBridge > Scheduled rules > `trigger-market` > Enable

## Why there was no work queue

The proposal planned a queue with several workers. Skinport returns the whole catalog for a game in one request, so one Lambda run per hour covered everything and stayed far under the rate limit. A queue only makes sense for a source that needs one request per item.
