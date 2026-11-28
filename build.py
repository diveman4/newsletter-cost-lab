#!/usr/bin/env python3
"""Build the static site into ./site from data/platforms.json and content/*.html.

Usage: python3 build.py [--base-url https://user.github.io/repo/]
"""
import argparse, html, json, math, os, shutil, datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = json.load(open(os.path.join(ROOT, "data", "platforms.json")))
SITE_NAME = "Newsletter Cost Lab"

# Hands-on test results written by TA (data/tests/<platform_id>.json). Only files with a tester and date are used;
# with no files, no test claims appear anywhere on the site.
TESTS = {}
_tdir = os.path.join(ROOT, "data", "tests")
if os.path.isdir(_tdir):
    for _f in sorted(os.listdir(_tdir)):
        if _f.endswith(".json"):
            _t = json.load(open(os.path.join(_tdir, _f)))
            if not (_t.get("tester") and _t.get("tested_on") and _t.get("platform_id")):
                raise SystemExit(f"data/tests/{_f}: needs platform_id, tester and tested_on")
            TESTS[_t["platform_id"]] = _t
for _p in DATA["platforms"]:
    if _p["id"] in TESTS:
        TESTS[_p["id"]]["_name"] = _p["name"]
PLACEMENT = {"inbox": "Inbox", "promotions": "Promotions tab", "spam": "Spam", "not_tested": "Not tested"}


def test_rows(t):
    r = t.get("results", {})
    rows = []
    if r.get("signup_to_first_issue_minutes") is not None:
        rows.append(("Sign-up to first issue sent", f"{r['signup_to_first_issue_minutes']} minutes"))
    sf = r.get("signup_form")
    if sf:
        rows.append(("Sign-up form or landing page built", ("Yes" if sf.get("done") else "No") + (f", {sf['minutes']} minutes" if sf.get("minutes") is not None else "") + (f". {sf['note']}" if sf.get("note") else "")))
    ip = r.get("inbox_placement")
    if ip:
        rows.append(("Where the test issue landed", "; ".join(f"{k.capitalize()}: {PLACEMENT.get(v, v)}" for k, v in ip.items())))
    ie = r.get("import_export")
    if ie:
        rows.append(("Import / export", "; ".join(x for x in [f"imported {ie['imported']} test contacts" if ie.get("imported") is not None else "", f"export included {ie['exported_fields']}" if ie.get("exported_fields") else "", ie.get("note", "")] if x)))
    ws = r.get("welcome_sequence")
    if ws:
        rows.append(("3-email welcome sequence on the free plan", ("Possible" if ws.get("possible_on_plan") else "Not possible") + (f". {ws['note']}" if ws.get("note") else "")))
    return rows


def gallery(t, rel=""):
    shots = t.get("screenshots", [])
    if not shots:
        return ""
    figs = ""
    for sh in shots:
        w, h = sh.get("w"), sh.get("h")
        size = f' width="{w}" height="{h}"' if w and h else ""
        figs += (f'<figure><a href="{rel}assets/tests/{html.escape(sh["file"])}" target="_blank" rel="noopener">'
                 f'<img src="{rel}assets/tests/{html.escape(sh["file"])}" alt="{html.escape(sh["caption"])}" loading="lazy"{size}></a>'
                 f'<figcaption>{html.escape(sh["caption"])}</figcaption></figure>')
    return f'<h3>Screenshots from the test</h3><p class="fine">Personal names and email addresses are blacked out. Tap an image to enlarge.</p><div class="shots">{figs}</div>'


def hands_on_line(ids, rel="", what="this comparison", only=""):
    """Accurate 'have we tested this?' sentence for pages covering several platforms."""
    tested = [i for i in ids if i in TESTS]
    if not tested:
        return f"<p>We haven't run hands-on tests of {'either platform' if len(ids) == 2 else 'these platforms'} yet, so {what} covers published prices{only} only.</p>"
    links = ", ".join(f'{html.escape(TESTS[i]["_name"])} ({html.escape(TESTS[i]["tested_on"])})' for i in tested)
    rest = len(ids) - len(tested)
    return (f'<p>Hands-on test results so far: {links}. See <a href="{rel}hands-on-tests.html">our hands-on tests</a>.'
            + (f" The other {'platform' if rest == 1 else 'platforms'} here {'hasn' if rest == 1 else 'haven'}'t been tested yet, so otherwise {what} covers published prices{only}." if rest else "")
            + "</p>")


def test_section(p, rel=""):
    t = TESTS.get(p["id"])
    if not t:
        return ""
    rows = "".join(f"<tr><th>{html.escape(a)}</th><td>{html.escape(b)}</td></tr>" for a, b in test_rows(t))
    probs = "".join(f"<li>{html.escape(x)}</li>" for x in t.get("problems", []))
    return (f'<h2>Our hands-on test of {html.escape(p["name"])}</h2>'
            f'<p>Tested by {html.escape(t["tester"])} on {html.escape(t["tested_on"])}, following our <a href="{rel}methodology.html#lab">fixed-task test</a>. Account: {html.escape(t.get("plan", "free plan"))}.</p>'
            f'<div class="scroll"><table class="grid-table"><tbody>{rows}</tbody></table></div>'
            + (f"<p><strong>What went wrong:</strong></p><ul>{probs}</ul>" if probs else "")
            + (f'<p>{html.escape(t["notes"])}</p>' if t.get("notes") else "")
            + (f'<blockquote class="tester">&ldquo;{html.escape(t["tester_comment"])}&rdquo; &mdash; {html.escape(t["tester"])}</blockquote>' if t.get("tester_comment") else "")
            + gallery(t, rel)
            + f'<p class="fine">One test on one date. Results such as inbox placement can vary from send to send. See <a href="{rel}hands-on-tests.html">all test results</a>.</p>')
GSC_VERIFICATION = "8OATEkWut0D8qP_lGnY6NPHhcCzGoT8kGBMH8Hik5fw"  # Google Search Console (TA)
OUT = os.path.join(ROOT, "site")

# ---------- cost model (mirrors assets/calc.js) ----------

def plan_options(p, subs, paid_needed, billing):
    """Yield (plan_label, monthly_price) options that can hold `subs`."""
    idx = 1 if billing == "annual" else 2
    fp = p["free_plan"]
    if fp["max_subscribers"] is None or subs <= (fp["max_subscribers"] or 0):
        if not paid_needed or fp["paid_subscriptions"]:
            yield ("Free", 0.0)
    for plan in p["plans"]:
        if paid_needed and not plan["paid_subscriptions"]:
            continue
        for tier in plan["tiers"]:
            if subs <= tier[0]:
                yield (plan["name"], float(tier[idx]))
                break


def cost(p, subs, paid_subs=0, price=0.0, billing="annual"):
    """Return dict(plan, base, fees, total) or dict(skip=reason)."""
    paid_needed = paid_subs > 0
    fm = p["fee_model"]
    if paid_needed and fm["type"] == "not_compared":
        return {"skip": "paid newsletters not compared yet"}
    opts = list(plan_options(p, subs, paid_needed, billing))
    if not opts:
        return {"skip": "no plan for this list size in our data"}
    plan, base = min(opts, key=lambda o: o[1])
    rev = paid_subs * price
    fees = 0.0
    if paid_needed:
        if fm["type"] == "own_processing":
            fees = rev * fm["pct"] / 100 + paid_subs * fm["fixed"]
        else:
            pr = DATA["processing"]
            fees = rev * (fm["pct"] + pr["stripe_pct"]) / 100 + paid_subs * pr["stripe_fixed"]
    return {"plan": plan, "base": base, "fees": fees, "total": base + fees}


def money(x):
    return "$0" if x == 0 else ("$" + (f"{x:,.0f}" if x >= 100 else f"{x:,.2f}".removesuffix(".00")))

# ---------- layout ----------

CSS = open(os.path.join(ROOT, "assets", "style.css")).read()


def page(path, title, desc, body, base, jsonld=None):
    url = base + ("" if path == "index.html" else path)
    nav = [("index.html", "Cost calculator"), ("free-plans.html", "Free plans"),
           ("substack-fees.html", "Substack fees"), ("guides/choose-your-first-newsletter-platform.html", "Beginner guide"),
           ("methodology.html", "How we verify")]
    depth = path.count("/")
    rel = "../" * depth
    nav_html = "".join(f'<a href="{rel}{h}">{html.escape(t)}</a>' for h, t in nav)
    ld = f'<script type="application/ld+json">{json.dumps(jsonld)}</script>' if jsonld else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="google-site-verification" content="{GSC_VERIFICATION}">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}">
<style>{CSS}</style>
{ld}
</head>
<body>
<header class="top"><div class="wrap">
<a class="brand" href="{rel}index.html">{SITE_NAME}</a>
<nav>{nav_html}</nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer class="wrap foot">
<p>Prices last verified against each vendor's own pricing page on <strong>{DATA['verified_on']}</strong>. Vendors change prices without notice. Check the linked pricing page before you buy.</p>
<p><a href="{rel}about.html">About</a> · <a href="{rel}disclosure.html">Affiliate disclosure</a> · <a href="{rel}privacy.html">Privacy policy</a> · <a href="{rel}changelog.html">Price change log</a> · <a href="{rel}contact.html">Contact</a></p>
</footer>
</body>
</html>
"""


def platform_link(p, label=None, rel_prefix=""):
    label = html.escape(label or p["name"])
    if p.get("affiliate_url"):
        return f'<a href="{html.escape(p["affiliate_url"])}" rel="sponsored noopener" target="_blank">{label}</a><sup class="aff" title="Affiliate link">*</sup>'
    return f'<a href="{html.escape(p["official_url"])}" rel="noopener" target="_blank">{label}</a>'


def cta(p, verified):
    """A clearly labelled button to the vendor. Uses the affiliate link only where one is set (marked *)."""
    if p.get("affiliate_url"):
        return (f'<p class="cta"><a class="btn" href="{html.escape(p["affiliate_url"])}" rel="sponsored noopener" target="_blank">Visit {html.escape(p["name"])} &rarr;</a>'
                f'<sup class="aff" title="Affiliate link">*</sup> <span class="fine">Affiliate link. Opens {html.escape(p["name"])}\'s website. Our prices were checked {verified}; confirm the current price there.</span></p>')
    return (f'<p class="cta"><a class="btn" href="{html.escape(p["pricing_url"])}" rel="noopener" target="_blank">See {html.escape(p["name"])}\'s pricing page &rarr;</a> '
            f'<span class="fine">Our prices were checked {verified}; confirm the current price there.</span></p>')


def any_affiliate():
    return any(p.get("affiliate_url") for p in DATA["platforms"])


def disclosure_box(rel):
    if any_affiliate():
        return f'<p class="disc">Links marked * are affiliate links: if you buy through them we may earn a commission, at no extra cost to you. It never changes the numbers. <a href="{rel}disclosure.html">Details</a>.</p>'
    return f'<p class="disc">We have no affiliate links on this site right now. If that changes, every affiliate link will be marked next to the link. <a href="{rel}disclosure.html">Details</a>.</p>'

# ---------- pages ----------

def build(base):
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "guides"))
    os.makedirs(os.path.join(OUT, "assets"))
    shutil.copy(os.path.join(ROOT, "assets", "calc.js"), os.path.join(OUT, "assets", "calc.js"))
    if os.path.isdir(os.path.join(ROOT, "assets", "tests")):
        shutil.copytree(os.path.join(ROOT, "assets", "tests"), os.path.join(OUT, "assets", "tests"))
    with open(os.path.join(OUT, "assets", "platforms.json"), "w") as f:
        json.dump(DATA, f)
    P = {p["id"]: p for p in DATA["platforms"]}
    pages = []
    PRICING_GUIDES = [("kit-pricing.html", "Kit pricing explained"), ("beehiiv-pricing.html", "beehiiv pricing explained"),
                      ("mailerlite-pricing.html", "MailerLite pricing explained"), ("ghost-pricing.html", "Ghost(Pro) pricing explained"),
                      ("systemeio-pricing.html", "systeme.io pricing explained")]

    COMPARISONS = [("kit-vs-beehiiv-cost.html", "Kit vs beehiiv"), ("mailerlite-vs-kit-cost.html", "MailerLite vs Kit"),
                   ("ghost-vs-beehiiv-cost.html", "Ghost(Pro) vs beehiiv"), ("mailerlite-vs-beehiiv-cost.html", "MailerLite vs beehiiv"),
                   ("kit-vs-systemeio-cost.html", "Kit vs systeme.io"),
                   ("substack-fees.html", "Substack vs beehiiv and Ghost (fees)")]


    # ---- index: calculator + cheapest table
    sizes = [500, 1000, 2500, 5000, 10000, 25000, 50000]
    head = "".join(f"<th>{s:,}</th>" for s in sizes)
    rows = ""
    for p in DATA["platforms"]:
        cells = ""
        for s in sizes:
            c = cost(p, s)
            cells += f'<td>{money(c["total"])}<small>{html.escape(c["plan"])}</small></td>' if "total" in c else '<td class="na">–</td>'
        rows += f"<tr><th>{platform_link(p)}</th>{cells}</tr>"
    cheapest = []
    for s in sizes:
        best = min(((cost(p, s), p) for p in DATA["platforms"] if "total" in cost(p, s) and p["id"] != "substack"),
                   key=lambda x: x[0]["total"])
        cheapest.append((s, best))
    bullets = "".join(f"<li><strong>{s:,} subscribers:</strong> {html.escape(b[1]['name'])} {html.escape(b[0]['plan'])} at {money(b[0]['total'])}/mo{' (free)' if b[0]['total']==0 else ''}</li>" for s, b in cheapest)
    body = f"""
