#!/usr/bin/env python3
"""
Builds assets/activity.svg — a custom contribution dashboard for the profile README.
Shows contributions, streaks, consistency, a heatmap, a weekly trend and top languages.
No issues / pull requests / reviews, no stars or forks.

Runs inside GitHub Actions (needs GITHUB_TOKEN and USERNAME env vars).
Run locally with:  python3 activity.py --demo   (uses sample data)
"""
import json, os, sys, random, datetime as dt, urllib.request
from xml.sax.saxutils import escape

OUT = os.environ.get("OUTPUT", "assets/activity.svg")

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount weekday } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false,
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes { languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
        edges { size node { name color } } } }
    }
  }
}"""


# ---------------------------------------------------------------- data
def fetch(login, token):
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "profile-activity-card"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        sys.exit(f"GraphQL error: {data['errors']}")
    return data["data"]["user"]


def demo():
    random.seed(7)
    end = dt.date(2026, 10, 14)
    start = end - dt.timedelta(days=end.weekday() + 1 + 52 * 7)  # Sunday, 53 weeks back
    weeks, cur, week = [], start, []
    while cur <= end:
        age = (end - cur).days
        p = 0.12 if age > 200 else 0.35 if age > 60 else 0.6
        n = 0 if age <= 6 and False else (random.choice([1, 1, 2, 2, 3, 4, 6, 9]) if random.random() < p else 0)
        if age <= 6:
            n = random.choice([2, 3, 5])
        week.append({"date": cur.isoformat(), "contributionCount": n, "weekday": (cur.weekday() + 1) % 7})
        if len(week) == 7:
            weeks.append({"contributionDays": week}); week = []
        cur += dt.timedelta(days=1)
    if week:
        weeks.append({"contributionDays": week})
    total = sum(d["contributionCount"] for w in weeks for d in w["contributionDays"])
    langs = [{"languages": {"edges": [{"size": 620000, "node": {"name": "TypeScript", "color": "#3178c6"}},
                                      {"size": 410000, "node": {"name": "JavaScript", "color": "#f1e05a"}},
                                      {"size": 90000, "node": {"name": "CSS", "color": "#663399"}},
                                      {"size": 30000, "node": {"name": "HTML", "color": "#e34c26"}}]}}]
    return {"contributionsCollection": {"contributionCalendar": {"totalContributions": total, "weeks": weeks}},
            "repositories": {"nodes": langs}}


# ---------------------------------------------------------------- stats
def stats(user):
    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = cal["weeks"]
    days = [d for w in weeks for d in w["contributionDays"]]
    counts = [d["contributionCount"] for d in days]

    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)

    i = len(counts) - 1
    if i >= 0 and counts[i] == 0:      # today not committed yet doesn't break the streak
        i -= 1
    current = 0
    while i >= 0 and counts[i] > 0:
        current += 1; i -= 1

    active = sum(1 for c in counts if c)
    best = max(days, key=lambda d: d["contributionCount"]) if days else None

    langs = {}
    for repo in user["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            n = e["node"]["name"]
            langs.setdefault(n, [0, e["node"]["color"] or "#64748B"])
            langs[n][0] += e["size"]
    top = sorted(langs.items(), key=lambda kv: -kv[1][0])[:5]
    tot = sum(v[0] for _, v in top) or 1
    top = [(n, v[0] / tot, v[1]) for n, v in top]

    return dict(total=cal["totalContributions"], weeks=weeks, days=days, longest=longest,
                current=current, active=active, ndays=len(days), best=best, langs=top)


# ---------------------------------------------------------------- render
C = dict(bg="#0B1220", line="#1E293B", acc="#38BDF8", acc2="#A78BFA", muted="#94A3B8",
         txt="#E2E8F0", dim="#64748B", green="#22C55E", amber="#FBBF24", empty="#131C2E")
LEVELS = ["#0C4A6E", "#0369A1", "#0EA5E9", "#38BDF8", "#7DD3FC"]


def level(n, mx):
    if n == 0:
        return None
    q = n / mx
    return 0 if q <= .15 else 1 if q <= .3 else 2 if q <= .5 else 3 if q <= .75 else 4


def fmt_date(s):
    d = dt.date.fromisoformat(s)
    return d.strftime("%b %-d, %Y")


def render(s):
    W = 900
    P = 30
    cell, gap = 12, 3
    step = cell + gap
    weeks = s["weeks"]
    gx = P + 34                       # heatmap x (room for day labels)
    gy = 210                          # heatmap y
    gw = len(weeks) * step - gap
    ry = gy + 7 * step + 6             # legend row y
    ty = ry + 56                      # trend chart y
    th = 70
    ly = ty + th + 40                 # languages y
    H = ly + 62 if s["langs"] else ty + th + 30
    o = []
    a = o.append

    first = s["days"][0]["date"] if s["days"] else ""
    last = s["days"][-1]["date"] if s["days"] else ""

    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
      f'role="img" aria-label="Contribution activity: {s["total"]} contributions in the last year">')
    a(f'''<defs>
  <linearGradient id="bd" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{C["acc"]}"/><stop offset=".5" stop-color="#1E3A8A"/><stop offset="1" stop-color="{C["acc2"]}"/></linearGradient>
  <radialGradient id="orb" cx=".92" cy=".02" r=".5"><stop offset="0" stop-color="{C["acc"]}" stop-opacity=".16"/><stop offset="1" stop-color="{C["acc"]}" stop-opacity="0"/></radialGradient>
  <radialGradient id="orb2" cx=".02" cy="1" r=".5"><stop offset="0" stop-color="{C["acc2"]}" stop-opacity=".12"/><stop offset="1" stop-color="{C["acc2"]}" stop-opacity="0"/></radialGradient>
  <pattern id="grid" width="22" height="22" patternUnits="userSpaceOnUse"><path d="M22 0H0V22" fill="none" stroke="{C["line"]}" stroke-width=".6"/></pattern>
  <linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{C["acc"]}" stop-opacity=".45"/><stop offset="1" stop-color="{C["acc"]}" stop-opacity="0"/></linearGradient>
  <linearGradient id="stroke" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{C["acc2"]}"/><stop offset="1" stop-color="{C["acc"]}"/></linearGradient>
  <linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".22"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
  <filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <clipPath id="gridclip"><rect x="{gx}" y="{gy}" width="{gw}" height="{7*step-gap}" rx="3"/></clipPath>
</defs>
<style>
  text{{font-family:"Segoe UI",Inter,-apple-system,"Helvetica Neue",Arial,sans-serif}}
  .mono{{font-family:"JetBrains Mono","Fira Code",Menlo,Consolas,monospace}}
  .up{{opacity:0;animation:up .7s cubic-bezier(.2,.8,.2,1) forwards}}
  @keyframes up{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:none}}}}
  .cell{{opacity:0;animation:pop .45s ease-out forwards}}
  @keyframes pop{{from{{opacity:0}}to{{opacity:1}}}}
  .hot{{animation:pop .45s ease-out forwards, breathe 2.6s ease-in-out infinite}}
  @keyframes breathe{{0%,100%{{opacity:1}}50%{{opacity:.55}}}}
  .sweep{{animation:sweep 5s ease-in-out 2.4s infinite both}}
  @keyframes sweep{{0%{{transform:translateX(-160px)}}60%,100%{{transform:translateX({gw+200}px)}}}}
  .draw{{stroke-dasharray:2000;stroke-dashoffset:2000;animation:draw 2.2s ease-out 1.2s forwards}}
  @keyframes draw{{to{{stroke-dashoffset:0}}}}
  .fill{{opacity:0;animation:pop 1s ease-out 2.4s forwards}}
  .bar{{transform-box:fill-box;transform-origin:left;transform:scaleX(0);animation:grow 1.2s cubic-bezier(.2,.8,.2,1) 2.8s forwards}}
  @keyframes grow{{to{{transform:scaleX(1)}}}}
  .pulse{{animation:breathe 2s ease-in-out infinite}}
</style>''')

    # card
    a(f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="16" fill="{C["bg"]}"/>')
    a(f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="16" fill="url(#grid)" opacity=".45"/>')
    a(f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="16" fill="url(#orb)"/>')
    a(f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="16" fill="url(#orb2)"/>')
    a(f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="16" fill="none" stroke="url(#bd)" stroke-width="2"/>')

    # header
    a(f'<g class="up" style="animation-delay:.1s">'
      f'<circle class="pulse" cx="{P+6}" cy="40" r="5" fill="{C["green"]}"/>'
      f'<text x="{P+20}" y="46" fill="{C["txt"]}" font-size="19" font-weight="700">Contribution Activity</text>'
      f'<text x="{W-P}" y="45" text-anchor="end" fill="{C["dim"]}" font-size="12.5" class="mono">'
      f'{escape(fmt_date(first))}  →  {escape(fmt_date(last))}</text></g>')

    # KPI tiles
    pct = round(100 * s["active"] / max(s["ndays"], 1))
    best = s["best"]
    tiles = [
        (f'{s["total"]:,}', "contributions", "in the last year", C["acc"]),
        (f'{s["current"]}', "day streak", "current", C["green"]),
        (f'{s["longest"]}', "day streak", "longest", C["amber"]),
        (f'{s["active"]}', "active days", f"{pct}% of the year", C["acc2"]),
    ]
    tw = (W - 2 * P - 3 * 14) / 4
    for k, (num, lab, sub, col) in enumerate(tiles):
        x = P + k * (tw + 14)
        a(f'<g class="up" style="animation-delay:{.25 + k*.12:.2f}s">'
          f'<rect x="{x:.1f}" y="70" width="{tw:.1f}" height="96" rx="12" fill="#0F172A" stroke="{C["line"]}"/>'
          f'<rect x="{x:.1f}" y="70" width="4" height="96" rx="2" fill="{col}"/>'
          f'<text x="{x+22:.1f}" y="118" fill="{col}" font-size="34" font-weight="800">{escape(num)}</text>'
          f'<text x="{x+22:.1f}" y="140" fill="{C["txt"]}" font-size="13.5" font-weight="600">{escape(lab)}</text>'
          f'<text x="{x+22:.1f}" y="157" fill="{C["dim"]}" font-size="12">{escape(sub)}</text></g>')

    # heatmap labels
    for r, lab in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        a(f'<text x="{gx-8}" y="{gy + r*step + cell - 2}" text-anchor="end" fill="{C["dim"]}" font-size="10.5">{lab}</text>')
    last_m = None
    for wi, w in enumerate(weeks):
        d0 = dt.date.fromisoformat(w["contributionDays"][0]["date"])
        m = d0.month
        if m != last_m and (wi < len(weeks) - 2):
            if last_m is not None or d0.day <= 7:
                a(f'<text x="{gx + wi*step}" y="{gy-8}" fill="{C["dim"]}" font-size="10.5">{d0.strftime("%b")}</text>')
            last_m = m

    # heatmap cells
    mx = max([d["contributionCount"] for d in s["days"]] + [1])
    for wi, w in enumerate(weeks):
        delay = .4 + wi * .028
        for d in w["contributionDays"]:
            r = d["weekday"]
            x, y = gx + wi * step, gy + r * step
            lv = level(d["contributionCount"], mx)
            title = f'{d["contributionCount"]} on {d["date"]}'
            if lv is None:
                a(f'<rect class="cell" style="animation-delay:{delay:.2f}s" x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{C["empty"]}"><title>{title}</title></rect>')
            else:
                cls = "cell hot" if lv == 4 else "cell"
                flt = ' filter="url(#glow)"' if lv >= 3 else ""
                a(f'<rect class="{cls}" style="animation-delay:{delay:.2f}s"{flt} x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{LEVELS[lv]}"><title>{title}</title></rect>')
    # light sweep across the grid
    a(f'<g clip-path="url(#gridclip)"><rect class="sweep" x="{gx}" y="{gy}" width="140" height="{7*step}" fill="url(#sweep)"/></g>')

    # legend row: best day on the left, Less/More scale on the right
    R = gx + gw
    sx0 = R - 34 - 6 * 15
    a(f'<g class="up" style="animation-delay:1.8s">')
    a(f'<text x="{sx0 - 6}" y="{ry + 15}" text-anchor="end" fill="{C["dim"]}" font-size="10.5">Less</text>')
    for k, col in enumerate([C["empty"]] + LEVELS):
        a(f'<rect x="{sx0 + k*15}" y="{ry + 5}" width="11" height="11" rx="2.5" fill="{col}"/>')
    a(f'<text x="{R}" y="{ry + 15}" text-anchor="end" fill="{C["dim"]}" font-size="10.5">More</text>')
    if best and best["contributionCount"]:
        a(f'<text x="{gx}" y="{ry + 15}" fill="{C["dim"]}" font-size="11.5">best day: '
          f'<tspan fill="{C["txt"]}" font-weight="600">{best["contributionCount"]} contributions</tspan> · {escape(fmt_date(best["date"]))}</text>')
    a('</g>')

    # weekly trend
    totals = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in weeks]
    tmx = max(totals + [1])
    pts = [(gx + i * step + cell / 2, ty + th - (v / tmx) * (th - 8)) for i, v in enumerate(totals)]
    a(f'<text x="{P}" y="{ty - 12}" fill="{C["muted"]}" font-size="12" font-weight="600" class="up" style="animation-delay:1.1s">Weekly momentum</text>')
    a(f'<line x1="{gx}" y1="{ty+th}" x2="{gx+gw}" y2="{ty+th}" stroke="{C["line"]}"/>')
    if len(pts) > 1:
        def smooth(p):
            d = f"M{p[0][0]:.1f},{p[0][1]:.1f}"
            for i in range(1, len(p)):
                x0, y0 = p[i-1]; x1, y1 = p[i]; cx = (x0 + x1) / 2
                d += f" C{cx:.1f},{y0:.1f} {cx:.1f},{y1:.1f} {x1:.1f},{y1:.1f}"
            return d
        line = smooth(pts)
        a(f'<path class="fill" d="{line} L{pts[-1][0]:.1f},{ty+th} L{pts[0][0]:.1f},{ty+th} Z" fill="url(#area)"/>')
        a(f'<path class="draw" d="{line}" fill="none" stroke="url(#stroke)" stroke-width="2.4" stroke-linecap="round" filter="url(#glow)"/>')
        px, py = pts[-1]
        a(f'<g class="fill"><circle cx="{px:.1f}" cy="{py:.1f}" r="4.5" fill="{C["acc"]}"/>'
          f'<circle class="pulse" cx="{px:.1f}" cy="{py:.1f}" r="9" fill="none" stroke="{C["acc"]}" stroke-width="1.5"/></g>')

    # languages
    if s["langs"]:
        a(f'<text x="{P}" y="{ly - 12}" fill="{C["muted"]}" font-size="12" font-weight="600" class="up" style="animation-delay:2.6s">Languages I write most</text>')
        bx, bw = P, W - 2 * P
        a(f'<rect x="{bx}" y="{ly}" width="{bw}" height="10" rx="5" fill="{C["empty"]}"/>')
        a(f'<clipPath id="barclip"><rect x="{bx}" y="{ly}" width="{bw}" height="10" rx="5"/></clipPath><g clip-path="url(#barclip)"><g class="bar">')
        x = bx
        for n, frac, col in s["langs"]:
            w_ = bw * frac
            a(f'<rect x="{x:.1f}" y="{ly}" width="{w_+.5:.1f}" height="10" fill="{col}"/>')
            x += w_
        a('</g></g>')
        x = bx
        a(f'<g class="up" style="animation-delay:3.2s">')
        for n, frac, col in s["langs"]:
            label = f"{n} {frac*100:.1f}%"
            a(f'<circle cx="{x+5}" cy="{ly+30}" r="5" fill="{col}"/>'
              f'<text x="{x+15}" y="{ly+34}" fill="{C["txt"]}" font-size="12.5">{escape(n)} <tspan fill="{C["dim"]}">{frac*100:.1f}%</tspan></text>')
            x += 30 + len(label) * 7.2
        a('</g>')

    a('</svg>')
    return "\n".join(o)


def main():
    if "--demo" in sys.argv:
        user = demo()
    else:
        token, login = os.environ.get("GITHUB_TOKEN"), os.environ.get("USERNAME")
        if not token or not login:
            sys.exit("Set GITHUB_TOKEN and USERNAME (or run with --demo)")
        user = fetch(login, token)
    svg = render(stats(user))
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
