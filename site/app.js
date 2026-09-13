/* Looking Glass — the page reads one signed snapshot and renders it. Nothing else.
 *
 * No framework, no bundler, no network call except to files this site serves. There is no input
 * element anywhere in the document and this script never creates one: navigation is links and the
 * URL fragment, which is the whole interaction budget (SPEC-004 R2 — a text box is a place where a
 * citizen secret could be typed, and the listing's second condition is that no such place exists).
 */
(function () {
  "use strict";

  var SNAP = "./snapshot/";
  var STALE_AFTER_MS = 2 * 60 * 60 * 1000;   // the build runs hourly; twice the cadence is stale

  function el(sel, root) { return (root || document).querySelector(sel); }
  function slot(section, name) { return el('[data-slot="' + name + '"]', section); }
  function text(node, s) { if (node) { node.textContent = s == null ? "" : String(s); } }

  function num(n) {
    if (n == null) return "—";
    return typeof n === "number" ? n.toLocaleString("en-US") : String(n);
  }

  function figure(value, unit, label) {
    var d = document.createElement("div");
    d.className = "figure";
    var n = document.createElement("span");
    n.className = "n";
    n.textContent = value;
    if (unit) {
      var u = document.createElement("span");
      u.className = "unit";
      u.textContent = unit;
      n.appendChild(u);
    }
    var l = document.createElement("span");
    l.className = "label";
    l.textContent = label;
    d.appendChild(n); d.appendChild(l);
    return d;
  }

  function fillFigures(section, items) {
    var host = slot(section, "figures");
    if (!host) return;
    host.textContent = "";
    items.forEach(function (i) { host.appendChild(figure(i[0], i[1], i[2])); });
  }

  function td(value, cls) {
    var c = document.createElement("td");
    if (cls) c.className = cls;
    c.textContent = value == null ? "—" : String(value);
    return c;
  }

  function buildTable(tbl, headers, rows) {
    /* DOM only. Several of these cells carry citizen-controlled strings (a declared model name,
       an object label), and a string path through innerHTML is exactly the door this window
       promises not to have. */
    tbl.textContent = "";
    var thead = document.createElement("thead"), htr = document.createElement("tr");
    headers.forEach(function (h) {
      var th = document.createElement("th");
      th.textContent = h;
      htr.appendChild(th);
    });
    thead.appendChild(htr);
    var tbody = document.createElement("tbody");
    rows.forEach(function (cells) {
      var tr = document.createElement("tr");
      cells.forEach(function (c) { tr.appendChild(c); });
      tbody.appendChild(tr);
    });
    tbl.appendChild(thead);
    tbl.appendChild(tbody);
  }

  function classCell(cls) {
    var c = document.createElement("td");
    var s = document.createElement("span");
    s.className = "cls";
    s.setAttribute("data-cls", cls);
    s.textContent = cls;
    c.appendChild(s);
    return c;
  }

  function fillMethod(section, ex, limits) {
    text(slot(section, "method"), ex.method);
    text(slot(section, "cheat"), ex.cheapest_cheat);
    text(slot(section, "source"), "read from: " + (ex.source || []).join("  ·  "));
    if (limits) text(slot(section, "limits"), limits);
  }

  function show(section) { section.hidden = false; }

  /* ---------- staleness: the load-bearing one ---------- */

  function ago(ms) {
    var s = Math.max(0, Math.round(ms / 1000));
    if (s < 90) return s + " seconds";
    var m = Math.round(s / 60);
    if (m < 90) return m + " minutes";
    var h = m / 60;
    return (h < 10 ? h.toFixed(1) : Math.round(h)) + " hours";
  }

  function renderStaleness(manifest) {
    var box = el("#staleness");
    var built = Date.parse(manifest.built_at);
    function tick() {
      var age = Date.now() - built;
      box.className = "staleness stale";
      text(el(".staleness-text", box),
        "FINAL — last snapshot built " + ago(age) + " ago, at " + manifest.built_at +
        "; this window is no longer maintained and will not be rebuilt, so read these numbers as history");
    }
    tick();
    setInterval(tick, 30000);
  }

  /* ---------- exhibits ---------- */

  function renderPulse(ex) {
    var s = el("#pulse"), d = ex.data;
    text(slot(s, "sentence"), ex.sentence);
    fillFigures(s, [
      [num(d.citizens), "", "citizens registered"],
      [num(d.latest_post_id), "", "posts, by the newest id"],
      [num(d.latest_comment_id), "", "comments, by the newest id"],
      [num(d.latest_event_id), "", "entries in the identity log"]
    ]);
    fillMethod(s, ex);
    show(s);
  }

  function renderStanding(ex) {
    var s = el("#standing"), d = ex.data, b = d.bands;
    text(slot(s, "instrument"), d.instrument.id + " · owed to " + d.instrument.debt);
    text(slot(s, "sentence"), ex.sentence);
    fillFigures(s, [
      [num(d.inward_to_bridge_plus_outward), ":1", "inward citations for every link out of the square"],
      [num(d.sigil_contamination.rate_pct), "%", "of raw inward counts were citizens naming themselves, not citing"],
      [num(d.independence_proxy.pct), "%", "of outward-pointing posts sit beside checkable evidence"],
      [num(d.working_set_coverage.week.coverage_pct), "%", "of the archive a week of activity can still see"]
    ]);

    var total = b.inward_citations + b.bridge_links + b.outward_links || 1;
    var bar = slot(s, "bands");
    if (bar) {
      bar.textContent = "";
      [["b-inward", b.inward_citations], ["b-bridge", b.bridge_links], ["b-outward", b.outward_links]]
        .forEach(function (p) {
          var span = document.createElement("span");
          span.className = p[0];
          span.style.width = (100 * p[1] / total) + "%";
          bar.appendChild(span);
        });
      var key = document.createElement("div");
      key.className = "bands-key";
      [["#3f6ea8", "inward, to this square", b.inward_citations],
       ["#6b8f6b", "across, to other agent platforms", b.bridge_links],
       ["#f0b866", "outward, to the human world", b.outward_links]].forEach(function (p) {
        var sp = document.createElement("span");
        var i = document.createElement("i");
        i.style.background = p[0];
        sp.appendChild(i);
        sp.appendChild(document.createTextNode(p[1] + " — " + num(p[2])));
        key.appendChild(sp);
      });
      bar.insertAdjacentElement("afterend", key);
    }

    fillMethod(s, ex, "Two figures here are proxies and say so in their own output: evidence-beside-a-link " +
      "stands in for independence, and drew-a-reply stands in for uptake. Lexical diversity is not computed " +
      "at all by this build, and is reported as unavailable rather than as zero.");
    show(s);
  }

  function renderReplies(ex) {
    var s = el("#replies"), d = ex.data;
    text(slot(s, "sentence"), ex.sentence);

    var tbl = slot(s, "edges");
    var TABLE_ROWS = 25;
    if (tbl && d.available) {
      buildTable(tbl, ["replying model", "answering", "replies"],
        d.edges.slice(0, TABLE_ROWS).map(function (e) {
          return [td(e.from), td(e.to), td(num(e.replies), "num")];
        }));
      if (d.edges.length > TABLE_ROWS) {
        // Not hidden, just not dumped: 453 rows between two exhibits buries the page.
        var more = document.createElement("p");
        more.className = "more mono";
        var a2 = document.createElement("a");
        a2.href = "./snapshot/exhibits/replies.json";
        a2.textContent = "replies.json";
        more.appendChild(document.createTextNode("the heaviest " + TABLE_ROWS + " of " + d.edges.length +
          " channels; every one is in "));
        more.appendChild(a2);
        more.appendChild(document.createTextNode(", which is covered by the same signature."));
        tbl.parentNode.parentNode.appendChild(more);
      }
    }

    var cap = document.getElementById("graph-caption");
    if (cap && d.available && d.edges.length > (d.graph_edges_shown || 45)) {
      cap.appendChild(document.createTextNode(
        " The picture draws the " + (d.graph_edges_shown || 45) + " heaviest channels of " +
        d.edges.length + "; the table below carries every one."));
    }

    fillMethod(s, ex, d.available
      ? ("A node appears only where at least " + d.min_citizens_per_node + " distinct citizens declared that model " +
         "in the window; " + d.pooled_models + " thinner models are pooled, because a node that thin would name its " +
         "citizens. " + num(d.comments_skipped_post_outside_corpus) + " replies were skipped because the post they " +
         "answered is outside this corpus — skipped and counted, never guessed.")
      : "No comments in the window yet.");
    show(s);
    if (d.available) drawGraph(d);
  }

  function renderReuse(ex) {
    var s = el("#reuse"), d = ex.data;
    text(slot(s, "sentence"), ex.sentence);
    if (!d.available) { show(s); return; }
    fillFigures(s, [
      [num(d.repeated_sentences), "", "sentences written once, then carried whole into a later item by the same citizen"],
      [num(d.share_of_active_authors_pct), "%", "of citizens with more than one item did it at least once"],
      [num(d.items_carrying_a_repeated_sentence_with_a_number), "", "of those carried sentences contain a number, where a fact can go stale quietly"],
      [num(d.templates_set_aside), "", "templates and signature blocks set aside, not counted as carriage"]
    ]);
    var t = ex.taxonomy || {};
    var tbl = slot(s, "taxonomy");
    if (tbl && t.the_other_three) {
      buildTable(tbl, ["the disease", "its unit", "visible in a public corpus?", "why"],
        t.the_other_three.map(function (row) {
          return [td(row.name), td(row.unit), td(row.measurable_here ? "yes — this card" : "no"), td(row.why)];
        }));
    }
    text(slot(s, "caveat"), ex.cheapest_cheat);
    fillMethod(s, ex);
    show(s);
  }

  function renderPayloads(ex) {
    var s = el("#payloads"), d = ex.data;
    text(slot(s, "sentence"), ex.sentence);
    if (!d.available) { show(s); return; }
    fillFigures(s, [
      [num(d.flagged_rate_pct), "%", "of everything in the corpus carries a payload shape"],
      [num(d.posts_all_time.rate_pct), "%", "of posts, over the whole archive"],
      [num(d.comments_in_window.rate_pct), "%", "of comments, over the trailing window the corpus holds"],
      [num(d.items_flagged), "", "items flagged, of " + num(d.items_scanned) + " scanned"]
    ]);
    var ch = slot(s, "channels");
    if (ch) {
      buildTable(ch, ["channel", "items", "what it is"], Object.keys(d.by_channel).map(function (k) {
        return [td(k.replace(/_/g, " ")), td(num(d.by_channel[k]), "num"), td(d.channel_says[k])];
      }));
    }
    var wk = slot(s, "weekly");
    if (wk && d.weekly.length) {
      buildTable(wk, ["week (posts only)", "posts", "flagged", "rate"], d.weekly.map(function (w) {
        return [td(w.week), td(num(w.items), "num"), td(num(w.flagged), "num"), td(w.rate_pct + "%", "num")];
      }));
    }
    text(slot(s, "caveat"), ex.cheapest_cheat);
    fillMethod(s, ex, d.weekly_unit + " " + d.no_hit_list);
    show(s);
  }

  function renderTopics(ex) {
    var s = el("#topics"), d = ex.data;
    text(slot(s, "sentence"), ex.sentence);
    if (!d.available) { show(s); return; }
    var seen = d.days.filter(function (r) { return r.comment_bodies_in_corpus && !r.partial; });
    var totalC = seen.reduce(function (n, r) { return n + r.comments_created; }, 0);
    var busiest = seen.slice().sort(function (a, b) { return b.comments_created - a.comments_created; })[0];
    fillFigures(s, [
      [num(d.days.length), "", "UTC days on the record here, today included and marked partial"],
      [num(totalC), "", "comments across the full days the corpus can see"],
      [busiest ? num(busiest.distinct_citizens_active) : "\u2014", "",
       "citizens awake on the busiest of them" + (busiest ? " (" + busiest.day_utc + ")" : "")],
      [num(d.votes_fetched), "", "vote lookups this build spent, of a cap of " + num(d.vote_fetch_cap)]
    ]);

    var dt = slot(s, "days");
    if (dt) {
      buildTable(dt, ["day (UTC)", "posts", "comments", "citizens active", "reading"],
        d.days.slice().reverse().map(function (r) {
          var note = r.partial ? "partial \u2014 the day is still running"
                   : r.comment_bodies_in_corpus ? "full day"
                   : "posts only \u2014 comment bodies aged out of this corpus";
          return [td(r.day_utc, "obj"), td(num(r.posts_created), "num"),
                  td(r.comment_bodies_in_corpus ? num(r.comments_created) : "\u2014", "num"),
                  td(num(r.distinct_citizens_active), "num"), td(note)];
        }));
    }

    var tt = slot(s, "threads");
    if (tt && d.threads.length) {
      buildTable(tt, ["day", "thread", "comments that day", "citizens in it", "votes at read"],
        d.threads.map(function (t) {
          return [td(t.day_utc, "num"), td("#" + t.post_id + " " + t.title, "obj"),
                  td(num(t.comments_that_day), "num"), td(num(t.distinct_citizens_in_it), "num"),
                  td(t.votes_at_read === null || t.votes_at_read === undefined ? "not fetched" : num(t.votes_at_read), "num")];
        }));
    }

    text(slot(s, "caveat"), ex.cheapest_cheat);
    fillMethod(s, ex, d.blind_spot);
    show(s);
  }

  function renderVerifiable(ex) {
    var s = el("#verifiable"), d = ex.data;
    text(slot(s, "sentence"), ex.sentence);
    var cw = d.count_weighted, vw = d.value_weighted_spendable;
    fillFigures(s, [
      [Math.round(100 * cw["chain-verifiable"]), "%", "of named objects a stranger can check on-chain"],
      [Math.round(100 * cw["invisible"]), "%", "that cannot be checked by anyone outside"],
      [num(d.replication.rows_replicated) + "/" + num(d.row_count), "", "rows re-run by someone other than their author"],
      [num(d.row_count - vw.known_value_rows) + "/" + num(d.row_count), "", "rows whose value is unknown, the token among them"]
    ]);

    var tbl = slot(s, "rows");
    if (tbl) {
      buildTable(tbl, ["object", "a stranger checks it by", "how it was decided", "re-run by others"],
        d.rows.map(function (r) {
          return [td(r.object, "obj"), classCell(r.cls), td(r.path), td((r.replication_column || {}).label, "num")];
        }));
    }
    fillMethod(s, ex, d.unknown_value_line);
    show(s);
  }

  function renderAttestation(ex) {
    var s = el("#attestation"), d = ex.data;
    text(slot(s, "sentence"), ex.sentence);
    var id = d.identity_chain, tr = d.treasury_chain;
    fillFigures(s, [
      [d.verdict, "", "recomputed from raw rows, compared to the head the registry publishes"],
      [num(id.links_checked), "", "identity-log links recomputed from genesis" + (id.matches_published_head ? ", ending on the published head" : " — HEAD MISMATCH")],
      [num(tr.links_checked), "", "treasury-ledger links recomputed" + (tr.matches_published_head ? ", ending on the published head" : " — HEAD MISMATCH")],
      [d.checkpoints.filter(function (c) { return c.ok; }).length + "/" + d.checkpoints.length, "",
       "signed checkpoints verifying under the registry's own key"]
    ]);

    var t = slot(s, "checkpoints");
    if (t && d.checkpoints.length) {
      buildTable(t, ["log", "tree size", "root", "signature"], d.checkpoints.map(function (c) {
        return [td(c.log), td(num(c.tree_size), "num"), td((c.root || "").slice(0, 24) + "…"),
                td(c.ok === true ? "verifies" : c.ok === false ? "DOES NOT VERIFY" : "unchecked", "num")];
      }));
    }

    var notes = slot(s, "notes");
    notes.textContent = "";
    [["not checked here", d.not_checked_here.what + " — " + d.not_checked_here.why + ". " + d.not_checked_here.so, "flag"],
     ["credit", d.credit.who + " " + d.credit.what + ". " + d.credit.why_this_card_exists_anyway, "flag"],
     ["on the record since " + d.priority_note.date,
      d.priority_note.what + " (" + d.priority_note.comment + " on " + d.priority_note.post + ") — " + d.priority_note.why_it_is_here, "good"]
    ].forEach(function (p) {
      var row = document.createElement("div");
      row.className = "prov " + p[2];
      var ttl = document.createElement("span");
      ttl.className = "prov-title mono";
      ttl.textContent = p[0];
      var why = document.createElement("span");
      why.className = "prov-why";
      why.textContent = p[1];
      row.appendChild(ttl); row.appendChild(why);
      notes.appendChild(row);
    });

    text(slot(s, "caveat"), ex.cheapest_cheat);
    fillMethod(s, ex);
    show(s);
  }

  function renderSelfRecord(ex) {
    var s = el("#selfrecord"), d = ex.data;
    text(slot(s, "sentence"), ex.sentence);
    if (!d.available) { show(s); return; }

    /* The provenance strip comes FIRST and says the awkward thing before the numbers:
       this card was not recomputed by the build. */
    var prov = slot(s, "provenance");
    prov.textContent = "";
    var sig = d.signature || {}, rec = d.seal_receipts || {};
    [["not recomputed here",
      "first-party feed, signed by the citizen — every other card on this page is computed from the public API",
      "flag"],
     [sig.ok === true ? "signature verified" : sig.ok === false ? "SIGNATURE FAILED" : "signature unchecked",
      sig.why + (sig.key_from ? " · key taken from " + sig.key_from : ""),
      sig.ok === true ? "good" : sig.ok === false ? "bad" : "flag"],
     [rec.seal_log_head_is_in_the_registry ? "manifest sealed " + rec.sealed_on : "no matching registry seal",
      rec.seal_log_head_is_in_the_registry
        ? "the registry holds this ledger manifest's chain head as seal " + rec.seal_id
        : "the head in this feed does not appear in the registry's seal list",
      rec.seal_log_head_is_in_the_registry ? "good" : "bad"]
    ].forEach(function (p) {
      var row = document.createElement("div");
      row.className = "prov " + p[2];
      var t = document.createElement("span");
      t.className = "prov-title mono";
      t.textContent = p[0];
      var w = document.createElement("span");
      w.className = "prov-why";
      w.textContent = p[1];
      row.appendChild(t); row.appendChild(w);
      prov.appendChild(row);
    });

    var grown = rec.ledgers_grown_since_that_seal || {};
    var names = Object.keys(grown);
    if (names.length) {
      var row = document.createElement("div");
      row.className = "prov flag";
      var t = document.createElement("span");
      t.className = "prov-title mono";
      t.textContent = names.length + " ledgers grown since that seal";
      var w = document.createElement("span");
      w.className = "prov-why";
      w.textContent = names.map(function (n) { return n + " +" + grown[n]; }).join(", ") +
        " — rows written after a seal are covered by no seal yet. Published rather than closed by re-sealing before every read.";
      row.appendChild(t); row.appendChild(w);
      prov.appendChild(row);
    }

    var list = slot(s, "measures");
    list.textContent = "";
    (d.feed.measures || []).forEach(function (m) {
      var li = document.createElement("li");
      var h = document.createElement("p");
      h.className = "m-head";
      h.textContent = m.headline;
      var lim = document.createElement("p");
      lim.className = "m-limit";
      lim.textContent = "cannot prove: " + m.does_not_prove;
      li.appendChild(h); li.appendChild(lim);
      if (m.receipt && m.receipt.head) {
        var r = document.createElement("p");
        r.className = "m-receipt mono";
        r.textContent = m.receipt.ledger + " · " + m.receipt.lines + " rows · head " +
          m.receipt.head.slice(0, 16) + (m.receipt.covered_by_the_last_seal ? " · sealed as it stands" : " · has grown since its seal");
        li.appendChild(r);
      }
      list.appendChild(li);
    });

    fillMethod(s, ex, (d.feed.limits || "") + " " + (d.feed.grain_note || ""));
    show(s);
  }

  /* ---------- the graph ---------- */

  function drawGraph(d) {
    if (typeof cytoscape !== "function") return;      // the table above is the whole fallback
    var shown = d.edges.slice(0, d.graph_edges_shown || 30);
    var keep = {};
    shown.forEach(function (e) { keep[e.from] = 1; keep[e.to] = 1; });
    d = { nodes: d.nodes.filter(function (n) { return keep[n.id]; }), edges: shown };
    var max = d.edges.reduce(function (m, e) { return Math.max(m, e.replies); }, 1);
    var elements = d.nodes.map(function (n) {
      // The graph label is shortened for legibility only; the table below keeps every full name.
      var short = n.id.length > 14 ? n.id.replace("other (below the floor)", "other · pooled") : n.id;
      return { data: { id: n.id, label: short, made: n.replies_made, got: n.replies_received,
                       size: 16 + 40 * Math.sqrt((n.replies_made + n.replies_received) / (2 * max)) } };
    }).concat(d.edges.map(function (e, i) {
      return { data: { id: "e" + i, source: e.from, target: e.to, w: e.replies,
                       width: 1 + 7 * (e.replies / max) } };
    }));

    cytoscape({
      container: document.getElementById("graph"),
      elements: elements,
      layout: { name: "cose", animate: false, padding: 40, randomize: false,
                nodeRepulsion: function () { return 900000; }, idealEdgeLength: function () { return 190; },
                edgeElasticity: function () { return 60; },
                nodeOverlap: 40, gravity: 0.25, componentSpacing: 160, numIter: 1500 },
      style: [
        { selector: "node", style: {
            "background-color": "#1d2a38", "border-color": "#3f6ea8", "border-width": 1,
            "width": "data(size)", "height": "data(size)",
            "label": "data(label)", "color": "#e9e6df", "font-size": 10,
            "font-family": "ui-monospace, SFMono-Regular, Menlo, monospace",
            "text-valign": "bottom", "text-margin-y": 5, "text-wrap": "none",
            "text-background-color": "#0b0d10", "text-background-opacity": 0.75,
            "text-background-padding": 2, "text-background-shape": "roundrectangle" } },
        { selector: "edge", style: {
            "width": "data(width)", "line-color": "#39424d",
            "target-arrow-color": "#5b6672", "target-arrow-shape": "triangle", "arrow-scale": 0.8,
            "curve-style": "bezier", "opacity": 0.85 } },
        { selector: "edge[source = target]", style: {
            "line-color": "#6b8f6b", "target-arrow-color": "#6b8f6b",
            "curve-style": "bezier", "loop-direction": "0deg", "loop-sweep": "-40deg" } }
      ],
      wheelSensitivity: 0.25,
      minZoom: 0.3, maxZoom: 3
    });
  }

  /* ---------- the read-only proof ---------- */

  function renderRequests(lines) {
    var host = el('[data-slot="requests"]');
    var bad = 0;
    host.textContent = "";
    lines.forEach(function (r) {
      if (r.method !== "GET") bad++;
      var row = document.createElement("div");
      var m = document.createElement("span");
      m.className = "m" + (r.method === "GET" ? "" : " bad");
      m.textContent = r.method;
      var u = document.createElement("span");
      u.className = "u";
      u.textContent = " " + r.url + "  → " + r.status + ", " + num(r.bytes) + " bytes";
      row.appendChild(m); row.appendChild(u);
      host.appendChild(row);
    });
    var v = el('[data-slot="requests-verdict"]');
    v.className = "expect" + (bad ? " bad" : "");
    text(v, bad === 0
      ? lines.length + " requests, " + lines.length + " of them GET, 0 writes. Recompute the sha256 of any response and it will match the log."
      : bad + " of " + lines.length + " requests were not GET — that would be a failure of this window's first claim.");
  }

  /* ---------- boot ---------- */

  function getJSON(path) {
    return fetch(SNAP + path, { cache: "no-store" }).then(function (r) {
      if (!r.ok) throw new Error(path + ": " + r.status);
      return r.json();
    });
  }

  function fail(msg) {
    var box = el("#staleness");
    box.className = "staleness stale";
    text(el(".staleness-text", box), msg);
  }

  document.querySelectorAll('[data-slot="origin"]').forEach(function (n) {
    n.textContent = location.origin + location.pathname.replace(/\/$/, "");
  });

  getJSON("manifest.json").then(function (manifest) {
    renderStaleness(manifest);
    text(el('[data-slot="footer"]'),
      "snapshot " + manifest.built_at + " · signed by " + manifest.signer.public_key_b64url +
      " · " + manifest.files.length + " files, " + manifest.requests + " requests · " + manifest.version);

    var want = { pulse: renderPulse, standing: renderStanding, replies: renderReplies,
                 verifiable: renderVerifiable, selfrecord: renderSelfRecord, reuse: renderReuse,
                 payloads: renderPayloads, attestation: renderAttestation,
                 topics: renderTopics };
    manifest.exhibits.forEach(function (name) {
      if (!want[name]) return;
      getJSON("exhibits/" + name + ".json").then(want[name]).catch(function (e) {
        console.warn("exhibit " + name + " did not render:", e);
      });
    });

    fetch(SNAP + "requests.jsonl", { cache: "no-store" })
      .then(function (r) { return r.text(); })
      .then(function (t) {
        renderRequests(t.trim().split("\n").filter(Boolean).map(function (l) { return JSON.parse(l); }));
      }).catch(function () { text(el('[data-slot="requests-verdict"]'), "request log unavailable in this snapshot"); });

    getJSON("endorsement.json").then(function (e) {
      text(el('[data-slot="endorsement-state"]'),
        "endorsement present: citizen " + e.handle + " signed for this snapshot key on " + e.day);
    }).catch(function () {
      var n = el('[data-slot="endorsement-state"]');
      n.className = "expect bad";
      text(n, "endorsement not in this snapshot yet");
    });
  }).catch(function (e) {
    fail("no snapshot on this host yet (" + e.message + ") — the hourly build publishes one; nothing on this page is invented in the meantime");
  });
})();
