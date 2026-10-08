--- main_orig.py	2026-10-08 05:38:27.620923128 +0000
+++ main.py	2026-10-08 05:39:27.726302980 +0000
@@ -12,6 +12,7 @@
 import logging
 import os
 import re
+import time
 import uuid
 from typing import Optional
 
@@ -57,29 +58,46 @@
 MAX_QTY_PER_ITEM = 20
 MAX_SESSIONS = 500
 MAX_TOOL_ROUNDS = 6
+SEARCH_LIMIT = 10         # was 5: Class IX Matric alone can have 8+ bundles
+MAX_SYNC_PAGES = 60       # safety stop: 60 pages x 250 products
 BESTSELLER_POOL = 60      # how many top sellers to keep ranked in Qdrant
 MAX_SUGGESTIONS = 4       # add-ons shown before checkout
 
 # Store facts the assistant may state. Edit freely.
 STORE_INFO = f"""
-- Clover.pk sells school books, HHS book bundles, stationery, school essentials and toys.
+- Clover.pk sells school books, HHS book bundles, stationery, school essentials, essential kits and toys.
 - Payment: only Cash on Delivery (COD) and PayFast (online). Never ask for payment details, and never tell anyone to pay into a bank account.
-- Support: Monday to Friday, 9:00 am to 5:00 pm. Phone +92-21-38722020, WhatsApp 0301 5676256.
+- Support: Monday to Friday, 9:00 am to 5:00 pm. Phone +92-21-38722020 or 0304 1112587, WhatsApp 0301 5676256.
 - Policy pages: shipping {STORE_URL}/pages/shipping-policy, exchange {STORE_URL}/pages/exchange-policy, refund {STORE_URL}/pages/refund-policy, cancellation {STORE_URL}/pages/cancellation-policy.
 """.strip()
 