<h1>What will your newsletter platform actually cost?</h1>
<p class="lede">Enter your list size and, if you charge readers, your paid subscribers. The calculator picks the cheapest plan on each platform that can hold your list, then adds the platform's cut and card-processing fees. Every price comes from the vendor's own pricing page, checked on {DATA['verified_on']}.</p>
{disclosure_box('')}
<section class="card" id="calc">
<div class="grid">
<label>Email subscribers<input id="subs" type="number" min="0" step="100" value="1000" inputmode="numeric"></label>
<label>Paid subscribers<input id="paid" type="number" min="0" step="10" value="0" inputmode="numeric"></label>
<label>Price per paid subscriber ($/month)<input id="price" type="number" min="0" step="1" value="8" inputmode="decimal"></label>
<label>Billing<select id="billing"><option value="annual">Pay yearly (monthly equivalent)</option><option value="monthly">Pay month to month</option></select></label>
</div>
<div id="result" aria-live="polite"><noscript><p>The calculator needs JavaScript. The static table below has the same numbers for free newsletters.</p></noscript></div>
<p class="fine">Fees assume one card payment per paid subscriber per month at Stripe's standard US rate ({DATA['processing']['stripe_pct']}% + ${DATA['processing']['stripe_fixed']:.2f}). Kit uses its own 3.5% + $0.30 transaction fee instead. Taxes, currency conversion and app-store purchases are not included.</p>
</section>

<h2>Cheapest option for a free newsletter</h2>
<p>For a newsletter you don't charge for (no paid subscriptions), billed yearly, the lowest monthly price in our data is:</p>
<ul>{bullets}</ul>
<p>Substack is $0 at any size but takes 10% once you charge readers. See <a href="substack-fees.html">when Substack's cut overtakes a flat plan</a>.</p>

<h2>Monthly price by list size (free newsletter, yearly billing)</h2>
<div class="scroll"><table class="grid-table"><thead><tr><th>Platform</th>{head}</tr></thead><tbody>{rows}</tbody></table></div>
<p class="fine">The cheapest plan that holds the list is used. "–" means the platform has no plan for that size in our data, or the price isn't verified yet. Buttondown prices are its base plan without add-ons (paid subscriptions and other features cost extra).</p>

<h2>Before you pick on price alone</h2>
<ul>
<li><strong>Free-plan ceilings differ a lot:</strong> 100 (Buttondown) to 10,000 (Kit) subscribers. See <a href="free-plans.html">the free plan comparison</a>.</li>
<li><strong>Paid newsletters change the maths.</strong> A percentage cut is cheap when you're small and expensive when you grow.</li>
<li><strong>Deciding between Kit and beehiiv?</strong> See <a href="kit-vs-beehiiv-cost.html">Kit vs beehiiv cost at every list size</a>.</li>
{('<li><strong>Hands-on tests:</strong> we ran the same tasks (first issue, sign-up form, inbox placement, import/export) on ' + ', '.join(html.escape(P[k]['name']) for k in TESTS if k in P) + '. <a href="hands-on-tests.html">See what happened</a>.</li>') if TESTS else ''}
<li><strong>Switching later has a cost.</strong> Paid subscribers on some platforms can't simply be moved. Pick a platform you can stay on for at least a year.</li>
</ul>

<h2>Price guides</h2>
<ul>
<li><a href="kit-pricing.html">Kit pricing explained</a>: every plan and list size, yearly vs monthly</li>
<li><a href="beehiiv-pricing.html">beehiiv pricing explained</a>: Free, Lite and Pro at every list size</li>
<li><a href="beehiiv-discount.html">beehiiv discount and promo codes</a>: what actually lowers the price</li>
<li><a href="mailerlite-pricing.html">MailerLite pricing explained</a>: Free, Comfort and Power at every list size</li>
<li><a href="ghost-pricing.html">Ghost(Pro) pricing explained</a>: Starter, Publisher and Business at every list size</li>
<li><a href="systemeio-pricing.html">systeme.io pricing explained</a>: Free, Startup, Webinar and Unlimited by contact count</li>
<li><a href="cheapest-newsletter-platform-1000-subscribers.html">Cheapest newsletter platform for 1,000 subscribers</a></li>
<li><a href="cheapest-newsletter-platform-5000-subscribers.html">Cheapest newsletter platform for 5,000 subscribers</a></li>
<li><a href="cheapest-newsletter-platform-10000-subscribers.html">Cheapest newsletter platform for 10,000 subscribers</a></li>
<li><a href="cheapest-newsletter-platform-25000-subscribers.html">Cheapest newsletter platform for 25,000 subscribers</a></li>
<li><a href="kit-vs-beehiiv-cost.html">Kit vs beehiiv cost at every list size</a></li>
<li><a href="mailerlite-vs-kit-cost.html">MailerLite vs Kit cost at every list size</a></li>
<li><a href="ghost-vs-beehiiv-cost.html">Ghost(Pro) vs beehiiv cost for free and paid newsletters</a></li>
<li><a href="mailerlite-vs-beehiiv-cost.html">MailerLite vs beehiiv cost at every list size</a></li>
<li><a href="kit-vs-systemeio-cost.html">Kit vs systeme.io cost for free and paid newsletters</a></li>
<li><a href="substack-fees.html">Substack fees vs flat-price plans</a></li>
</ul>
<script src="assets/calc.js" defer></script>
"""
    ld = {"@context": "https://schema.org", "@type": "WebApplication", "name": "Newsletter platform cost calculator",
          "applicationCategory": "BusinessApplication", "operatingSystem": "Any", "url": base,
          "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}, "dateModified": DATA["verified_on"]}
    pages.append(("index.html", "Newsletter Platform Cost Calculator (Kit, beehiiv, Substack, Ghost, MailerLite)",
                  "Compare the real monthly cost of Kit, beehiiv, Substack, Ghost, MailerLite and systeme.io at your list size, including paid-subscription fees. Prices verified " + DATA["verified_on"] + ".", body, ld))

    # ---- free plans
    rows = ""
    order = sorted(DATA["platforms"], key=lambda p: -(p["free_plan"]["max_subscribers"] if p["free_plan"]["max_subscribers"] is not None else 10**9))
    for p in order:
        fp = p["free_plan"]
        cap = "Any size" if fp["max_subscribers"] is None else ("No free plan" if fp["max_subscribers"] == 0 else f"{fp['max_subscribers']:,}")
        paid = "Yes" if fp["paid_subscriptions"] else "No"
        rows += f"<tr><th>{platform_link(p)}</th><td>{cap}</td><td>{paid}</td><td>{html.escape(fp['summary'])}</td><td><a href='{html.escape(p['pricing_url'])}' rel='noopener' target='_blank'>Pricing page</a></td></tr>"
    body = f"""
<h1>Newsletter platform free plans compared</h1>
<p class="lede">How many subscribers can you have before you pay, and can you charge readers on the free plan? Checked on each vendor's pricing page on {DATA['verified_on']}.</p>
{disclosure_box('')}
<div class="scroll"><table class="grid-table"><thead><tr><th>Platform</th><th>Free up to</th><th>Paid subs on free plan</th><th>What you get</th><th>Source</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>Which free plan fits?</h2>
<ul>
<li><strong>You want the most room before paying:</strong> Kit's free plan covers up to 10,000 subscribers, the highest fixed cap here. Substack has no cap, but takes 10% when you charge.</li>
<li><strong>You want to sell or charge from day one without a monthly bill:</strong> Substack (10% cut), Kit (3.5% + $0.30 per transaction) and systeme.io (0% platform fee, up to 2,000 contacts) allow it on free plans.</li>
<li><strong>You only need a small list for now:</strong> beehiiv (2,500) also works, but paid subscriptions need a paid plan.</li>
</ul>
<p>Want the monthly price once you outgrow the free plan? <a href="index.html">Use the cost calculator</a>.</p>
<p>Kit and beehiiv side by side once you pass their free limits: <a href="kit-vs-beehiiv-cost.html">Kit vs beehiiv cost at every list size</a>.</p>
"""
    pages.append(("free-plans.html", "Newsletter Platform Free Plans Compared (Subscriber Limits, " + DATA["verified_on"][:4] + ")",
                  "Free plan subscriber limits for Kit, beehiiv, Substack, systeme.io, MailerLite, Buttondown and Ghost, and whether you can charge readers on each.", body, None))

    # ---- substack break-even
    price = 8
    lists = [1000, 5000, 10000, 25000]
    rows = ""
    for s in lists:
        for rival in ("beehiiv", "ghost"):
            r = P[rival]
            found = None
            for paid in range(1, s + 1):
                sub = cost(P["substack"], s, paid, price)["total"]
                rc = cost(r, s, paid, price)
                if "total" in rc and sub > rc["total"]:
                    found = (paid, sub, rc)
                    break
            if found:
                paid, sub, rc = found
                rows += f"<tr><td>{s:,}</td><td>{html.escape(r['name'])} {html.escape(rc['plan'])}</td><td>{paid:,} paid readers (${paid*price:,.0f}/mo revenue)</td><td>{money(sub)} vs {money(rc['total'])}</td></tr>"
            else:
                rows += f"<tr><td>{s:,}</td><td>{html.escape(r['name'])}</td><td>Never within this list size</td><td>–</td></tr>"
    body = f"""
