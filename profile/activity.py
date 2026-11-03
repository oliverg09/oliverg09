"""Reads my public activity from GitHub into profile/cache/."""
import json
import re
import urllib.parse
import urllib.request


def request(url, body=None, token=None):
    headers = {"User-Agent": "profile-aquarium", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers), timeout=30) as res:
        return res.read().decode()


def calendar_from_profile(user):
    """The contribution graph of the public profile: the same numbers visitors see."""
    page = request(f"https://github.com/users/{user}/contributions")
    dates = {cid: day for day, cid in re.findall(r'data-date="([\d-]+)"[^>]*?id="([^"]+)"', page)}
    counts = {}
    for cid, tip in re.findall(r'<tool-tip[^>]*?for="([^"]+)"[^>]*>([^<]*)</tool-tip>', page):
        if cid in dates:
            n = re.match(r"(\d+) contribution", tip)
            counts[dates[cid]] = int(n.group(1)) if n else 0
    return counts


def calendar_from_graphql(user, token):
    query = ("query($u:String!){user(login:$u){contributionsCollection{contributionCalendar"
             "{weeks{contributionDays{date contributionCount}}}}}}")
    body = json.dumps({"query": query, "variables": {"u": user}}).encode()
    res = json.loads(request("https://api.github.com/graphql", body, token))
    if res.get("errors"):
        raise SystemExit(f"GraphQL: {res['errors']}")
    weeks = res["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return {d["date"]: d["contributionCount"] for w in weeks for d in w["contributionDays"]}


def calendar(user, token):
    try:
        counts = calendar_from_profile(user)
        if len(counts) > 300:
            return counts
        print(f"profile page: only {len(counts)} days found")
    except OSError as exc:
        print(f"profile page: {exc}")
    if not token:
        raise SystemExit("No contribution calendar: the profile page failed and GITHUB_TOKEN is not set.")
    return calendar_from_graphql(user, token)


def pulls(user, token):
    q = urllib.parse.quote(f"type:pr author:{user} is:public")
    items = []
    for page in range(1, 11):  # the search API stops at 1,000 results
        res = json.loads(request(f"https://api.github.com/search/issues?q={q}&sort=created&order=desc"
                                 f"&per_page=100&page={page}", token=token))
        items += res["items"]
        if len(res["items"]) < 100:
            break
    return [{"title": i["title"], "url": i["html_url"], "repo": i["repository_url"].split("/repos/", 1)[1],
             "state": i["state"], "opened": i["created_at"][:10],
             "merged": (i["pull_request"].get("merged_at") or "")[:10] or None} for i in items]


def fetch(user, token, cache):
    cache.mkdir(exist_ok=True)
    days = dict(sorted(calendar(user, token).items()))
    prs = pulls(user, token)
    profile = json.loads(request(f"https://api.github.com/users/{user}", token=token))
    (cache / "calendar.json").write_text(json.dumps(days, indent=0) + "\n", encoding="utf-8")
    (cache / "pulls.json").write_text(json.dumps(prs, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (cache / "user.json").write_text(json.dumps({"created": profile["created_at"][:10]}) + "\n", encoding="utf-8")
    print(f"{len(days)} days, {sum(days.values())} contributions, {len(prs)} pull requests")
