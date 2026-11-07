#!/usr/bin/env python3
"""Build the static site into ./site from data/platforms.json and content/*.html.

Usage: python3 build.py [--base-url https://user.github.io/repo/]
"""
import argparse, html, json, math, os, shutil, datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = json.load(open(os.path.join(ROOT, "data", "platforms.json")))
SITE_NAME = "Newsletter Cost Lab"
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
        if p["id"] == "buttondown":
            return {"skip": "price above 100 subscribers not verified yet"}
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
    return "$0" if x == 0 else ("$" + (f"{x:,.0f}" if x >= 100 else f"{x:,.2f}".rstrip("0").rstrip(".")))

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
<p><a href="{rel}about.html">About</a> · <a href="{rel}disclosure.html">Affiliate disclosure</a> · <a href="{rel}changelog.html">Price change log</a> · <a href="{rel}contact.html">Contact</a></p>
</footer>
</body>
</html>
"""


def platform_link(p, label=None, rel_prefix=""):
    label = html.escape(label or p["name"])
    if p.get("affiliate_url"):
        return f'<a href="{html.escape(p["affiliate_url"])}" rel="sponsored noopener" target="_blank">{label}</a><sup class="aff" title="Affiliate link">*</sup>'
    return f'<a href="{html.escape(p["official_url"])}" rel="noopener" target="_blank">{label}</a>'


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
    with open(os.path.join(OUT, "assets", "platforms.json"), "w") as f:
        json.dump(DATA, f)
    P = {p["id"]: p for p in DATA["platforms"]}
    pages = []

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
<p class="fine">The cheapest plan that holds the list is used. "–" means the platform has no plan for that size in our data, or the price isn't verified yet. Buttondown is free up to 100 subscribers; its paid tiers are not verified yet.</p>

<h2>Before you pick on price alone</h2>
<ul>
<li><strong>Free-plan ceilings differ a lot:</strong> 100 (Buttondown) to 10,000 (Kit) subscribers. See <a href="free-plans.html">the free plan comparison</a>.</li>
<li><strong>Paid newsletters change the maths.</strong> A percentage cut is cheap when you're small and expensive when you grow.</li>
<li><strong>Switching later has a cost.</strong> Paid subscribers on some platforms can't simply be moved. Pick a platform you can stay on for at least a year.</li>
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
<p class="fine">We haven't run hands-on tests of these platforms yet, so this guide is based on published prices and limits only. Hands-on results will be added here once our <a href="../methodology.html#lab">fixed-task tests</a> are published.</p>
"""
    ld = {"@context": "https://schema.org", "@type": "Article", "headline": "How to choose your first newsletter platform: a 6-question checklist",
          "dateModified": DATA["verified_on"], "datePublished": DATA["verified_on"], "author": {"@type": "Organization", "name": SITE_NAME}}
    pages.append(("guides/choose-your-first-newsletter-platform.html", "How to Choose Your First Newsletter Platform (6-Question Checklist)",
                  "A practical checklist for picking your first newsletter tool: list size, paid subscriptions, automations, cost at scale and switching risk.", body, ld))

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
<h2 id="lab">Fixed-task platform tests (coming soon)</h2>
<p>Price is only half of the decision. We're preparing a repeatable test that runs the same tasks on each platform's free plan, with the same inputs, and publishes the raw results:</p>
<ol>
<li>Time to go from sign-up to a sent first issue.</li>
<li>Build and embed a sign-up form on a test page.</li>
<li>Send an identical issue to a fixed set of test inboxes (Gmail, Outlook, Yahoo) and record inbox, promotions or spam placement.</li>
<li>Import and export a test list of 100 addresses, and check what's kept.</li>
<li>Set up a 3-email welcome sequence where the free plan allows it.</li>
</ol>
<p>Results will be dated, repeated on a schedule, and published with what went wrong as well as what worked. We won't claim to have tested anything until a test has actually been run.</p>
"""
    pages.append(("methodology.html", "How We Verify Newsletter Platform Prices", "Our method for checking newsletter platform prices and the fixed-task tests we run on each platform.", body, None))

    # ---- changelog
    body = f"""
<h1>Price change log</h1>
<p>Every time we re-check prices, changes are recorded here, newest first.</p>
<h2>{DATA['verified_on']}</h2>
<ul><li>First full verification of Kit, beehiiv, MailerLite, Ghost(Pro), Substack, systeme.io and Buttondown free-plan limits.</li></ul>
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