<h1>Substack fees: when does the 10% cut cost more than a flat plan?</h1>
<p class="lede">Substack is free until you charge readers, then keeps 10% of paid-subscription revenue on top of card fees. Flat-price platforms with a 0% cut (beehiiv Lite/Pro, Ghost Publisher) cost money every month but take nothing extra. This page finds the break-even point.</p>
{disclosure_box('')}
<h2>Break-even at ${price}/month per paid subscriber, yearly billing</h2>
<div class="scroll"><table class="grid-table"><thead><tr><th>Total list</th><th>Compared with</th><th>Substack becomes more expensive at</th><th>Monthly cost at that point</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="fine">Both sides include Stripe's standard {DATA['processing']['stripe_pct']}% + ${DATA['processing']['stripe_fixed']:.2f} per payment, so the difference is Substack's 10% against the flat plan price. Prices verified {DATA['verified_on']}.</p>
<h2>How to read this</h2>
<p>The rule of thumb: Substack's cut overtakes a flat plan once 10% of your paid revenue is bigger than that plan's monthly price. At $8 per reader, every 10 paid subscribers adds $8 a month to Substack's take. A $49 plan is overtaken at around 62 paid readers.</p>
<p>Price isn't the only factor. Substack's network can bring readers, and moving paid subscribers off a platform later can mean asking them to re-subscribe. If you expect to charge readers within a year, run your own numbers in the <a href="index.html">calculator</a> before you start.</p>
"""
    pages.append(("substack-fees.html", "Substack Fees vs beehiiv and Ghost: Break-even Calculator",
                  "When does Substack's 10% cut cost more than a flat beehiiv or Ghost plan? Break-even points by list size, using prices verified " + DATA["verified_on"] + ".", body, None))

    # ---- guide
    body = f"""
<h1>How to choose your first newsletter platform: a 6-question checklist</h1>
<p class="lede">Most "best newsletter platform" lists rank tools. This checklist helps you decide which one fits <em>your</em> plans before you put your first subscriber on it. It uses only the prices and limits we verified on {DATA['verified_on']}.</p>
{disclosure_box('../')}
<h2>1. How many subscribers do you expect in 12 months?</h2>
<p>Be honest: most first newsletters stay under 1,000 for their first year. If that's you, a free plan covers it on Kit (up to 10,000), beehiiv (2,500) or systeme.io (2,000). MailerLite's free plan stops at 250 and Buttondown's at 100.</p>
<h2>2. Will you charge readers?</h2>
<p>If yes, the free plans that allow it are Substack (10% cut), Kit (3.5% + $0.30 per transaction) and systeme.io (0% platform fee). beehiiv and Ghost need a paid plan for paid subscriptions, but take 0%. See <a href="../substack-fees.html">the break-even table</a>.</p>
<h2>3. Do you need automations (welcome sequences, tagging)?</h2>
<p>Kit's free plan doesn't include visual automations; its Creator plan does. beehiiv lists automations from its Lite plan. Decide whether a welcome sequence matters on day one or can wait.</p>
<h2>4. Is the newsletter the product, or does it support another business?</h2>
<p>If the newsletter <em>is</em> the product, publishing-first tools (Substack, beehiiv, Ghost) give you a website and archive. If it supports courses, coaching or products, an all-in-one tool like Kit or systeme.io may save you a second subscription.</p>
<h2>5. What will it cost when you succeed?</h2>
<p>Put your 12-month subscriber goal into the <a href="../index.html">cost calculator</a>, not today's number. A platform that's free now can cost $100+ a month at 10,000 subscribers.</p>
<h2>6. How hard would it be to leave?</h2>
<p>Exporting a free subscriber list is usually simple. Moving <em>paid</em> subscribers can be harder because payment setups differ between platforms. If you plan to charge, pick the platform you'd be happy to stay on.</p>
<h2>Quick picks by situation</h2>
<div class="scroll"><table class="grid-table"><thead><tr><th>Your situation</th><th>Worth a look first</th><th>Why</th></tr></thead><tbody>
<tr><td>Free newsletter, want the most room before paying</td><td>{platform_link(P['kit'])}</td><td>Free up to 10,000 subscribers</td></tr>
<tr><td>Want to charge readers with no monthly bill</td><td>{platform_link(P['substack'])}</td><td>$0 to start, 10% of paid revenue</td></tr>
<tr><td>Plan to grow a paid newsletter past ~60 paying readers</td><td>{platform_link(P['beehiiv'])} or {platform_link(P['ghost'])}</td><td>0% cut on paid plans</td></tr>
<tr><td>Newsletter plus a course or digital product</td><td>{platform_link(P['systemeio'])}</td><td>Free up to 2,000 contacts, 0% platform fee</td></tr>
<tr><td>Small, simple, low-cost list</td><td>{platform_link(P['mailerlite'])}</td><td>Comfort from $10.80/mo (500 subs, yearly)</td></tr>
</tbody></table></div>
{hands_on_line([q["id"] for q in DATA["platforms"]], "../", "this guide", " and limits")}
"""
    ld = {"@context": "https://schema.org", "@type": "Article", "headline": "How to choose your first newsletter platform: a 6-question checklist",
          "dateModified": DATA["verified_on"], "datePublished": DATA["verified_on"], "author": {"@type": "Organization", "name": SITE_NAME}}
    pages.append(("guides/choose-your-first-newsletter-platform.html", "How to Choose Your First Newsletter Platform (6-Question Checklist)",
                  "A practical checklist for picking your first newsletter tool: list size, paid subscriptions, automations, cost at scale and switching risk.", body, ld))

    # ---- Kit vs beehiiv (all numbers computed from platforms.json)
    kit, bee = P["kit"], P["beehiiv"]
    kv_sizes = [1000, 2500, 5000, 10000, 15000, 25000, 50000]

    def cell(c):
        return f'{money(c["total"])}<small>{html.escape(c["plan"])}</small>' if "total" in c else "–"

    def winner(a, b):
        if "total" not in a or "total" not in b:
            return "–"
        if a["total"] == b["total"]:
            return "Same"
        return "Kit" if a["total"] < b["total"] else "beehiiv"

    def free_rows(billing):
        r = ""
        for s in kv_sizes:
            a, b = cost(kit, s, billing=billing), cost(bee, s, billing=billing)
            r += f"<tr><td>{s:,}</td><td>{cell(a)}</td><td>{cell(b)}</td><td>{winner(a, b)}</td></tr>"
        return r

    def plan_price(p, plan_name, s, idx):
        for pl in p["plans"]:
            if pl["name"] == plan_name:
                for t in pl["tiers"]:
                    if s <= t[0]:
                        return t[idx]
        return None

    pair_rows = ""
    for s in kv_sizes:
        vals = [plan_price(kit, "Creator", s, 1), plan_price(bee, "Lite", s, 1), plan_price(kit, "Pro", s, 1), plan_price(bee, "Pro", s, 1)]
        pair_rows += f"<tr><td>{s:,}</td>" + "".join(f"<td>{money(v) if v is not None else '–'}</td>" for v in vals) + "</tr>"

    kv_price, kv_share = 8, 0.05
    paid_rows = ""
    for s in kv_sizes:
        paid = int(s * kv_share)
        a, b = cost(kit, s, paid, kv_price), cost(bee, s, paid, kv_price)
        paid_rows += (f"<tr><td>{s:,}</td><td>{paid:,} (${paid*kv_price:,}/mo)</td>"
                      f"<td>{cell(a)}</td><td>{cell(b)}</td><td>{winner(a, b)}</td></tr>")

    kit_free = kit["free_plan"]["max_subscribers"]
    bee_free = bee["free_plan"]["max_subscribers"]
    kfm, pr = kit["fee_model"], DATA["processing"]
    # first list size (from beehiiv's tier boundaries) where beehiiv's cheapest paid-newsletter option beats Kit's at 5% paying
    flip = None
    for s in kv_sizes:
        paid = int(s * kv_share)
        a, b = cost(kit, s, paid, kv_price), cost(bee, s, paid, kv_price)
        if "total" in a and "total" in b and b["total"] < a["total"]:
            flip = (s, a, b)
            break
    flip_txt = "In our paid-newsletter example, Kit stays cheaper at every list size we have data for."
    if flip:
        flip_txt = f"In our paid-newsletter example, beehiiv is first the cheaper option at {flip[0]:,} subscribers ({money(flip[2]['total'])} vs {money(flip[1]['total'])} a month)."
    kit_pro_note = next((pl.get("monthly_factor_note", "") for pl in kit["plans"] if pl["name"] == "Pro"), "")
    body = f"""
<h1>Kit vs beehiiv: what each costs at every list size</h1>
<p class="lede">Kit and beehiiv are both popular with people starting a newsletter, but they price very differently. This page puts their published prices side by side at each list size, for a free newsletter and for one that charges readers. Prices verified on each vendor's pricing page on {DATA['verified_on']}.</p>
{disclosure_box('')}
<h2>The short version</h2>
<ul>
<li><strong>Free plans:</strong> Kit is free up to {kit_free:,} subscribers; beehiiv is free up to {bee_free:,}. Between those sizes, a free newsletter costs $0 on Kit but needs a paid beehiiv plan.</li>
<li><strong>Charging readers:</strong> Kit's free plan allows paid subscriptions with a {kfm['pct']}% + ${kfm['fixed']:.2f} transaction fee. beehiiv needs a paid plan (Lite or above) but takes a 0% cut, so you pay only Stripe's {pr['stripe_pct']}% + ${pr['stripe_fixed']:.2f}.</li>
<li>{flip_txt}</li>
</ul>

<h2>Free newsletter, yearly billing (monthly equivalent)</h2>
<div class="scroll"><table class="grid-table"><thead><tr><th>Subscribers</th><th>{platform_link(kit)}</th><th>{platform_link(bee)}</th><th>Cheaper</th></tr></thead><tbody>{free_rows('annual')}</tbody></table></div>

<h2>Free newsletter, month-to-month billing</h2>
<div class="scroll"><table class="grid-table"><thead><tr><th>Subscribers</th><th>Kit</th><th>beehiiv</th><th>Cheaper</th></tr></thead><tbody>{free_rows('monthly')}</tbody></table></div>
<p class="fine">The cheapest plan that holds the list is used for each platform. Month-to-month prices are read from each vendor's pricing page with yearly billing switched off.</p>

<h2>Plan against plan, yearly billing</h2>
<p>If you already know you want a paid plan (for example for automations or to remove branding), these are the entry and upper plans side by side:</p>
<div class="scroll"><table class="grid-table"><thead><tr><th>Subscribers</th><th>Kit Creator</th><th>beehiiv Lite</th><th>Kit Pro</th><th>beehiiv Pro</th></tr></thead><tbody>{pair_rows}</tbody></table></div>
<p class="fine">{html.escape(kit_pro_note)} Plan features differ, so compare what each plan includes on the vendor's pricing page before choosing on price.</p>

<h2>Paid newsletter example: {int(kv_share*100)}% of readers pay ${kv_price}/month</h2>
<div class="scroll"><table class="grid-table"><thead><tr><th>Subscribers</th><th>Paying readers</th><th>Kit total / month</th><th>beehiiv total / month</th><th>Cheaper</th></tr></thead><tbody>{paid_rows}</tbody></table></div>
<p class="fine">Totals are plan price (yearly billing) plus fees on paid subscriptions: Kit's {kfm['pct']}% + ${kfm['fixed']:.2f} per transaction, or Stripe's standard {pr['stripe_pct']}% + ${pr['stripe_fixed']:.2f} with beehiiv's 0% cut. One card payment per paying reader per month is assumed. Your own numbers will differ; try them in the <a href="index.html">cost calculator</a>.</p>

