// Newsletter cost calculator. Mirrors cost() in build.py.
(function () {
  var DATA = null;
  var $ = function (id) { return document.getElementById(id); };

  function money(x) {
    if (x === 0) return "$0";
    return "$" + (x >= 100 ? Math.round(x).toLocaleString("en-US") : (Math.round(x * 100) / 100).toFixed(2).replace(/\.00$/, ""));
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  function options(p, subs, paidNeeded, billing) {
    var idx = billing === "annual" ? 1 : 2, out = [], fp = p.free_plan;
    if (fp.max_subscribers === null || subs <= (fp.max_subscribers || 0)) {
      if (!paidNeeded || fp.paid_subscriptions) out.push(["Free", 0]);
    }
    p.plans.forEach(function (plan) {
      if (paidNeeded && !plan.paid_subscriptions) return;
      for (var i = 0; i < plan.tiers.length; i++) {
        if (subs <= plan.tiers[i][0]) { out.push([plan.name, plan.tiers[i][idx]]); break; }
      }
    });
    return out;
  }

  function cost(p, subs, paidSubs, price, billing) {
    var paidNeeded = paidSubs > 0, fm = p.fee_model;
    if (paidNeeded && fm.type === "not_compared") return { skip: "paid newsletters not compared yet" };
    var opts = options(p, subs, paidNeeded, billing);
    if (!opts.length) return { skip: "no plan for this list size in our data" };
    var best = opts.reduce(function (a, b) { return b[1] < a[1] ? b : a; });
    var rev = paidSubs * price, fees = 0;
    if (paidNeeded) {
      if (fm.type === "own_processing") fees = rev * fm.pct / 100 + paidSubs * fm.fixed;
      else fees = rev * (fm.pct + DATA.processing.stripe_pct) / 100 + paidSubs * DATA.processing.stripe_fixed;
    }
    return { plan: best[0], base: best[1], fees: fees, total: best[1] + fees };
  }

  function link(p) {
    if (p.affiliate_url) return '<a href="' + esc(p.affiliate_url) + '" rel="sponsored noopener" target="_blank">' + esc(p.name) + '</a><sup class="aff" title="Affiliate link">*</sup>';
    return '<a href="' + esc(p.official_url) + '" rel="noopener" target="_blank">' + esc(p.name) + "</a>";
  }

  function num(id) { var v = parseFloat($(id).value); return isFinite(v) && v >= 0 ? v : 0; }

  function render() {
    var subs = Math.round(num("subs")), paid = Math.min(Math.round(num("paid")), subs), price = num("price"), billing = $("billing").value;
    var ok = [], skip = [];
    DATA.platforms.forEach(function (p) {
      var c = cost(p, subs, paid, price, billing);
      if (c.skip) skip.push([p, c.skip]); else ok.push([p, c]);
    });
    ok.sort(function (a, b) { return a[1].total - b[1].total; });
    var rev = paid * price;
    var h = '<div class="scroll"><table class="res"><thead><tr><th>Platform</th><th>Plan</th><th>Plan price</th><th>Fees on paid subs</th><th>Total / month</th>' + (rev > 0 ? "<th>You keep</th>" : "") + "</tr></thead><tbody>";
    ok.forEach(function (r, i) {
      var p = r[0], c = r[1];
      h += '<tr class="' + (i === 0 ? "best" : "") + '"><td>' + link(p) + "</td><td>" + esc(c.plan) + "</td><td>" + money(c.base) + "</td><td>" + (paid ? money(c.fees) : "–") + '</td><td class="total">' + money(c.total) + "</td>" + (rev > 0 ? "<td>" + money(rev - c.total) + "</td>" : "") + "</tr>";
    });
    h += "</tbody></table></div>";
    if (rev > 0) h += '<p class="fine">Paid revenue: ' + money(rev) + "/month from " + paid.toLocaleString("en-US") + " paying readers.</p>";
    if (skip.length) h += '<p class="fine">Not shown: ' + skip.map(function (s) { return esc(s[0].name) + " (" + esc(s[1]) + ")"; }).join("; ") + ".</p>";
    h += '<p class="share"><button type="button" id="copylink">Copy a link to these results</button> <span id="copied" class="fine" aria-live="polite"></span></p>';
    $("result").innerHTML = h;
    updateUrl(subs, paid, price, billing);
    $("copylink").addEventListener("click", copyLink);
  }

  // Shareable links: ?subs=5000&paid=250&price=8&billing=monthly
  function updateUrl(subs, paid, price, billing) {
    try {
      var q = "?subs=" + subs + (paid ? "&paid=" + paid + "&price=" + price : "") + (billing === "monthly" ? "&billing=monthly" : "");
      history.replaceState(null, "", location.pathname + q + location.hash);
    } catch (e) {}
  }
  function copyLink() {
    var url = location.href, done = function () { $("copied").textContent = "Link copied."; };
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(url).then(done, function () { $("copied").textContent = url; }); }
      else { $("copied").textContent = url; }
    } catch (e) { $("copied").textContent = url; }
  }
  function readUrl() {
    try {
      var q = new URLSearchParams(location.search);
      ["subs", "paid", "price"].forEach(function (k) {
        var v = parseFloat(q.get(k));
        if (isFinite(v) && v >= 0 && v <= 10000000) $(k).value = String(v);
      });
      if (q.get("billing") === "monthly" || q.get("billing") === "annual") $("billing").value = q.get("billing");
    } catch (e) {}
  }

  function init() {
    fetch("assets/platforms.json").then(function (r) { return r.json(); }).then(function (d) {
      DATA = d;
      readUrl();
      ["subs", "paid", "price", "billing"].forEach(function (id) { $(id).addEventListener("input", render); $(id).addEventListener("change", render); });
      render();
    }).catch(function () { $("result").innerHTML = "<p>Could not load price data. The tables below still work.</p>"; });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
