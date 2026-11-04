import os, urllib.request, urllib.error, boto3
from datetime import datetime, timezone

BUCKET = os.environ["BUCKET"].strip()
s3 = boto3.client("s3")

# Steam app id -> S3 folder name. CS2 keeps its old folder so the loader still works.
GAMES = {730: "cs2", 570: "dota2"}

BASE_URL = "https://api.skinport.com/v1/items?app_id={app_id}&currency=USD&tradable=false"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def fetch_and_store(app_id, folder):
    req = urllib.request.Request(BASE_URL.format(app_id=app_id), headers={
        "Accept-Encoding": "br",
        "Accept": "application/json",
        "User-Agent": UA,
    })

    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            status = r.status
            encoding = r.headers.get("Content-Encoding")
    except urllib.error.HTTPError as e:
        return {"game": folder, "error": "fetch failed", "status": e.code}
    except urllib.error.URLError as e:
        return {"game": folder, "error": "network error", "reason": str(e.reason)}

    stamp = datetime.now(timezone.utc)
    key = f"{folder}/{stamp:%Y/%m/%d}/{stamp:%H%M%S}.json.br"

    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=raw,
        ContentType="application/json",
        ContentEncoding=encoding or "br",
        Metadata={"source": "skinport", "app_id": str(app_id), "collected_at": stamp.isoformat()},
    )

    return {"game": folder, "status": status, "encoding": encoding, "bytes": len(raw), "key": key}


def lambda_handler(event, context):
    # One game failing does not stop the other from being saved.
    return {"results": [fetch_and_store(app_id, folder) for app_id, folder in GAMES.items()]}