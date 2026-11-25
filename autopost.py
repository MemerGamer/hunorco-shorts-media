#!/usr/bin/env python3
"""Keep Buffer's queues filled from schedule.json (run daily by GitHub Actions).

For every channel it creates the next scheduled posts until the channel holds
MAX_QUEUED scheduled posts (Buffer free plan: 10). A post is never created twice:
an entry is skipped when the channel already has a post at that exact time.
Exits non-zero (so GitHub sends a failure email) when a post failed to publish.

Env: BUFFER_API_KEY (required), DRY_RUN=1 to only print what would happen.
"""
import datetime as dt
import json
import os
import sys
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

API = "https://api.buffer.com"
ORG = "6b06ccf81b717aa2e40a05e9"
CHANNELS = {
    "youtube": "6b06cee58541f09ecb9c0b29",
    "tiktok": "6b06e8af8541f09ecb9d3d7a",
    "instagram": "6b06e7c78541f09ecb9d3647",
}
MEDIA_BASE = "https://memergamer.github.io/hunorco-shorts-media/"
TZ = ZoneInfo("Europe/Bucharest")
MAX_QUEUED = 10
MIN_LEAD = dt.timedelta(minutes=30)
THUMB_MS = 1500  # a frame from the title card
DRY = os.environ.get("DRY_RUN") == "1"


def gql(query: str, variables: dict | None = None) -> dict:
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['BUFFER_API_KEY']}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        body = json.load(r)
    if body.get("errors"):
        raise RuntimeError(json.dumps(body["errors"]))
    return body["data"]


def all_posts() -> list[dict]:
    q = """query($after: String, $input: PostsInput!) {
      posts(first: 100, after: $after, input: $input) {
        edges { node { id status dueAt channelId text error { message } } }
        pageInfo { hasNextPage endCursor }
      } }"""
    out, after = [], None
    while True:
        d = gql(q, {"after": after, "input": {"organizationId": ORG,
                    "filter": {"channelIds": list(CHANNELS.values())}}})["posts"]
        out += [e["node"] for e in d["edges"]]
        if not d["pageInfo"]["hasNextPage"]:
            return out
        after = d["pageInfo"]["endCursor"]


def due(e: dict) -> dt.datetime:
    h, m = map(int, e["time"].split(":"))
    d = dt.date.fromisoformat(e["date"])
    return dt.datetime(d.year, d.month, d.day, h, m, tzinfo=TZ)


def iso(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def post_input(platform: str, e: dict) -> dict:
    video = {"url": MEDIA_BASE + e["video"], "metadata": {"thumbnailOffset": THUMB_MS}}
    base = {
        "channelId": CHANNELS[platform],
        "schedulingType": "automatic",
        "mode": "customScheduled",
        "dueAt": iso(due(e)),
        "needsApproval": False,
        "source": "hunorco-shorts-media",
        "assets": [{"video": video}],
    }
    if platform == "youtube":
        base["text"] = e["youtube"]["description"]
        base["metadata"] = {"youtube": {
            "title": e["youtube"]["title"], "type": "short", "privacy": "public",
            "categoryId": "27", "madeForKids": False, "notifySubscribers": True,
            "license": "youtube", "embeddable": True, "isAiGenerated": False}}
    elif platform == "tiktok":
        base["text"] = e["tiktok"]
        base["metadata"] = {"tiktok": {"isAiGenerated": False}}
    else:
        base["text"] = e["instagram"]
        base["metadata"] = {"instagram": {"type": "reel", "shouldShareToFeed": True,
                                          "isAiGenerated": False}}
    return base


CREATE = """mutation($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess { post { id dueAt status } }
    ... on MutationError { message }
  } }"""


def main() -> int:
    sched = json.loads(Path(__file__).with_name("schedule.json").read_text())
    posts = all_posts()
    now = dt.datetime.now(dt.timezone.utc)
    failed = [p for p in posts if p["status"] == "error"]
    for p in failed:
        print(f"FAILED post {p['id']} on {p['channelId']} at {p['dueAt']}: {(p.get('error') or {}).get('message')}")
    rc = 1 if failed else 0
    for platform, cid in CHANNELS.items():
        mine = [p for p in posts if p["channelId"] == cid]
        taken = {p["dueAt"][:16] for p in mine if p.get("dueAt")}
        queued = sum(p["status"] in ("scheduled", "sending") for p in mine)
        added = 0
        for e in sched:
            if queued >= MAX_QUEUED:
                break
            t = due(e)
            if t - now < MIN_LEAD or iso(t)[:16] in taken:
                continue
            if DRY:
                print(f"[dry] {platform}: {e['date']} {e['slug']}")
            else:
                r = gql(CREATE, {"input": post_input(platform, e)})["createPost"]
                if "post" not in r:
                    print(f"ERROR {platform} {e['slug']}: {r.get('message')}")
                    rc = 1
                    break
                print(f"{platform}: queued {e['slug']} for {r['post']['dueAt']}")
            queued += 1
            added += 1
        print(f"{platform}: {queued} queued ({added} added)")
    return rc


if __name__ == "__main__":
    sys.exit(main())