<h2>Things the price tables don't show</h2>
<ul>
<li>Kit's free plan has no visual automations; beehiiv's free plan has no paid subscriptions.</li>
<li>Kit sometimes runs a first-year discount on Pro. The tables use the standard price.</li>
<li>Both vendors change prices from time to time. Every change we find goes in the <a href="changelog.html">price change log</a>.</li>
</ul>
<p>Also compare: <a href="mailerlite-vs-kit-cost.html">MailerLite vs Kit cost</a>, <a href="ghost-vs-beehiiv-cost.html">Ghost(Pro) vs beehiiv cost</a>, <a href="mailerlite-vs-beehiiv-cost.html">MailerLite vs beehiiv cost</a>, <a href="kit-pricing.html">Kit pricing</a>, <a href="beehiiv-pricing.html">beehiiv pricing</a>.</p>
{hands_on_line(["kit", "beehiiv"], only=" and limits")}
"""
    pages.append(("kit-vs-beehiiv-cost.html", "Kit vs beehiiv Cost at Every List Size (" + DATA["verified_on"][:4] + ")",
                  "Kit vs beehiiv prices side by side from 1,000 to 50,000 subscribers, for free and paid newsletters, using prices verified " + DATA["verified_on"] + ".", body, None))

    # ---- MailerLite vs Kit (all numbers computed from platforms.json)
    ml = P["mailerlite"]
    mk_sizes = [500, 1000, 2500, 5000, 8000, 10000, 15000, 20000, 25000, 30000, 35000, 40000, 45000, 50000, 55000]
    mk_sizes = [s for s in mk_sizes if "total" in cost(ml, s) and "total" in cost(kit, s)]

    def mk_winner(a, b):
        if a["total"] == b["total"]:
            return "Same"
        return "MailerLite" if a["total"] < b["total"] else "Kit"

    def mk_rows(billing):
        r = ""
        for s in mk_sizes:
            a, b = cost(ml, s, billing=billing), cost(kit, s, billing=billing)
            r += f"<tr><td>{s:,}</td><td>{cell(a)}</td><td>{cell(b)}</td><td>{mk_winner(a, b)}</td></tr>"
        return r

    mk_y = [(s, cost(ml, s), cost(kit, s)) for s in mk_sizes]
    kit_free_sizes = [s for s, a, b in mk_y if b["total"] == 0]
    above = [(s, a, b) for s, a, b in mk_y if b["total"] > 0]
    ml_wins = [s for s, a, b in above if a["total"] < b["total"]]
    kit_wins = [s for s, a, b in above if b["total"] < a["total"]]
    gap = max(abs(a["total"] - b["total"]) for s, a, b in above) if above else 0
    ml_first = ml["plans"][0]
    mk_pair = ""
    for s in mk_sizes:
        vals = [plan_price(ml, "Comfort", s, 1), plan_price(kit, "Creator", s, 1), plan_price(ml, "Power", s, 1), plan_price(kit, "Pro", s, 1)]
        mk_pair += f"<tr><td>{s:,}</td>" + "".join(f"<td>{money(v) if v is not None else '–'}</td>" for v in vals) + "</tr>"
    def _and(xs):
        xs = list(xs)
        return "" if not xs else (xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1])
    above_txt = ""
    if above:
        above_txt = (f"<li><strong>Above {kit_free:,} subscribers</strong> both are paid and, with yearly billing, the prices are close (at most {money(gap)} a month apart in our table). "
                     f"The cheaper one switches with each vendor's price tiers (yearly billing; see the month-to-month table too): MailerLite at {_and(f'{s:,}' for s in ml_wins) or 'none'}; "
                     f"Kit at {_and(f'{s:,}' for s in kit_wins) or 'none'} subscribers.</li>")
    body = f"""
<h1>MailerLite vs Kit: what each costs at every list size</h1>
<p class="lede">MailerLite and Kit (formerly ConvertKit) are both email tools many people start a newsletter with. This page puts their published prices side by side from {mk_sizes[0]:,} to {mk_sizes[-1]:,} subscribers, using each vendor's own pricing page, checked on {DATA['verified_on']}.</p>
{disclosure_box('')}
<h2>The short version</h2>
<ul>
<li><strong>Up to {kit_free:,} subscribers:</strong> Kit's free plan covers the list, so a free newsletter costs $0 on Kit. MailerLite's free plan stops at {ml['free_plan']['max_subscribers']:,} subscribers; above that its cheapest plan is {html.escape(ml_first['name'])}, from {money(ml_first['tiers'][0][1])}/month billed yearly.</li>
{above_txt}
<li><strong>Charging readers:</strong> Kit allows paid subscriptions on every plan, including Free, with a {kfm['pct']}% + ${kfm['fixed']:.2f} transaction fee. MailerLite's paid-newsletter costs aren't in our data yet, so this page compares free newsletters only.</li>
<li><strong>Free plans aren't equal:</strong> Kit: {html.escape(kit['free_plan']['summary'])} MailerLite: {html.escape(ml['free_plan']['summary'])}</li>
</ul>

<h2>Free newsletter, yearly billing (monthly equivalent)</h2>
<div class="scroll"><table class="grid-table"><thead><tr><th>Subscribers</th><th>{platform_link(ml)}</th><th>{platform_link(kit)}</th><th>Cheaper</th></tr></thead><tbody>{mk_rows('annual')}</tbody></table></div>

<h2>Free newsletter, month-to-month billing</h2>
<div class="scroll"><table class="grid-table"><thead><tr><th>Subscribers</th><th>MailerLite</th><th>Kit</th><th>Cheaper</th></tr></thead><tbody>{mk_rows('monthly')}</tbody></table></div>
<p class="fine">The cheapest plan that holds the list is used for each platform. Both vendors price in tiers, so the subscriber counts above are tier limits: a list slightly over one moves to the next price.</p>

<h2>Plan against plan, yearly billing</h2>
<p>If you already know you want a paid plan (for example for automations), these are each vendor's two main plans side by side:</p>
<div class="scroll"><table class="grid-table"><thead><tr><th>Subscribers</th><th>MailerLite Comfort</th><th>Kit Creator</th><th>MailerLite Power</th><th>Kit Pro</th></tr></thead><tbody>{mk_pair}</tbody></table></div>
<p class="fine">{html.escape(kit_pro_note)} Plan features differ, so compare what each plan includes on the vendor's pricing page before choosing on price.</p>
<div class="ctas">{cta(ml, DATA['verified_on'])}{cta(kit, DATA['verified_on'])}</div>

<h2>Things the price tables don't show</h2>
<ul>
<li>The free plans differ in more than list size: see each one's limits in the short version above, and on <a href="free-plans.html">free plans compared</a>.</li>
<li>Kit sometimes runs a first-year discount on Pro. The tables use the standard price.</li>
<li>Prices change from time to time. Every change we find goes in the <a href="changelog.html">price change log</a>.</li>
</ul>
<p>More detail: <a href="mailerlite-pricing.html">MailerLite pricing</a>, <a href="kit-pricing.html">Kit pricing</a>, <a href="kit-vs-beehiiv-cost.html">Kit vs beehiiv</a>, <a href="mailerlite-vs-beehiiv-cost.html">MailerLite vs beehiiv</a>, or run your own numbers in the <a href="index.html">cost calculator</a>.</p>
{hands_on_line(["mailerlite", "kit"], only=" and limits")}
"""
    pages.append(("mailerlite-vs-kit-cost.html", "MailerLite vs Kit (ConvertKit) Pricing Compared at Every List Size (" + DATA["verified_on"][:4] + ")",
                  f"MailerLite vs Kit prices side by side from {mk_sizes[0]:,} to {mk_sizes[-1]:,} subscribers, yearly and monthly, using prices verified " + DATA["verified_on"] + ".", body, None))

    # ---- generic two-platform cost comparison (all numbers computed from platforms.json)
    def pair_page(aid, bid, fname, sizes, plan_pairs, lede, extra_points, paid_share=0.05, paid_price=8, title=None, desc=None):
        A, B = P[aid], P[bid]
        sizes = [s for s in sizes if "total" in cost(A, s) or "total" in cost(B, s)]

        def win(a, b):
            if "total" not in a or "total" not in b:
                return "–"
            if a["total"] == b["total"]:
                return "Same"
            return A["name"] if a["total"] < b["total"] else B["name"]

        def rows(billing):
            r = ""
            for s in sizes:
                a, b = cost(A, s, billing=billing), cost(B, s, billing=billing)
                r += f"<tr><td>{s:,}</td><td>{cell(a)}</td><td>{cell(b)}</td><td>{html.escape(win(a, b))}</td></tr>"
            return r

        def sizes_txt(xs):
            xs = [f"{s:,}" for s in xs]
            return "" if not xs else (xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1])

        yr = [(s, cost(A, s), cost(B, s)) for s in sizes]
        a_w = [s for s, a, b in yr if win(a, b) == A["name"]]
        b_w = [s for s, a, b in yr if win(a, b) == B["name"]]
        free_bits = []
        if a_w:
            free_bits.append(f"{html.escape(A['name'])} at {sizes_txt(a_w)}")
        if b_w:
            free_bits.append(f"{html.escape(B['name'])} at {sizes_txt(b_w)}")
        free_line = ("With yearly billing, the cheaper one for a free newsletter is " + "; ".join(free_bits) + " subscribers.") if free_bits else ""

        def fee_desc(p):
            fm = p["fee_model"]
            if fm["type"] == "own_processing":
                return f"{p['name']} charges {fm['pct']}% + ${fm['fixed']:.2f} per transaction"
            if fm["type"] == "stripe":
                return f"{p['name']} takes {fm['pct']:g}% (Stripe's {pr['stripe_pct']}% + ${pr['stripe_fixed']:.2f} per payment still applies)"
            return f"{p['name']}: {fm['label']}"

        def paid_plan_note(p):
            fp = p["free_plan"]
            if fp["paid_subscriptions"] and fp["max_subscribers"] != 0:
                return f"{p['name']} allows them on its free plan"
            names = [pl["name"] for pl in p["plans"] if pl["paid_subscriptions"]]
            return f"{p['name']} needs {' or '.join(names)} for them"

        def fees_both():
            fa, fb = A["fee_model"], B["fee_model"]
            if fa["type"] == fb["type"] == "stripe" and fa["pct"] == fb["pct"]:
                return f"Both take {fa['pct']:g}% of paid-subscription revenue; Stripe's {pr['stripe_pct']}% + ${pr['stripe_fixed']:.2f} per payment still applies"
            return f"{fee_desc(A)}; {fee_desc(B)}"

        comparable = A["fee_model"]["type"] != "not_compared" and B["fee_model"]["type"] != "not_compared"
        paid_html, paid_line = "", ""
        if comparable:
            pr_rows, pa_w, pb_w = "", [], []
            for s in sizes:
                n = int(s * paid_share)
                a, b = cost(A, s, n, paid_price), cost(B, s, n, paid_price)
                w = win(a, b)
                (pa_w if w == A["name"] else pb_w if w == B["name"] else []).append(s)
                pr_rows += f"<tr><td>{s:,}</td><td>{n:,} (${n*paid_price:,}/mo)</td><td>{cell(a)}</td><td>{cell(b)}</td><td>{html.escape(w)}</td></tr>"
            bits = []
            if pa_w:
                bits.append(f"{html.escape(A['name'])} at {sizes_txt(pa_w)}")
            if pb_w:
                bits.append(f"{html.escape(B['name'])} at {sizes_txt(pb_w)}")
            paid_line = (f"<li><strong>Charging readers:</strong> {html.escape(paid_plan_note(A))}; {html.escape(paid_plan_note(B))}. "
                         f"{html.escape(fees_both())}. In our example ({int(paid_share*100)}% of readers paying ${paid_price}/month), the cheaper one is "
                         + "; ".join(bits) + " subscribers.</li>")
            paid_html = f"""