+# What the HHS bundle catalog looks like (taken from the live store menu).
+CATALOG_FACTS = """
+- Pre-Nursery and Nursery: one Complete Bundle each, no stream. Do not ask for a stream.
+- Prep to Class VIII: Matric, O Level and Fast Track bundles. There is no AKU EB for these classes.
+- Class IX and X: Matric, O Level, AKU EB and Fast Track bundles.
+- Matric and O Level bundles are usually sold as separate Exercise and Textbook bundles for each class. Show every one the results contain.
+- Subject groups (AKU EB: Biology or Computer; Matric: Biology, Computer, Commerce or Arts) apply to Class IX and X only.
+""".strip()
+
 SYSTEM_PROMPT = f"""You are the friendly online order assistant for Clover.pk, a school books and stationery store.
 You help parents find products, build a cart, and get a checkout link.
 
 WHAT YOU KNOW ABOUT THE STORE:
 {STORE_INFO}
 
+CATALOG LAYOUT:
+{CATALOG_FACTS}
+
 RULES:
 - You are also a helpful sales assistant. Start by finding out what the parent needs, one short question at a time (for books: class and stream; for stationery or essentials: what the child needs and roughly how many). Do not ask for things already given.
 - Use search_products to find products. Never guess products, prices, or stock.
-- HHS book bundles depend on class and stream (Matric, O Level, AKU EB, Fast Track). "AKU", "AKU-EB" and "AKUEB" all mean the AKU EB stream, so never ask which stream when a parent says one of them. If the class or the stream is missing, ask only for what is missing before searching.
-- Groups: AKU EB has Biology or Computer. Matric has Biology, Computer, Commerce or Arts. When the parent gives a class and stream and the results show separate bundles for several groups, list every matching bundle with its price and let the parent choose. Do not ask "which group?" before showing them.
+- Never decide yourself that a class, stream or group does not exist. Always search and trust the results.
+- In search_products, always fill class_name and stream when the parent gave them. class_name is PRE-NURSERY, NURSERY, PREP, or a Roman numeral from I to X ("class 3" or "three" means III). stream is one of: Matric, O Level, AKU EB, Fast Track.
+- HHS book bundles depend on class and stream (Matric, O Level, AKU EB, Fast Track). "AKU", "AKU-EB" and "AKUEB" all mean the AKU EB stream, so never ask which stream when a parent says one of them. If the class or the stream is missing, ask only for what is missing before searching. For Pre-Nursery and Nursery do not ask for a stream.
+- When the parent gives a class and stream and the results show several bundles (Exercise and Textbook, or separate groups), show every matching bundle and let the parent choose. Do not ask "which group?" before showing them.
 - Bundles are for a specific session (for example 2026-27). Offer the newest session shown in the results and mention the session name.
+- If search_products returns streams_available_for_this_class or classes_available_for_this_stream, tell the parent what is available and offer to search again.
 - Add to the cart only when the parent clearly wants that item. Use the exact handle and variant_id from the search results.
 - Quote prices only from tool results, in Rs. Shipping and taxes are calculated at checkout; do not state delivery charges or delivery times, point to the shipping policy page instead.
 - When the parent is done choosing, call view_cart and then get_suggestions in the same turn. Show the items and total, then offer at most 3 add-ons from get_suggestions: "bought_together" items first (say "Often bought together"), then "best_sellers" (say "Best seller"). Only suggest items returned by get_suggestions. Be gentle, never pushy, and suggest only once. Then ask whether they want to add any or go to checkout.
@@ -105,10 +123,29 @@
         "type": "function",
         "function": {
             "name": "search_products",
-            "description": "Search the Clover.pk catalog. Include class, stream, subject or product name in the query.",
+            "description": (
+                "Search the Clover.pk catalog. Put the product name or subject in query. "
+                "Also fill class_name, stream and kind whenever the parent mentioned them, "
+                "because they filter the results exactly."
+            ),
             "parameters": {
                 "type": "object",
-                "properties": {"query": {"type": "string"}},
+                "properties": {
+                    "query": {"type": "string"},
+                    "class_name": {
+                        "type": "string",
+                        "description": "PRE-NURSERY, NURSERY, PREP, or a Roman numeral I to X (class 3 -> III).",
+                    },
+                    "stream": {
+                        "type": "string",
+                        "enum": ["Matric", "O Level", "AKU EB", "Fast Track"],
+                    },
+                    "kind": {
+                        "type": "string",
+                        "enum": ["Exercise", "Textbook", "Complete", "Kit"],
+                        "description": "Optional. Only set if the parent asked for exercise books, textbooks, a complete bundle or an essential kit.",
+                    },
+                },
                 "required": ["query"],
             },
         },
@@ -205,22 +242,156 @@
 
 
 # ============================================================================
-# PRODUCT SYNC  (Shopify -> Qdrant)
+# FACETS: class, stream, session, kind (read from titles, not guessed by the LLM)
+# ============================================================================
+
+ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V",
+         6: "VI", 7: "VII", 8: "VIII", 9: "IX", 10: "X"}
+WORD_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
+            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
+CLASS_ORDER = ["PRE-NURSERY", "NURSERY", "PREP"] + list(ROMAN.values())
+
+# Longest alternatives first so "VIII" is not read as "V".
+ROMAN_RE = r"(XII|XI|X|IX|VIII|VII|VI|IV|V|III|II|I)"
+SESSION_RE = r"\b20\d{2}\s*[-\u2013]\s*\d{2}\b"
+
+LEVELS = [  # most specific first
+    ("PRE-NURSERY", r"\bpre[\s\-]?nursery\b"),
+    ("NURSERY", r"\bnursery\b"),
+    ("PREP", r"\bprep\b|\bkindergarten\b"),
+]
+
+STREAMS = [
+    ("AKU EB", r"\baku[\s\-]?eb\b|\baku\b|\bakueb\b"),
+    ("Matric", r"\bmatric\b"),
+    ("O Level", r"\bo[\s\-]?level\b"),
+    ("Fast Track", r"\bfast[\s\-]?track\b"),
+]
+
+KINDS = [
+    ("Kit", r"\bessential kit\b"),
+    ("Exercise", r"\bexercise\b"),
+    ("Textbook", r"\btext[\s\-]?book\b"),
+    ("Complete", r"\bcomplete\b"),
+]
+
+KEYWORD_FIELDS = ("class", "stream", "session", "kind")
+
+
+def extract_class(text: str, allow_trailing: bool = True) -> Optional[str]:
+    """Return PRE-NURSERY / NURSERY / PREP / Roman numeral, or None."""
+    text = (text or "").strip()
+    for label, pat in LEVELS:
+        if re.search(pat, text, re.I):
+            return label
+
+    m = re.search(rf"\b(?:class|grade)\s+{ROMAN_RE}\b", text, re.I)  # "Class III"
+    if m:
+        return m.group(1).upper()
+
+    m = re.search(r"\b(?:class|grade)\s*(\d{1,2})\b", text, re.I)  # "Class 3"
+    if m:
+        return ROMAN.get(int(m.group(1)))
+
+    m = re.search(
+        r"\b(?:class|grade)\s+(one|two|three|four|five|six|seven|eight|nine|ten)\b",
+        text, re.I,
+    )  # "class three"
+    if m:
+        return ROMAN[WORD_NUM[m.group(1).lower()]]
+
+    if allow_trailing:
+        # "Mutala E Quran IV" or "Islamic Studies III (Revised Edition)".
+        # A lone trailing "I" is too ambiguous (it is usually a part number).
+        m = re.search(rf"\b{ROMAN_RE}\s*(?:\([^)]*\))?\s*$", text, re.I)
+        if m and m.group(1).upper() != "I":
+            return m.group(1).upper()
+    return None
+
+
+def extract_stream(text: str) -> Optional[str]:
+    for name, pat in STREAMS:
+        if re.search(pat, text or "", re.I):
+            return name
+    return None
+
+
+def extract_kind(text: str) -> Optional[str]:
+    for name, pat in KINDS:
+        if re.search(pat, text or "", re.I):
+            return name
+    return None
+
+
+def extract_facets(product: dict, tags: list) -> dict:
+    """
+    Title is the most reliable source. The URL handle is NOT reliable for the
+    session (a "2026-27" title can sit on a "...-2024-25-copy" handle), so the
+    session comes from the title only. The handle is used only as a class hint.
+    """
+    title = product.get("title", "")
+    handle_text = (product.get("handle", "") or "").replace("-", " ")
+    extra = " ".join([product.get("product_type", "") or "", *tags])
+
+    sess = re.search(SESSION_RE, title)
+    return {
+        "class": (
+            extract_class(title)
+            or extract_class(handle_text, allow_trailing=False)
+            or extract_class(extra, allow_trailing=False)
+        ),
+        "stream": extract_stream(title) or extract_stream(extra),
+        "session": re.sub(r"\s+", "", sess.group(0)).replace("\u2013", "-") if sess else None,
+        "kind": extract_kind(title),
+        "is_bundle": bool(re.search(r"\bbundle\b", title, re.I)),
+    }
+
+
+def normalize_class(value) -> Optional[str]:
+    """Turn whatever the model sends ('3', 'three', 'class iii') into a stored label."""
+    if not value:
+        return None
+    v = re.sub(r"^(class|grade)\s*", "", str(value).strip().lower())
+    if re.fullmatch(r"pre[\s\-_]?nursery|pn", v):
+        return "PRE-NURSERY"
+    if v == "nursery":
+        return "NURSERY"
+    if v in ("prep", "kg", "kindergarten"):
+        return "PREP"
+    if v.isdigit():
+        return ROMAN.get(int(v))
+    if v in WORD_NUM:
+        return ROMAN[WORD_NUM[v]]
+    if v.upper() in CLASS_ORDER:
+        return v.upper()
+    return None
+
+
+def normalize_stream(value) -> Optional[str]:
+    return extract_stream(str(value)) if value else None
+
+
+def normalize_kind(value) -> Optional[str]:
+    return extract_kind(str(value)) if value else None
+
+
+# ============================================================================
+# PRODUCT SYNC  (Shopify -> Qdrant, built into a new collection, then swapped in)
 # ============================================================================
 
 BROWSER_HEADERS = {"User-Agent": "Mozilla/5.0 (CloverOrderBot)"}
-SYNC_STATE = {"running": False, "products": 0, "error": None}
+SYNC_STATE = {"running": False, "products": 0, "collection": None, "error": None}
 
 
-def clean_text(html: str, limit: int = 300) -> str:
+def clean_text(html: str, limit: int = 500) -> str:
     text = re.sub(r"<[^>]+>", " ", html or "")
     return re.sub(r"\s+", " ", text).strip()[:limit]
 
 
 def fetch_all_products() -> list:
     """Read the public product list, 250 at a time, until it runs out."""
-    products, page = [], 1
-    while True:
+    products, seen, page = [], set(), 1
+    while page <= MAX_SYNC_PAGES:
         r = requests.get(
             f"{STORE_URL}/products.json",
             params={"limit": 250, "page": page},
@@ -230,9 +401,13 @@
         r.raise_for_status()
         batch = r.json().get("products", [])
         if not batch:
-            return products
-        products.extend(batch)
+            break
+        for p in batch:
+            if p["id"] not in seen:
+                seen.add(p["id"])
+                products.append(p)
         page += 1
+    return products
 
 
 def fetch_bestseller_ranks() -> dict:
@@ -257,6 +432,8 @@
     if isinstance(tags, str):
         tags = [t.strip() for t in tags.split(",")]
 
+    facets = extract_facets(product, tags)
+
     variants = [
         {
             "id": str(v["id"]),
@@ -264,7 +441,7 @@
             "price": v.get("price"),
             "available": v.get("available", True),
         }
-        for v in product.get("variants", [])[:20]
+        for v in product.get("variants", [])[:50]
     ]
 
     image = (product.get("image") or {}).get("src") or next(
@@ -273,8 +450,19 @@
     if image:
         image += ("&" if "?" in image else "?") + "width=300"
 
+    # Put the facets into the text too, in plain words, so the embedding sees them.
+    facet_text = " ".join(
+        part
+        for part in (
+            f"Level: {facets['class']}." if facets["class"] else "",
+            f"Stream: {facets['stream']}." if facets["stream"] else "",
+            f"Kind: {facets['kind']}." if facets["kind"] else "",
+            f"Session: {facets['session']}." if facets["session"] else "",
+        )
+        if part
+    )
     embed_text = (
-        f"{product.get('title', '')}. "
+        f"{product.get('title', '')}. {facet_text} "
         f"Type: {product.get('product_type', '')}. "
         f"Brand: {product.get('vendor', '')}. "
         f"Tags: {', '.join(tags)}. "
@@ -292,45 +480,92 @@
             "image": image,
             "url": f"{STORE_URL}/products/{product.get('handle', '')}",
             "variants": variants,
+            **facets,
         },
     )
 
 
+def point_alias_to(client: QdrantClient, new_name: str):
+    """Make PRODUCT_COLLECTION an alias of new_name, then delete older copies."""
+    aliases = {a.alias_name: a.collection_name for a in client.get_aliases().aliases}
+    names = {c.name for c in client.get_collections().collections}
+
+    if PRODUCT_COLLECTION in names and PRODUCT_COLLECTION not in aliases:
+        # Old layout: a real collection holds the alias name. It must go once
+        # (a few seconds of downtime on the first run of this version only).
+        client.delete_collection(PRODUCT_COLLECTION)
+
+    ops = []
+    if PRODUCT_COLLECTION in aliases:
+        ops.append(
+            models.DeleteAliasOperation(
+                delete_alias=models.DeleteAlias(alias_name=PRODUCT_COLLECTION)
+            )
+        )
+    ops.append(
+        models.CreateAliasOperation(
+            create_alias=models.CreateAlias(
+                collection_name=new_name, alias_name=PRODUCT_COLLECTION
+            )
+        )
+    )
+    client.update_collection_aliases(change_aliases_operations=ops)
+
+    pattern = re.compile(rf"^{re.escape(PRODUCT_COLLECTION)}_\d+$")
+    for name in names:
+        if name != new_name and pattern.match(name):
+            client.delete_collection(name)
+
+
 def sync_products():
-    """Fetch first, then replace the collection, so a failed fetch loses nothing."""
+    """Fetch first, build a fresh collection, then swap the alias. Search never goes down."""
     SYNC_STATE.update(running=True, error=None)
+    new_name = None
     try:
         products = fetch_all_products()
         ranks = fetch_bestseller_ranks()
         points = [build_point(p, ranks) for p in products]
 
         client = get_qdrant()
-        if client.collection_exists(PRODUCT_COLLECTION):
-            client.delete_collection(PRODUCT_COLLECTION)
+        new_name = f"{PRODUCT_COLLECTION}_{int(time.time())}"
         client.create_collection(
-            collection_name=PRODUCT_COLLECTION,
+            collection_name=new_name,
             vectors_config=models.VectorParams(
                 size=VECTOR_SIZE, distance=models.Distance.COSINE
             ),
         )
 
         client.create_payload_index(
-            collection_name=PRODUCT_COLLECTION,
+            collection_name=new_name,
             field_name="bestseller_rank",
             field_schema=models.PayloadSchemaType.INTEGER,
         )
+        for field in KEYWORD_FIELDS:
+            client.create_payload_index(
+                new_name, field, models.PayloadSchemaType.KEYWORD
+            )
+        client.create_payload_index(
+            new_name, "is_bundle", models.PayloadSchemaType.BOOL
+        )
 
         for start in range(0, len(points), 50):
             client.upsert(
-                collection_name=PRODUCT_COLLECTION,
+                collection_name=new_name,
                 points=points[start : start + 50],
             )
 
-        SYNC_STATE["products"] = len(points)
-        logger.info("Synced %s products", len(points))
+        point_alias_to(client, new_name)
+
+        SYNC_STATE.update(products=len(points), collection=new_name)
+        logger.info("Synced %s products into %s", len(points), new_name)
     except Exception as e:
         logger.exception("Product sync failed")
         SYNC_STATE["error"] = str(e)
+        if new_name:  # do not leave a half-built collection behind
+            try:
+                get_qdrant().delete_collection(new_name)
+            except Exception:
+                pass
     finally:
         SYNC_STATE["running"] = False
 
@@ -363,10 +598,6 @@
     }
 
 
-ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V",
-         6: "VI", 7: "VII", 8: "VIII", 9: "IX", 10: "X"}
-
-
 def normalize_query(query: str) -> str:
     """Spell things the way product titles do, so search finds them."""
     # aku / akueb / aku-eb  ->  AKU EB
@@ -374,12 +605,17 @@
     # olevel / o-level  ->  O Level
     q = re.sub(r"\bo[\s\-]?level\b", "O Level", q, flags=re.I)
 
-    # "class 5" -> "class 5 Class V" (titles use Roman numerals)
+    # "class 5" / "class five" -> add "Class V" (titles use Roman numerals)
     def add_roman(m):
-        n = int(m.group(2))
-        return f"{m.group(0)} Class {ROMAN[n]}" if n in ROMAN else m.group(0)
+        label = extract_class(m.group(0), allow_trailing=False)
+        return f"{m.group(0)} Class {label}" if label else m.group(0)
 
-    return re.sub(r"\b(class|grade)\s*(\d{1,2})\b", add_roman, q, flags=re.I)
+    return re.sub(
+        r"\b(?:class|grade)\s*(?:\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\b",
+        add_roman,
+        q,
+        flags=re.I,
+    )
 
 
 def list_price(variant: dict):
@@ -389,18 +625,109 @@
         return None
 
 
-def tool_search_products(query: str, session: dict) -> str:
-    query = normalize_query(query)
+def build_filter(cls, stream, kind) -> Optional[models.Filter]:
+    conds = [
+        models.FieldCondition(key=key, match=models.MatchValue(value=value))
+        for key, value in (("class", cls), ("stream", stream), ("kind", kind))
+        if value
+    ]
+    return models.Filter(must=conds) if conds else None
+
+
+def scroll_all(scroll_filter=None, fields=True) -> list:
+    client = get_qdrant()
+    out, offset = [], None
+    while True:
+        pts, offset = client.scroll(
+            collection_name=PRODUCT_COLLECTION,
+            scroll_filter=scroll_filter,
+            limit=256,
+            offset=offset,
+            with_payload=fields,
+            with_vectors=False,
+        )
+        out.extend(pts)
+        if offset is None:
+            return out
+
+
+def semantic_search(query: str, cls, stream, kind) -> list:
+    query_filter = build_filter(cls, stream, kind)
     result = get_qdrant().query_points(
         collection_name=PRODUCT_COLLECTION,
         query=models.Document(text=query, model=INFERENCE_MODEL),
-        limit=5,
+        query_filter=query_filter,
+        limit=SEARCH_LIMIT,
         with_payload=True,
     )
+    points = result.points
+    if query_filter is None:  # filters are exact; the score cut-off is only for free text
+        points = [p for p in points if p.score >= MIN_SCORE]
+    logger.info(
+        "search q=%r class=%s stream=%s kind=%s -> %s",
+        query, cls, stream, kind,
+        [(p.payload["title"], round(p.score, 3)) for p in points],
+    )
+    return points
+
+
+def newest_session_only(points: list) -> list:
+    """If the same product exists for several sessions, keep the newest one."""
+    best = {}
+    for p in points:
+        key = re.sub(SESSION_RE, "", p.payload["title"]).strip().lower()
+        session = p.payload.get("session") or ""
+        if key not in best or session > (best[key].payload.get("session") or ""):
+            best[key] = p
+    keep = {id(p) for p in best.values()}
+    return [p for p in points if id(p) in keep]
+
+
+def availability_hint(cls, stream) -> dict:
+    """Tell the model what really exists, so it never guesses."""
+    bundles = scroll_all(
+        models.Filter(
+            must=[models.FieldCondition(key="is_bundle", match=models.MatchValue(value=True))]
+        ),
+        fields=["class", "stream"],
+    )
+    out = {"message": "No exact match found."}
+    if cls:
+        streams = {p.payload.get("stream") for p in bundles if p.payload.get("class") == cls}
+        out["streams_available_for_this_class"] = sorted(s for s in streams if s)
+    if stream:
+        classes = {p.payload.get("class") for p in bundles if p.payload.get("stream") == stream}
+        out["classes_available_for_this_stream"] = [c for c in CLASS_ORDER if c in classes]
+    return out
+
+
+def tool_search_products(
+    query: str, session: dict, class_name=None, stream=None, kind=None
+) -> str:
+    # Use what the model passed; if it forgot, read it from the parent's words.
+    cls = normalize_class(class_name) or extract_class(query, allow_trailing=False)
+    st = normalize_stream(stream) or extract_stream(query)
+    kd = normalize_kind(kind)
+
+    query = normalize_query(query)
+
+    attempts = [(cls, st, kd)]
+    if kd:  # a wrong "kind" must not hide everything
+        attempts.append((cls, st, None))
+
+    points = []
+    for a_cls, a_st, a_kd in attempts:
+        points = semantic_search(query, a_cls, a_st, a_kd)
+        if points:
+            break
+
+    if not points:
+        if cls or st:
+            return json.dumps(availability_hint(cls, st))
+        return json.dumps({"message": "No matching products found."})
+
     found = []
-    for point in result.points:
-        if point.score < MIN_SCORE:
-            continue
+    for point in newest_session_only(points):
         p = point.payload
         card = compact_product(p)
         if card:
@@ -410,6 +737,7 @@
                 "title": p["title"],
                 "handle": p["handle"],
                 "url": p["url"],
+                "session": p.get("session"),
                 "variants": [
                     {
                         "id": v["id"],
@@ -421,8 +749,6 @@
                 ],
             }
         )
-    if not found:
-        return json.dumps({"message": "No matching products found."})
     return json.dumps(found)
 
 
@@ -616,7 +942,13 @@
     cart = session["cart"]
     try:
         if name == "search_products":
-            return tool_search_products(args.get("query", ""), session)
+            return tool_search_products(
+                args.get("query", ""),
+                session,
+                args.get("class_name"),
+                args.get("stream"),
+                args.get("kind"),
+            )
         if name == "add_to_cart":
             return tool_add_to_cart(
                 cart,
@@ -835,3 +1167,67 @@
             return {"url": None, "products": session["cards"]}
         session["suggested"] = True
     return {"url": json.loads(tool_checkout_link(session)).get("checkout_url")}
+
+
+# ============================================================================
+# DEBUG ROUTES (protected by the same secret as /sync-products)
+# ============================================================================
+
+
+def require_secret(secret: Optional[str]):
+    if not SYNC_SECRET or secret != SYNC_SECRET:
+        raise HTTPException(403, "Invalid secret.")
+
+
+@app.get("/debug/search")
+def debug_search(
+    q: str,
+    class_name: Optional[str] = None,
+    stream: Optional[str] = None,
+    kind: Optional[str] = None,
+    secret: Optional[str] = None,
+):
+    """See exactly what the search tool would return, with scores."""
+    require_secret(secret)
+    cls = normalize_class(class_name) or extract_class(q, allow_trailing=False)
+    st = normalize_stream(stream) or extract_stream(q)
+    kd = normalize_kind(kind)
+    points = semantic_search(normalize_query(q), cls, st, kd)
+    return {
+        "filters": {"class": cls, "stream": st, "kind": kd},
+        "results": [
+            {
+                "title": p.payload["title"],
+                "score": round(p.score, 3),
+                "class": p.payload.get("class"),
+                "stream": p.payload.get("stream"),
+                "kind": p.payload.get("kind"),
+                "session": p.payload.get("session"),
+            }
+            for p in points
+        ],
+    }
+
+
+@app.get("/debug/facets")
+def debug_facets(secret: Optional[str] = None):
+    """Audit the sync: counts, and every product whose class or stream was not detected."""
+    require_secret(secret)
+    rows = [p.payload for p in scroll_all()]
+    bundles = [r for r in rows if r.get("is_bundle")]
+
+    matrix = {}
+    for r in bundles:
+        matrix.setdefault(r.get("class") or "UNKNOWN", set()).add(r.get("stream") or "none")
+
+    return {
+        "total_products": len(rows),
+        "total_bundles": len(bundles),
+        "bundle_streams_by_class": {
+            c: sorted(matrix[c]) for c in CLASS_ORDER + ["UNKNOWN"] if c in matrix
+        },
+        "products_without_class": sorted(r["title"] for r in rows if not r.get("class")),
+        "bundles_without_class": sorted(r["title"] for r in bundles if not r.get("class")),
+        "bundles_without_stream": sorted(r["title"] for r in bundles if not r.get("stream")),
+        "bundles_without_session": sorted(r["title"] for r in bundles if not r.get("session")),
+    }