<h2>Paid newsletter example: {int(paid_share*100)}% of readers pay ${paid_price}/month</h2>
<div class="scroll"><table class="grid-table"><thead><tr><th>Subscribers</th><th>Paying readers</th><th>{html.escape(A['name'])} total / month</th><th>{html.escape(B['name'])} total / month</th><th>Cheaper</th></tr></thead><tbody>{pr_rows}</tbody></table></div>
<p class="fine">Totals are the cheapest plan that allows paid subscriptions (yearly billing) plus fees. {html.escape(fees_both())}. One card payment per paying reader per month is assumed. Your own numbers will differ; try them in the <a href="index.html">cost calculator</a>.</p>
"""
        else:
            skip = [p["name"] for p in (A, B) if p["fee_model"]["type"] == "not_compared"]
            paid_line = f"<li><strong>Charging readers:</strong> {html.escape(' and '.join(skip))} paid-newsletter costs aren't in our data yet, so this page compares free newsletters only.</li>"

        pp_head = "".join(f"<th>{html.escape(P[pid]['name'])} {html.escape(pn)}</th>" for pid, pn in plan_pairs)
        pp_rows = ""
        for s in sizes:
            vals = [plan_price(P[pid], pn, s, 1) for pid, pn in plan_pairs]
            pp_rows += f"<tr><td>{s:,}</td>" + "".join(f"<td>{money(v) if v is not None else '–'}</td>" for v in vals) + "</tr>"
        notes = " ".join(html.escape(pl["monthly_factor_note"]) for p in (A, B) for pl in p["plans"] if pl.get("monthly_factor_note"))
        others = " · ".join(f'<a href="{f}">{html.escape(t)}</a>' for f, t in COMPARISONS if f != fname)
        guides = ", ".join(f'<a href="{g}">{html.escape(t)}</a>' for g, t in PRICING_GUIDES if g.split("-")[0] in (aid, bid))
        body = f"""
<h1>{html.escape(A['name'])} vs {html.escape(B['name'])}: what each costs at every list size</h1>
<p class="lede">{lede} Prices are from each vendor's own pricing page, checked on {DATA['verified_on']}.</p>
{disclosure_box('')}
<h2>The short version</h2>
<ul>
<li><strong>Free plans:</strong> {html.escape(A['name'])}: {html.escape(A['free_plan']['summary'])} {html.escape(B['name'])}: {html.escape(B['free_plan']['summary'])}</li>
<li><strong>Free newsletter:</strong> {free_line}</li>
{paid_line}
{"".join(f"<li>{x}</li>" for x in extra_points)}
</ul>

<h2>Free newsletter, yearly billing (monthly equivalent)</h2>
<div class="scroll"><table class="grid-table"><thead><tr><th>Subscribers</th><th>{platform_link(A)}</th><th>{platform_link(B)}</th><th>Cheaper</th></tr></thead><tbody>{rows('annual')}</tbody></table></div>

<h2>Free newsletter, month-to-month billing</h2>
<div class="scroll"><table class="grid-table"><thead><tr><th>Subscribers</th><th>{html.escape(A['name'])}</th><th>{html.escape(B['name'])}</th><th>Cheaper</th></tr></thead><tbody>{rows('monthly')}</tbody></table></div>
<p class="fine">The cheapest plan that holds the list is used for each platform. "–" means no plan for that size in our data. Both vendors price in tiers, so a list slightly over a tier limit moves to the next price.</p>
{paid_html}
<h2>Plan against plan, yearly billing</h2>
<div class="scroll"><table class="grid-table"><thead><tr><th>Subscribers</th>{pp_head}</tr></thead><tbody>{pp_rows}</tbody></table></div>
<p class="fine">{notes} Plan features differ, so compare what each plan includes on the vendor's pricing page before choosing on price.</p>
<div class="ctas">{cta(A, DATA['verified_on'])}{cta(B, DATA['verified_on'])}</div>

<h2>Related</h2>
<p>Price guides: {guides}. Other comparisons: {others}. Or run your own numbers in the <a href="index.html">cost calculator</a>. Every price change we find goes in the <a href="changelog.html">price change log</a>.</p>
{hands_on_line([A["id"], B["id"]], only=" and limits")}
"""
        year = DATA["verified_on"][:4]
        pages.append((fname, title or f"{A['name']} vs {B['name']} Cost at Every List Size ({year})",
                      desc or f"{A['name']} vs {B['name']} prices side by side from {sizes[0]:,} to {sizes[-1]:,} subscribers, yearly and monthly, using prices verified {DATA['verified_on']}.",
                      body, None))

    _gh, _bh = P["ghost"], P["beehiiv"]
    _gh_paid = [pl for pl in _gh["plans"] if pl["paid_subscriptions"]]
    _gh_nopaid = [pl["name"] for pl in _gh["plans"] if not pl["paid_subscriptions"]]
    pair_page("ghost", "beehiiv", "ghost-vs-beehiiv-cost.html",
              [1000, 2500, 5000, 10000, 25000, 50000, 100000],
              [("ghost", "Publisher"), ("beehiiv", "Lite"), ("ghost", "Business"), ("beehiiv", "Pro")],
              "Ghost(Pro) and beehiiv both take a 0% cut of paid subscriptions, so for a paid newsletter the difference comes down to the plan price at your list size. This page puts their published prices side by side, for a free newsletter and for one that charges readers.",
              [f"<strong>Members vs subscribers:</strong> Ghost(Pro) prices by members (free and paying sign-ups together); beehiiv prices by subscribers. Both count everyone on your list.",
               f"<strong>Ghost(Pro) Starter</strong> ({money(_gh['plans'][0]['tiers'][0][1])}/month billed yearly, up to {_gh['plans'][0]['tiers'][0][0]:,} members) is the cheapest Ghost(Pro) plan but doesn't include paid memberships; {' and '.join(html.escape(pl['name']) for pl in _gh_paid)} do. Ghost's pricing page shows Business at its {_gh_paid[-1]['tiers'][0][0]:,}-member price for smaller lists."],
              title="Ghost(Pro) vs beehiiv Cost for Free and Paid Newsletters (" + DATA["verified_on"][:4] + ")",
              desc="Ghost(Pro) vs beehiiv prices side by side from 1,000 to 100,000 subscribers, for free and paid newsletters (both take 0%), using prices verified " + DATA["verified_on"] + ".")

    _ml = P["mailerlite"]
    pair_page("mailerlite", "beehiiv", "mailerlite-vs-beehiiv-cost.html",
              [500, 1000, 2500, 5000, 10000, 25000, 50000, 100000],
              [("mailerlite", "Comfort"), ("beehiiv", "Lite"), ("mailerlite", "Power"), ("beehiiv", "Pro")],
              "MailerLite is an email marketing tool priced by subscribers; beehiiv is a newsletter platform with a website built in. This page puts their published prices side by side from 500 to 100,000 subscribers.",
              [f"<strong>Smallest paid plans:</strong> MailerLite {html.escape(_ml['plans'][0]['name'])} starts at {money(_ml['plans'][0]['tiers'][0][1])}/month billed yearly for up to {_ml['plans'][0]['tiers'][0][0]:,} subscribers; beehiiv {html.escape(_bh['plans'][0]['name'])} starts at {money(_bh['plans'][0]['tiers'][0][1])}/month billed yearly for up to {_bh['plans'][0]['tiers'][0][0]:,}."],
              title="MailerLite vs beehiiv Pricing Compared at Every List Size (" + DATA["verified_on"][:4] + ")")

    _kt, _sy = P["kit"], P["systemeio"]
    _sy_free = _sy["free_plan"]["max_subscribers"]
    _kt_free = _kt["free_plan"]["max_subscribers"]
    _sy_first = _sy["plans"][0]
    _sy_cap = max(t[0] for pl in _sy["plans"] for t in pl["tiers"])
    _sy_unl = next(pl for pl in _sy["plans"] if any(t[0] == _sy_cap for t in pl["tiers"]))
    _kt_cr = next(pl for pl in _kt["plans"] if pl["name"] == "Creator")
    _kt_next = next(t for t in _kt_cr["tiers"] if t[0] > _kt_free)
    pair_page("kit", "systemeio", "kit-vs-systemeio-cost.html",
              [1000, 2000, 2500, 5000, 10000, 15000, 25000, 50000],
              [("kit", "Creator"), ("kit", "Pro")] + [("systemeio", pl["name"]) for pl in _sy["plans"]],
              f"Kit (formerly ConvertKit) and systeme.io both let you charge readers on their free plans, but they price paid plans very differently: Kit steps up in subscriber tiers, while systeme.io has {len(_sy['plans'])} plans set by contact count, the largest with no cap in our data. This page puts their published prices side by side from 1,000 to 50,000 subscribers.",
              [f"<strong>Both free up to {_sy_free:,}:</strong> for a free newsletter, both cost $0 up to {_sy_free:,} subscribers. Past that, Kit's free plan continues to {_kt_free:,}, while systeme.io moves to {html.escape(_sy_first['name'])} ({money(_sy_first['tiers'][0][1])}/month billed yearly, up to {_sy_first['tiers'][0][0]:,} contacts).",
               f"<strong>Past Kit's free plan:</strong> Kit Creator is {money(_kt_next[1])}/month billed yearly up to {_kt_next[0]:,} subscribers and {money(_kt_cr['tiers'][-1][1])} up to {_kt_cr['tiers'][-1][0]:,} (the largest size in our data). systeme.io {html.escape(_sy_unl['name'])} stays at {money(_sy_unl['tiers'][0][1])}/month billed yearly, with no contact cap in our data.",
               "<strong>Contacts vs subscribers:</strong> systeme.io prices by contacts (everyone on your list); Kit prices by subscribers. This page treats the two numbers as the same.",
               f"<strong>systeme.io yearly prices</strong> are calculated from its \"2 months free\" offer on yearly billing."],
              title="Kit vs systeme.io Cost for Free and Paid Newsletters (" + DATA["verified_on"][:4] + ")",
              desc="Kit (ConvertKit) vs systeme.io prices side by side from 1,000 to 50,000 subscribers, for free and paid newsletters, yearly and monthly, using prices verified " + DATA["verified_on"] + ".")

    # ---- single-platform pricing pages (all numbers from platforms.json)
    def tier_price(plan, s, idx):
        for t in plan["tiers"]:
            if s <= t[0]:
                return t[idx]
        return None

    def cheapest_other(p, s, billing="annual"):
        best = None
        for q in DATA["platforms"]:
            if q["id"] in (p["id"], "substack"):
                continue
            c = cost(q, s, billing=billing)
            if "total" in c and (best is None or c["total"] < best[1]["total"]):
                best = (q, c)
        return best

    def pricing_page(pid, fname, extra_note="", size_labels=None, unit="subscribers", title=None, desc=None, extra_related=""):
        size_labels = size_labels or {}
        p = P[pid]
        fp = p["free_plan"]
        sizes = sorted({t[0] for pl in p["plans"] for t in pl["tiers"]})
        head = "".join(f"<th>{html.escape(pl['name'])}<br><small>yearly</small></th><th>{html.escape(pl['name'])}<br><small>monthly</small></th>" for pl in p["plans"])
        rows = ""
        for s in sizes:
            cells = ""
            for pl in p["plans"]:
                y, m = tier_price(pl, s, 1), tier_price(pl, s, 2)
                cells += f"<td>{money(y) if y is not None else '–'}</td><td>{money(m) if m is not None else '–'}</td>"
            rows += f"<tr><td>{html.escape(size_labels.get(s, f'{s:,}'))}</td>{cells}</tr>"
        entry = p["plans"][0]
        e_y, e_m = entry["tiers"][0][1], entry["tiers"][0][2]
        savings = [round((1 - t[1] / t[2]) * 100) for t in entry["tiers"] if t[2]]
        save_txt = f"{min(savings)}%" if min(savings) == max(savings) else f"{min(savings)}-{max(savings)}%"
        fm = p["fee_model"]
        pr = DATA["processing"]
        if fm["type"] == "own_processing":
            fee_txt = f"{p['name']} charges {fm['pct']}% + ${fm['fixed']:.2f} per transaction on paid subscriptions."
        elif fm["type"] == "stripe":
            fee_txt = f"{p['name']} takes {fm['pct']:g}% of paid-subscription revenue; Stripe's standard {pr['stripe_pct']}% + ${pr['stripe_fixed']:.2f} per payment still applies."
        else:
            fee_txt = html.escape(fm["label"]) + "."
        # what each step up costs, and the cheapest alternative at the same size
        cmp_sizes = [s for s in [1000, 5000, 10000, 25000, 50000, 100000] if "total" in cost(p, s)]
        cmp_rows = ""
        for s in cmp_sizes:
            c = cost(p, s)
            o = cheapest_other(p, s)
            other = f"{html.escape(o[0]['name'])} {html.escape(o[1]['plan'])}: {money(o[1]['total'])}" if o else "–"
            cmp_rows += f"<tr><td>{s:,}</td><td>{money(c['total'])}<small>{html.escape(c['plan'])}</small></td><td>{other}</td></tr>"
        notes = " ".join(html.escape(pl["monthly_factor_note"]) for pl in p["plans"] if pl.get("monthly_factor_note"))
        if p.get("annual_note"):
            notes += " " + html.escape(p["annual_note"])
        year = DATA["verified_on"][:4]
        plan_names = ", ".join(pl["name"] for pl in p["plans"])
        fm_name = f" (formerly {p['formerly']})" if p.get("formerly") else ""
        if fp["max_subscribers"] is None:
            q_free = "It's free at any list size."
        elif fp["max_subscribers"] == 0:
            q_free = f"There's no free plan."
        else:
            q_free = f"It's free up to {fp['max_subscribers']:,} {unit}."
        q_at = []
        for qs in (10000, 25000):
            qc = cost(p, qs)
            if "total" in qc:
                q_at.append(f"at {qs:,} {unit} the cheapest option is {money(qc['total'])}/month ({html.escape(qc['plan'])})")
        q_at_txt = (" With yearly billing, " + " and ".join(q_at) + ".") if q_at else ""
        answer = (f'<div class="answer"><p><strong>How much does {html.escape(p["name"])} cost?</strong> {q_free} '
                  f'Paid plans start at {money(e_y)}/month billed yearly ({money(e_m)} month to month) for up to {entry["tiers"][0][0]:,} {unit}.{q_at_txt}</p></div>')
        body = f"""
<h1>{html.escape(p['name'])}{html.escape(fm_name)} pricing explained: what you'll pay at every list size</h1>
<p class="lede">{html.escape(p['name'])} prices depend on how many {unit} you have and on whether you pay yearly or monthly. This page lists every price on {html.escape(p['name'])}'s own <a href="{html.escape(p['pricing_url'])}" rel="noopener" target="_blank">pricing page</a>, checked on {DATA['verified_on']}.</p>
{disclosure_box('')}
{answer}
{cta(p, DATA['verified_on'])}
<h2>The short version</h2>
<ul>
<li><strong>Free plan:</strong> {html.escape(fp['summary'])} {"You can charge readers on the free plan." if fp["paid_subscriptions"] else ("Paid subscriptions need a paid plan." if fm["type"] != "not_compared" else "")}</li>
<li><strong>Paid plans:</strong> {html.escape(plan_names)}. The cheapest starts at {money(e_y)}/month billed yearly ({money(e_m)} month to month) for up to {entry['tiers'][0][0]:,} {unit}.</li>
<li><strong>Yearly billing</strong> saves about {save_txt} on the {html.escape(entry['name'])} plan, depending on list size.</li>
<li><strong>Paid newsletters:</strong> {fee_txt}</li>
</ul>
<h2>{html.escape(p['name'])} price by list size</h2>
<div class="scroll"><table class="grid-table"><thead><tr><th>{unit.capitalize()} up to</th>{head}</tr></thead><tbody>{rows}</tbody></table></div>
<p class="fine">"Yearly" is the monthly equivalent when billed yearly. "–" means that plan isn't offered at that size in our data. {notes} {extra_note}</p>
<h2>How {html.escape(p['name'])} compares at the same size</h2>
<p>For a free newsletter on yearly billing, here is {html.escape(p['name'])}'s cheapest option next to the cheapest option on any other platform we track (Substack excluded, since it's free until you charge):</p>
<div class="scroll"><table class="grid-table"><thead><tr><th>Subscribers</th><th>{platform_link(p)}</th><th>Cheapest elsewhere</th></tr></thead><tbody>{cmp_rows}</tbody></table></div>
<p class="fine">Plans differ in features, so the cheapest price isn't automatically the best fit. Run your own numbers, including paid subscribers, in the <a href="index.html">cost calculator</a>.</p>
{cta(p, DATA['verified_on'])}
<h2>Related</h2>
<ul>
{"".join(f'<li><a href="{f}">{html.escape(t)} cost compared</a></li>' for f, t in COMPARISONS if f != "substack-fees.html" and p["id"] in f.replace("-cost.html", "").split("-vs-"))}
<li><a href="cheapest-newsletter-platform-1000-subscribers.html">Cheapest newsletter platform for 1,000 subscribers</a></li>
<li><a href="cheapest-newsletter-platform-5000-subscribers.html">Cheapest newsletter platform for 5,000 subscribers</a></li>
<li><a href="cheapest-newsletter-platform-10000-subscribers.html">Cheapest newsletter platform for 10,000 subscribers</a></li>
<li><a href="cheapest-newsletter-platform-25000-subscribers.html">Cheapest newsletter platform for 25,000 subscribers</a></li>
<li>Other price guides: {", ".join(f'<a href="{g}">{html.escape(t)}</a>' for g, t in PRICING_GUIDES if g != fname)}</li>
{extra_related}<li><a href="free-plans.html">Free plans compared</a></li>
<li><a href="changelog.html">Price change log</a></li>
</ul>
{test_section(p) or f"<p>We haven't run hands-on tests of {html.escape(p['name'])} yet, so this page covers published prices and limits only.</p>"}
"""
        pages.append((fname, title or f"{p['name']} Pricing {year}{fm_name}: Every Plan and List Size Explained",
                      desc or f"{p['name']}{fm_name} pricing at every subscriber count: free plan limit, {plan_names} prices on yearly and monthly billing, and paid-newsletter fees. Verified {DATA['verified_on']}.", body, None))

    _yr = DATA["verified_on"][:4]
    pricing_page("kit", "kit-pricing.html",
                 title=f"Kit Pricing & Plans {_yr} (formerly ConvertKit): Free, Creator and Pro at Every List Size",
                 desc=f"What each Kit (ConvertKit) plan costs: free up to {P['kit']['free_plan']['max_subscribers']:,} subscribers, then Creator and Pro prices from {min(t[0] for pl in P['kit']['plans'] for t in pl['tiers']):,} to {max(t[0] for pl in P['kit']['plans'] for t in pl['tiers']):,} subscribers, yearly and monthly, plus Kit's paid-newsletter fee. Verified {DATA['verified_on']}.")
    pricing_page("beehiiv", "beehiiv-pricing.html",
                 extra_related='<li><a href="beehiiv-discount.html">beehiiv discount and promo codes: what actually lowers the price</a></li>\n')
    pricing_page("mailerlite", "mailerlite-pricing.html")
    _g = P["ghost"]
    _g_nopaid = [pl["name"] for pl in _g["plans"] if not pl["paid_subscriptions"]]
    _g_paid = [pl["name"] for pl in _g["plans"] if pl["paid_subscriptions"]]
    _g_start = next(pl for pl in _g["plans"] if pl["name"] == "Starter")
    pricing_page("ghost", "ghost-pricing.html", title=f"Ghost Pro Pricing {_yr}: Ghost(Pro) Starter, Publisher and Business Plans by Member Count",
                 desc=f"What Ghost(Pro) costs per month from {min(t[0] for pl in P['ghost']['plans'] for t in pl['tiers']):,} to {max(t[0] for pl in P['ghost']['plans'] for t in pl['tiers']):,} members: Starter, Publisher and Business prices on yearly and monthly billing, and Ghost's {P['ghost']['fee_model']['pct']:g}% fee on paid memberships. Verified {DATA['verified_on']}.",
                 extra_note=
                 f"Starter is listed up to {_g_start['tiers'][-1][0]:,} members only. "
                 f"Paid memberships need {' or '.join(_g_paid)}; {', '.join(_g_nopaid)} does not include them. "
                 f"Ghost's pricing page shows the Business price below {_g['plans'][-1]['tiers'][0][0]:,} members at its {_g['plans'][-1]['tiers'][0][0]:,}-member rate. "
                 "Self-hosting Ghost is free software but you pay for and run your own server, which isn't priced here.")

    _s = P["systemeio"]
    _s_cap = max(t[0] for pl in _s["plans"] for t in pl["tiers"])
    _s_unl = next(pl["name"] for pl in _s["plans"] if any(t[0] == _s_cap for t in pl["tiers"]))
    pricing_page("systemeio", "systemeio-pricing.html",
                 f"systeme.io prices by contacts (everyone on your list), not only newsletter subscribers. "
                 f"\"No limit\" is the {_s_unl} plan, which has no contact cap. "
                 "The free plan also includes funnels, courses and checkout, so you're not paying for email alone. "
                 "Payment processor fees still apply; the fee above assumes Stripe's standard US rate.",
                 size_labels={_s_cap: "No limit"}, unit="contacts")

    # ---- beehiiv discounts (numbers from platforms.json: tiers, referral_offer, yearly_saving_claim)
    _b = P["beehiiv"]
    _ro = _b.get("referral_offer")
    _ys = _b.get("yearly_saving_claim")
    if _ro:
        _bf = _b["free_plan"]["max_subscribers"]
        _pct, _mon = _ro["discount_pct"], _ro["discount_months"]
        _lite = next(pl for pl in _b["plans"] if pl["name"] == "Lite")
        _show = [t for t in _lite["tiers"] if t[0] in (1000, 2500, 5000, 10000, 25000, 50000, 100000)]
        d_rows = ""
        for s_, y_, m_ in _show:
            yearly_save = (m_ - y_) * 12
            ref_save = m_ * _pct / 100 * _mon
            first_year_ref = m_ * 12 - ref_save
            d_rows += (f"<tr><td>{s_:,}</td><td>{money(m_)}</td><td>{money(y_)}</td>"
                       f"<td>{money(yearly_save)}</td><td>{money(ref_save)}</td><td>{money(first_year_ref)}</td><td>{money(y_ * 12)}</td></tr>")
        pro = next(pl for pl in _b["plans"] if pl["name"] == "Pro")
        p_rows = ""
        for s_, y_, m_ in [t for t in pro["tiers"] if t[0] in (1000, 10000, 25000, 100000)]:
            p_rows += f"<tr><td>{s_:,}</td><td>{money(m_)}</td><td>{money(y_)}</td><td>{money((m_ - y_) * 12)}</td><td>{money(m_ * _pct / 100 * _mon)}</td></tr>"
        alt_rows = ""
        for s_ in (5000, 10000, 25000, 50000):
            c = cost(_b, s_)
            o = cheapest_other(_b, s_)
            if "total" in c and o:
                alt_rows += f"<tr><td>{s_:,}</td><td>{money(c['total'])}<small>{html.escape(c['plan'])}</small></td><td>{html.escape(o[0]['name'])} {html.escape(o[1]['plan'])}: {money(o[1]['total'])}</td></tr>"
        l1 = _lite["tiers"][0]
        _yearly_wins = all((m_ - y_) * 12 > m_ * _pct / 100 * _mon for _, y_, m_ in _show)
        _cmp_txt = ("Over a full year, yearly billing saves more than the referral offer at every Lite list size below."
                    if _yearly_wins else "Which saves more depends on your list size; see the table below.")
        body = f"""
<h1>beehiiv discount, coupon and promo codes: what actually lowers the price</h1>
<p class="lede">People search for a beehiiv coupon before they upgrade. Here is what beehiiv's own pages offered when we checked on {html.escape(_ro['verified_on'])}, and how much each option saves at your list size. Every price comes from beehiiv's <a href="{html.escape(_b['pricing_url'])}" rel="noopener" target="_blank">pricing page</a>.</p>
{disclosure_box('')}
<div class="answer"><p><strong>Is there a beehiiv discount code?</strong> beehiiv's pricing page showed no coupon or promo code when we checked. The ways to pay less are: stay on the free plan (up to {_bf:,} subscribers), pay yearly, and the partner-referral offer: according to beehiiv's <a href="{html.escape(_ro['source'])}" rel="noopener" target="_blank">partner page</a>, customers referred through a partner link get a {_ro['trial_days']}-day trial and {_pct}% off their first {_mon} months. {_cmp_txt}</p></div>
<h2>The short version</h2>
<ul>
<li><strong>Free plan:</strong> {html.escape(_b['free_plan']['summary'])} If you're under {_bf:,} subscribers and don't charge readers, the cheapest beehiiv is $0.</li>
<li><strong>Yearly billing:</strong> {("beehiiv's pricing FAQ says: &ldquo;" + html.escape(_ys['text']) + "&rdquo;") if _ys else ''} On Lite at {l1[0]:,} subscribers that's {money(l1[1])}/month instead of {money(l1[2])}, or {money((l1[2] - l1[1]) * 12)} a year.</li>
<li><strong>Partner referral offer:</strong> {_pct}% off the first {_mon} months. On Lite at {l1[0]:,} subscribers, month to month, that's {money(l1[2] * _pct / 100 * _mon)} in total. {html.escape(_ro.get('note', ''))}</li>
<li><strong>Coupon sites:</strong> we only list offers shown on beehiiv's own pages. We can't vouch for codes posted elsewhere.</li>
</ul>
<h2>What each option saves on beehiiv Lite</h2>
<div class="scroll"><table class="grid-table"><thead><tr><th>Subscribers up to</th><th>Monthly price</th><th>Yearly billing (per month)</th><th>Yearly billing saves / year</th><th>Referral offer saves ({_pct}% &times; {_mon} months)</th><th>First year, monthly + referral offer</th><th>First year, yearly billing</th></tr></thead><tbody>{d_rows}</tbody></table></div>
<p class="fine">Referral savings are calculated on month-to-month prices, because beehiiv's partner page doesn't say whether the {_pct}% applies to yearly billing. Whether the offer can be combined with yearly billing isn't stated either. Taxes not included.</p>
<h2>Same numbers for beehiiv Pro</h2>
<div class="scroll"><table class="grid-table"><thead><tr><th>Subscribers up to</th><th>Monthly price</th><th>Yearly billing (per month)</th><th>Yearly billing saves / year</th><th>Referral offer saves</th></tr></thead><tbody>{p_rows}</tbody></table></div>
<h2>Is beehiiv the cheapest option at your size?</h2>
<p>A discount matters less than picking the right platform. For a free newsletter on yearly billing, here is beehiiv's cheapest plan next to the cheapest plan on any other platform we track (Substack excluded):</p>
<div class="scroll"><table class="grid-table"><thead><tr><th>Subscribers</th><th>{platform_link(_b)}</th><th>Cheapest elsewhere</th></tr></thead><tbody>{alt_rows}</tbody></table></div>
<p class="fine">Plans differ in features, so the cheapest price isn't automatically the best fit. beehiiv takes {_b['fee_model']['pct']:g}% of paid-subscription revenue (Stripe fees still apply); for paid newsletters, run your numbers in the <a href="index.html">cost calculator</a>.</p>
{cta(_b, DATA['verified_on'])}
<p class="fine">Our beehiiv links are partner (affiliate) links, marked *. beehiiv's partner page says referred customers get the offer above; we haven't gone through beehiiv's checkout ourselves to confirm how it appears. If you'd rather not use our link, go to beehiiv's site directly: the prices on this page are the same either way.</p>
<h2>Related</h2>
<ul>
<li><a href="beehiiv-pricing.html">beehiiv pricing explained</a>: Free, Lite and Pro at every list size</li>
{"".join(f'<li><a href="{f}">{html.escape(t)} cost compared</a></li>' for f, t in COMPARISONS if "beehiiv" in f)}
<li><a href="free-plans.html">Free plans compared</a></li>
<li><a href="changelog.html">Price change log</a></li>
</ul>
{test_section(_b) or "<p>We haven't run hands-on tests of beehiiv yet, so this page covers published prices and beehiiv's published offers only.</p>"}
"""
        pages.append(("beehiiv-discount.html", f"beehiiv Discount, Coupon and Promo Codes ({DATA['verified_on'][:4]}): What Actually Saves Money",
                      f"No beehiiv promo code was shown on beehiiv's pricing page. What does save money: the free plan up to {_bf:,} subscribers, yearly billing, and beehiiv's {_pct}%-off-{_mon}-months partner referral offer, with the savings at each list size. Checked {_ro['verified_on']}.", body, None))

    # ---- cheapest at 10,000 subscribers
    def rank_rows(s, paid=0, price=0, billing="annual", include_substack=True):
        res = []
        for q in DATA["platforms"]:
            if not include_substack and q["id"] == "substack":
                continue
            c = cost(q, s, paid, price, billing)
            if "total" in c:
                res.append((q, c))
        res.sort(key=lambda r: (r[1]["total"], r[0]["name"].lower()))
        return res

    def rows_html(res, show_fees=False):
        out = ""
        for i, (q, c) in enumerate(res):
            fee = f"<td>{money(c['fees'])}</td>" if show_fees else ""
            out += f"<tr{' class=\"best\"' if c['total'] == res[0][1]['total'] else ''}><td>{platform_link(q)}</td><td>{html.escape(c['plan'])}</td><td>{money(c['base'])}</td>{fee}<td>{money(c['total'])}</td></tr>"
        return out

    def names_and(names):
        names = list(names)
        return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]

    def cheapest_page(S, over, paid_n, paid_price, lede, over_note):
        free_y = rank_rows(S)
        free_m = rank_rows(S, billing="monthly")
        paid_y = rank_rows(S, paid_n, paid_price)
        over_y = rank_rows(over, include_substack=False)
        nosub = [r for r in free_y if r[0]["id"] != "substack"]
        low = nosub[0][1]["total"]
        tied = [r for r in nosub if r[1]["total"] == low]
        if low == 0:
            free_txt = (f"{names_and(html.escape(r[0]['name']) for r in tied)} "
                        f"{'all have free plans that hold' if len(tied) > 1 else 'has a free plan that holds'} {S:,} subscribers, so the cheapest price is $0 a month. "
                        "Substack is also $0 if you never charge.")
        else:
            free_txt = (f"{names_and(html.escape(r[0]['name'] + ' ' + r[1]['plan']) for r in tied)} "
                        f"{'are' if len(tied) > 1 else 'is'} cheapest at {money(low)}/month (Substack is also $0 if you never charge).")
        best_paid = paid_y[0]
        olow = over_y[0][1]["total"]
        otied = [r for r in over_y if r[1]["total"] == olow]
        over_txt = (f"{names_and(html.escape(r[0]['name'] + ' ' + r[1]['plan']) for r in otied)} at {money(olow)}/month")
        skipped_paid = [q["name"] for q in DATA["platforms"] if "skip" in cost(q, S, paid_n, paid_price)]
        free_m_nosub = [r for r in free_m if r[0]["id"] != "substack"]
        paid_free_plans = [r for r in paid_y if r[1]["plan"] == "Free" and r[0]["id"] != "substack"]
        body = f"""
<h1>Cheapest newsletter platform for {S:,} subscribers</h1>
<p class="lede">{lede} This page ranks every platform we track by what it costs at exactly {S:,} subscribers, for a free newsletter and for a paid one. Prices verified on each vendor's pricing page on {DATA['verified_on']}.</p>
{disclosure_box('')}
<h2>The short version</h2>
<ul>
<li><strong>Free newsletter:</strong> {free_txt}</li>
<li><strong>Paid newsletter</strong> ({paid_n:,} readers paying ${paid_price}/month): {html.escape(best_paid[0]['name'])} {html.escape(best_paid[1]['plan'])} is cheapest at {money(best_paid[1]['total'])}/month including fees.</li>
<li><strong>Growing past {S:,}?</strong> At {over:,} subscribers the cheapest option is {over_txt}. {over_note}</li>
</ul>

<h2>Free newsletter at {S:,} subscribers, yearly billing</h2>
<div class="scroll"><table class="grid-table"><thead><tr><th>Platform</th><th>Plan</th><th>Plan price</th><th>Total / month</th></tr></thead><tbody>{rows_html(free_y)}</tbody></table></div>

<h2>Free newsletter at {S:,} subscribers, month-to-month billing</h2>
<div class="scroll"><table class="grid-table"><thead><tr><th>Platform</th><th>Plan</th><th>Plan price</th><th>Total / month</th></tr></thead><tbody>{rows_html(free_m)}</tbody></table></div>
<p class="fine">Free plans cost the same either way. The cheapest paid plan at this size on month-to-month billing is {html.escape(next((r[0]['name'] + ' ' + r[1]['plan'] + ' at ' + money(r[1]['total']) + '/month' for r in free_m_nosub if r[1]['total'] > 0), 'not available in our data'))}.</p>

<h2>Paid newsletter: {paid_n:,} paying readers at ${paid_price}/month</h2>
<div class="scroll"><table class="grid-table"><thead><tr><th>Platform</th><th>Plan</th><th>Plan price</th><th>Fees</th><th>Total / month</th></tr></thead><tbody>{rows_html(paid_y, True)}</tbody></table></div>
<p class="fine">Fees are the platform's cut plus card processing, assuming one payment per paying reader per month (Stripe standard {DATA['processing']['stripe_pct']}% + ${DATA['processing']['stripe_fixed']:.2f}; Kit uses its own {P['kit']['fee_model']['pct']}% + ${P['kit']['fee_model']['fixed']:.2f}). {('Free plans that allow paid subscriptions at this size: ' + html.escape(', '.join(r[0]['name'] for r in paid_free_plans)) + '. ') if paid_free_plans else ''}Not shown: {html.escape(', '.join(skipped_paid)) or 'none'} (paid newsletters not compared yet).</p>

<h2>If you'll pass {S:,} soon: prices at {over:,}</h2>
<div class="scroll"><table class="grid-table"><thead><tr><th>Platform</th><th>Plan</th><th>Plan price</th><th>Total / month</th></tr></thead><tbody>{rows_html(over_y)}</tbody></table></div>
<p class="fine">Free newsletter, yearly billing. Free plans have hard subscriber caps and paid plans are priced in tiers, so a few hundred extra subscribers can move you into the next price band.</p>
<p>Different list size? Use the <a href="index.html">cost calculator</a> or see the rankings for {names_and([f'<a href="cheapest-newsletter-platform-{n}-subscribers.html">{n:,}</a>' for n in CHEAPEST_SIZES if n != S])} subscribers. Only comparing two platforms? See {names_and([f'<a href="{f}">{html.escape(t)}</a>' for f, t in COMPARISONS if f != "substack-fees.html"]).replace(" and ", " or ")}. Single-platform price guides: {", ".join(f'<a href="{g}">{html.escape(t.replace(" pricing explained", ""))}</a>' for g, t in PRICING_GUIDES)}. All free-plan limits: <a href="free-plans.html">free plans compared</a>.</p>
{hands_on_line([q["id"] for q in DATA["platforms"]], what="this ranking")}
"""
        pages.append((f"cheapest-newsletter-platform-{S}-subscribers.html", f"Cheapest Newsletter Platform for {S:,} Subscribers (" + DATA["verified_on"][:4] + ")",
                      f"Every newsletter platform ranked by monthly cost at {S:,} subscribers, for free and paid newsletters, using prices verified " + DATA["verified_on"] + ".", body, None))

    CHEAPEST_SIZES = [1000, 5000, 10000, 25000]
    cheapest_page(1000, 3000, 50, 8,
                  "1,000 subscribers is a common first-year goal, and at this size several platforms are still free.",
                  f"Free plans on beehiiv (up to {P['beehiiv']['free_plan']['max_subscribers']:,}) and systeme.io (up to {P['systemeio']['free_plan']['max_subscribers']:,}) stop before that, while Kit's goes to {P['kit']['free_plan']['max_subscribers']:,}, so check where you expect to be in a year.")
    _sys_start = P["systemeio"]["plans"][0]
    cheapest_page(5000, 6000, 250, 8,
                  "5,000 subscribers is past most free plans, so this is often the first list size where you start paying.",
                  f"systeme.io {_sys_start['name']} covers up to {_sys_start['tiers'][0][0]:,} contacts, so a slightly bigger list moves you to its next plan.")
    cheapest_page(10000, 12000, 500, 8,
                  "10,000 subscribers is where many free plans end and prices start to climb.",
                  "Check the next tier before you commit.")
    cheapest_page(25000, 30000, 1250, 8,
                  "25,000 subscribers is well past every capped free plan, so here the monthly bill depends entirely on each platform's paid tiers.",
                  f"systeme.io {_s_unl} has no contact cap in our data, so its price stays the same as you grow; the other platforms step up in tiers.")

    # ---- hands-on test results (only when TA has written at least one results file)
    if TESTS:
        tested = [P[k] for k in sorted(TESTS, key=lambda k: P[k]["name"].lower()) if k in P]
        secs = "".join(test_section(p) for p in tested)
        body = f"""
<h1>Hands-on newsletter platform tests</h1>
<p class="lede">We ran the same fixed tasks on each platform's plan, with the same inputs, and recorded what happened, including what went wrong. Platforms tested so far: {html.escape(', '.join(p['name'] for p in tested))}.</p>
{disclosure_box('')}
{secs}
<p>How the test works: <a href="methodology.html#lab">our method</a>. Prices for every platform: <a href="index.html">cost calculator</a>.</p>
"""
        pages.append(("hands-on-tests.html", "Newsletter Platform Hands-on Tests: Same Tasks on Every Platform",
                      "Results of running the same fixed tasks (first issue, sign-up form, inbox placement, import/export, welcome sequence) on each newsletter platform.", body, None))

    # ---- methodology
    srcs = "".join(f"<li>{html.escape(p['name'])}: <a href='{html.escape(p['pricing_url'])}' rel='noopener' target='_blank'>{html.escape(p['pricing_url'])}</a></li>" for p in DATA["platforms"])
    body = f"""
<h1>How we verify prices (and how we'll test platforms)</h1>
<h2>Price verification</h2>
<ol>
<li>Prices are read from each vendor's own public pricing page, at every list size the page's own slider offers, for both yearly and monthly billing where shown.</li>
<li>Each price is stored with the date it was checked. The current data was checked on <strong>{DATA['verified_on']}</strong>.</li>
<li>Where a vendor only states a discount (for example "2 months free" on yearly billing), we calculate the other price and say so.</li>
<li>Where we couldn't verify a number, we show "–" instead of guessing.</li>
<li>Prices are re-checked regularly, and every change is recorded in the <a href="changelog.html">price change log</a>.</li>
</ol>
<p>Sources used:</p><ul>{srcs}</ul>
<h2 id="lab">Fixed-task platform tests{"" if TESTS else " (coming soon)"}</h2>
<p>Price is only half of the decision. We're preparing a repeatable test that runs the same tasks on each platform's free plan, with the same inputs, and publishes the raw results:</p>
<ol>
<li>Time to go from sign-up to a sent first issue.</li>
<li>Build and embed a sign-up form on a test page.</li>
<li>Send an identical issue to a fixed set of test inboxes (Gmail, Outlook, Yahoo) and record inbox, promotions or spam placement.</li>
<li>Import and export a test list of 100 addresses, and check what's kept.</li>
<li>Set up a 3-email welcome sequence where the free plan allows it.</li>
</ol>
<p>Results will be dated, repeated on a schedule, and published with what went wrong as well as what worked. We won't claim to have tested anything until a test has actually been run.{(' Results so far: <a href="hands-on-tests.html">hands-on test results</a>.') if TESTS else ''}</p>
"""
    pages.append(("methodology.html", "How We Verify Newsletter Platform Prices", "Our method for checking newsletter platform prices and the fixed-task tests we run on each platform.", body, None))

    # ---- changelog (from data/platforms.json "changelog", newest first)
    entries = "".join(f"<h2>{html.escape(e['date'])}</h2><ul>" + "".join(f"<li>{html.escape(c)}</li>" for c in e["changes"]) + "</ul>" for e in DATA.get("changelog", []))
    body = f"""
<h1>Price change log</h1>
<p>Every time we re-check prices, changes are recorded here, newest first.</p>
{entries}
"""
    pages.append(("changelog.html", "Newsletter Platform Price Change Log", "A dated log of price changes we've found on newsletter platform pricing pages.", body, None))

    # ---- about / disclosure / contact
    pages.append(("about.html", "About " + SITE_NAME, "Who runs Newsletter Cost Lab and why.", f"""
<h1>About {SITE_NAME}</h1>
<p>{SITE_NAME} is an independent site run by one developer based in Japan. It isn't owned by, or paid by, any of the platforms it covers.</p>
<p>The aim is simple: help people starting a newsletter see what each platform will really cost, using numbers anyone can check against the vendor's own pricing page, and, from our upcoming tests, how each one performs on the same tasks.</p>
<p>The site's source and data are public on GitHub, so you can see exactly where each number comes from.</p>
<p>Found a wrong price? Please <a href="contact.html">tell us</a>. Corrections are logged in the <a href="changelog.html">change log</a>.</p>
""", None))
    aff_list = "".join(f"<li>{html.escape(p['name'])}</li>" for p in DATA["platforms"] if p.get("affiliate_url")) or "<li>None at the moment.</li>"
    pages.append(("disclosure.html", "Affiliate Disclosure", "How Newsletter Cost Lab makes money and how affiliate links are marked.", f"""
<h1>Affiliate disclosure</h1>
<p>Some platforms we cover run affiliate programs. If we join one, links to that platform may become affiliate links: if you sign up or buy through them, we may earn a commission, at no extra cost to you.</p>
<p>Affiliate links are always marked with an asterisk (*) right next to the link, and they carry <code>rel="sponsored"</code>.</p>
<p><strong>Affiliate links currently on this site:</strong></p><ul>{aff_list}</ul>
<p><strong>What commissions never change:</strong> the numbers. The calculator and tables sort platforms purely by price from the vendor's own pricing page. A platform that pays us more doesn't rank higher, and a platform with no affiliate program is still included.</p>
""", None))
    aff_names = [p["name"] for p in DATA["platforms"] if p.get("affiliate_url")]
    pages.append(("privacy.html", "Privacy Policy", "What Newsletter Cost Lab collects (very little), how affiliate links work, and how to contact us.", f"""
<h1>Privacy policy</h1>
<p class="fine">Last updated: 2026-11-23</p>
<p>{SITE_NAME} is a small independent site. We don't ask for your name, email address or any other personal details, and we don't run ads.</p>
<h2>What this site collects</h2>
<ul>
<li><strong>No accounts, forms or newsletters.</strong> There is nothing to sign up for here.</li>
<li><strong>No analytics or tracking scripts.</strong> We don't use Google Analytics, advertising pixels or similar tools, and the site itself sets no cookies.</li>
<li><strong>The cost calculator runs in your browser.</strong> The numbers you type are not sent to us or stored anywhere.</li>
</ul>
<h2>Hosting</h2>
<p>The site is hosted on GitHub Pages. Like most web hosts, GitHub may log technical data such as your IP address when your browser requests a page, for security and to run the service. We don't receive or use those logs. See <a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement" rel="noopener" target="_blank">GitHub's privacy statement</a>.</p>
<h2>Search statistics</h2>
<p>We use Google Search Console to see which search terms bring people to the site. It shows only totals (for example, how many times a page appeared in Google results), not who visited.</p>
<h2>Affiliate links</h2>
<p>Some links are affiliate links, marked with an asterisk (*){(': currently ' + ', '.join(html.escape(n) for n in aff_names)) if aff_names else ''}. If you click one, you leave this site, and the platform or its affiliate partner may set a cookie on its own website to record that you came from us. That cookie is governed by that company's privacy policy, not ours. Read more in our <a href="disclosure.html">affiliate disclosure</a>.</p>
<h2>Contact and GitHub</h2>
<p>The <a href="contact.html">contact page</a> points to the site's public GitHub repository. Anything you post there is public and handled under GitHub's terms.</p>
<h2>Changes</h2>
<p>If this policy changes, we'll update this page and the date at the top.</p>
""", None))
    pages.append(("contact.html", "Contact", "How to contact Newsletter Cost Lab.", """
<h1>Contact</h1>
<p>To report a wrong price, suggest a platform or ask a question, open an issue on the site's GitHub repository:</p>
<p><a href="https://github.com/__GH_USER__/__GH_REPO__/issues" rel="noopener" target="_blank">github.com/__GH_USER__/__GH_REPO__/issues</a></p>
<p>Please include the platform, the price you saw and the date.</p>
""", None))

    gh_user = os.environ.get("GH_USER", "")
    gh_repo = os.environ.get("GH_REPO", "")
    for path, title, desc, body, ld in pages:
        out = page(path, title, desc, body, base, ld).replace("__GH_USER__", gh_user).replace("__GH_REPO__", gh_repo)
        with open(os.path.join(OUT, path), "w") as f:
            f.write(out)

    with open(os.path.join(OUT, "404.html"), "w") as f:
        f.write(page("404.html", "Page not found", "Page not found.", '<h1>Page not found</h1><p><a href="index.html">Go to the cost calculator</a>.</p>', base))
    today = DATA["verified_on"]
    urls = "".join(f"<url><loc>{base}{'' if p[0]=='index.html' else p[0]}</loc><lastmod>{today}</lastmod></url>" for p in pages)
    with open(os.path.join(OUT, "sitemap.xml"), "w") as f:
        f.write(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>')
    with open(os.path.join(OUT, "robots.txt"), "w") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {base}sitemap.xml\n")
    open(os.path.join(OUT, ".nojekyll"), "w").close()
    print("built", len(pages) + 1, "pages into", OUT)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("BASE_URL", "https://example.github.io/newsletter-cost-lab/"))
    a = ap.parse_args()
    build(a.base_url if a.base_url.endswith("/") else a.base_url + "/")
