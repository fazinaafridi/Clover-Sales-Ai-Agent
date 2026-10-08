/* Clover.pk chat widget: chat + product cards + cart + checkout.
   Add to the Shopify theme (before </body>):
   <script src="https://YOUR-APP.onrender.com/widget.js" defer></script> */
(function () {
  if (window.__cloverChat) return;
  window.__cloverChat = true;

  var API = new URL(document.currentScript.src).origin;
  var GREEN = "#2e7d32";
  var sid = null;
  try { sid = localStorage.getItem("clover_sid"); } catch (e) {}
  var cart = { items: [], subtotal: "Rs. 0" };
  var busy = false;

  // ---------- helpers ----------
  function h(tag, attrs, kids) {
    var el = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "text") el.textContent = attrs[k];
      else if (k.slice(0, 2) === "on") el.addEventListener(k.slice(2), attrs[k]);
      else el.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (c) { if (c) el.appendChild(c); });
    return el;
  }

  function post(path, body) {
    return fetch(API + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }

  // ---------- styles ----------
  var css = "\
#cvr-btn{position:fixed;right:18px;bottom:18px;width:58px;height:58px;border-radius:50%;border:0;background:" + GREEN + ";color:#fff;font-size:26px;cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,.3);z-index:99998}\
#cvr-box{position:fixed;right:18px;bottom:88px;width:380px;max-width:calc(100vw - 24px);height:600px;max-height:calc(100vh - 110px);background:#fff;border-radius:14px;box-shadow:0 8px 30px rgba(0,0,0,.28);display:none;flex-direction:column;overflow:hidden;z-index:99999;font:14px/1.4 -apple-system,Segoe UI,Roboto,sans-serif;color:#222}\
#cvr-box.open{display:flex}\
#cvr-head{background:" + GREEN + ";color:#fff;padding:12px 14px;font-weight:600;display:flex;justify-content:space-between;align-items:center}\
#cvr-head button{background:none;border:0;color:#fff;font-size:20px;cursor:pointer}\
#cvr-msgs{flex:1;overflow-y:auto;padding:12px;background:#f6f7f6}\
.cvr-m{max-width:85%;padding:8px 11px;border-radius:12px;margin:6px 0;white-space:pre-wrap;word-wrap:break-word}\
.cvr-bot{background:#fff;border:1px solid #e3e6e3;margin-right:auto}\
.cvr-me{background:" + GREEN + ";color:#fff;margin-left:auto}\
.cvr-chips{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0}\
.cvr-chip{border:1px solid " + GREEN + ";color:" + GREEN + ";background:#fff;border-radius:16px;padding:5px 10px;cursor:pointer;font-size:13px}\
.cvr-row{display:flex;gap:10px;overflow-x:auto;padding:4px 2px 8px;margin:4px 0;scroll-snap-type:x mandatory}\
.cvr-card{flex:0 0 170px;scroll-snap-align:start;background:#fff;border:1px solid #e3e6e3;border-radius:10px;overflow:hidden;display:flex;flex-direction:column}\
.cvr-card img{width:100%;height:120px;object-fit:contain;background:#fafafa}\
.cvr-noimg{height:120px;background:#f0f2f0;display:flex;align-items:center;justify-content:center;font-size:30px}\
.cvr-card .b{padding:8px;display:flex;flex-direction:column;gap:6px;flex:1}\
.cvr-tag{font-size:11px;color:#b45309;font-weight:600}\
.cvr-title{font-size:13px;font-weight:600;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}\
.cvr-price{font-weight:700;color:" + GREEN + "}\
.cvr-card select{width:100%;font-size:12px;padding:3px;border:1px solid #ccc;border-radius:6px}\
.cvr-add{margin-top:auto;border:0;background:" + GREEN + ";color:#fff;border-radius:8px;padding:7px;cursor:pointer;font-weight:600}\
.cvr-add:disabled{background:#9aa59a;cursor:default}\
#cvr-cartbar{border-top:1px solid #e3e6e3;background:#fff}\
#cvr-cartsum{display:flex;justify-content:space-between;align-items:center;padding:8px 12px;cursor:pointer;font-weight:600}\
#cvr-cartlist{display:none;max-height:150px;overflow-y:auto;padding:0 12px 6px;font-size:13px}\
#cvr-cartlist.open{display:block}\
.cvr-li{display:flex;justify-content:space-between;gap:8px;padding:4px 0;border-bottom:1px solid #f0f0f0}\
.cvr-li button{border:0;background:none;color:#c62828;cursor:pointer}\
#cvr-checkout{margin:0 12px 8px;width:calc(100% - 24px);border:0;background:#f59e0b;color:#fff;border-radius:8px;padding:9px;font-weight:700;cursor:pointer}\
#cvr-checkout:disabled{background:#ccc;cursor:default}\
#cvr-in{display:flex;border-top:1px solid #e3e6e3}\
#cvr-in input{flex:1;border:0;padding:12px;font-size:14px;outline:none}\
#cvr-in button{border:0;background:#fff;color:" + GREEN + ";font-weight:700;padding:0 14px;cursor:pointer}";
  document.head.appendChild(h("style", { text: css }));

  // ---------- UI shell ----------
  var msgs = h("div", { id: "cvr-msgs" });
  var input = h("input", { type: "text", placeholder: "Type your message…", maxlength: "500" });
  var cartSum = h("div", { id: "cvr-cartsum", onclick: function () { cartList.classList.toggle("open"); } });
  var cartList = h("div", { id: "cvr-cartlist" });
  var checkoutBtn = h("button", { id: "cvr-checkout", text: "Checkout", onclick: checkout });
  var box = h("div", { id: "cvr-box" }, [
    h("div", { id: "cvr-head" }, [
      h("span", { text: "Clover.pk Assistant" }),
      h("button", { text: "×", "aria-label": "Close", onclick: toggle }),
    ]),
    msgs,
    h("div", { id: "cvr-cartbar" }, [cartSum, cartList, checkoutBtn]),
    h("div", { id: "cvr-in" }, [
      input,
      h("button", { text: "Send", onclick: function () { send(input.value); } }),
    ]),
  ]);
  var launcher = h("button", { id: "cvr-btn", text: "💬", "aria-label": "Chat", onclick: toggle });
  document.body.appendChild(box);
  document.body.appendChild(launcher);
  input.addEventListener("keydown", function (e) { if (e.key === "Enter") send(input.value); });

  var greeted = false;
  function toggle() {
    box.classList.toggle("open");
    if (box.classList.contains("open") && !greeted) {
      greeted = true;
      bot("Assalam o Alaikum! 👋 I'm Clover.pk's virtual assistant. I can help you find school books, bundles and stationery, and build your cart.");
      var chips = h("div", { class: "cvr-chips" });
      ["HHS book bundle", "Stationery", "Toys"].forEach(function (t) {
        chips.appendChild(h("button", { class: "cvr-chip", text: t, onclick: function () { send(t); } }));
      });
      msgs.appendChild(chips);
    }
  }

  function scroll() { msgs.scrollTop = msgs.scrollHeight; }
  function bot(t) { var m = h("div", { class: "cvr-m cvr-bot", dir: "auto", text: t }); msgs.appendChild(m); scroll(); return m; }
  function me(t) { msgs.appendChild(h("div", { class: "cvr-m cvr-me", dir: "auto", text: t })); scroll(); }

  // ---------- product cards ----------
  function price(v) { return v.price || ""; }

  function renderCards(products) {
    if (!products || !products.length) return;
    var row = h("div", { class: "cvr-row" });
    products.forEach(function (p) { row.appendChild(card(p)); });
    msgs.appendChild(row);
    scroll();
  }

  function card(p) {
    var variants = p.variants || [];
    var sel = null;
    var priceEl = h("div", { class: "cvr-price", text: variants[0] ? price(variants[0]) : "" });
    var body = [];
    if (p.label) body.push(h("div", { class: "cvr-tag", text: "⭐ " + p.label }));
    body.push(h("div", { class: "cvr-title", text: p.title }));
    if (variants.length > 1) {
      sel = h("select");
      variants.forEach(function (v, i) {
        sel.appendChild(h("option", { value: v.id, text: v.title + " — " + price(v) }));
      });
      sel.addEventListener("change", function () {
        var v = variants.filter(function (x) { return x.id === sel.value; })[0];
        priceEl.textContent = v ? price(v) : "";
      });
      body.push(sel);
    }
    body.push(priceEl);
    var btn = h("button", { class: "cvr-add", text: "Add to cart" });
    btn.addEventListener("click", function () {
      var vid = sel ? sel.value : variants[0].id;
      btn.disabled = true;
      btn.textContent = "Adding…";
      post("/cart/add", { session_id: ensureSid(), handle: p.handle, variant_id: vid, quantity: 1 })
        .then(function (r) {
          updateCart(r.cart);
          if (r.ok) {
            btn.textContent = "Added ✓";
            setTimeout(function () { btn.disabled = false; btn.textContent = "Add more"; }, 1500);
          } else {
            btn.textContent = r.error || "Unavailable";
            setTimeout(function () { btn.disabled = false; btn.textContent = "Add to cart"; }, 2500);
          }
        })
        .catch(function () { btn.disabled = false; btn.textContent = "Try again"; });
    });
    body.push(btn);

    var top = p.image
      ? h("a", { href: p.url, target: "_blank", rel: "noopener" }, [h("img", { src: p.image, alt: p.title, loading: "lazy" })])
      : h("div", { class: "cvr-noimg", text: "📚" });
    return h("div", { class: "cvr-card" }, [top, h("div", { class: "b" }, body)]);
  }

  // ---------- cart ----------
  function ensureSid() {
    if (!sid) {
      sid = (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : "s" + Date.now() + Math.random().toString(16).slice(2);
      try { localStorage.setItem("clover_sid", sid); } catch (e) {}
    }
    return sid;
  }

  function updateCart(c) {
    if (c) cart = c;
    var n = cart.items.reduce(function (a, i) { return a + i.qty; }, 0);
    cartSum.textContent = "";
    cartSum.appendChild(h("span", { text: "🛒 Cart (" + n + ")" }));
    cartSum.appendChild(h("span", { text: cart.subtotal }));
    cartList.textContent = "";
    cart.items.forEach(function (i) {
      cartList.appendChild(h("div", { class: "cvr-li" }, [
        h("span", { text: i.qty + " × " + i.name }),
        h("span", {}, [
          document.createTextNode(i.line_total + " "),
          h("button", { text: "✕", title: "Remove", onclick: function () {
            post("/cart/remove", { session_id: ensureSid(), variant_id: i.variant_id }).then(function (r) { updateCart(r.cart); });
          } }),
        ]),
      ]));
    });
    checkoutBtn.disabled = n === 0;
  }

  function checkout() {
    if (!sid || !cart.items.length) return;
    checkoutBtn.disabled = true;
    post("/cart/checkout", { session_id: sid })
      .then(function (r) {
        if (r.url) {
          bot("Your cart is ready. Pick Cash on Delivery or PayFast on the next page 👇");
          window.open(r.url, "_blank");
        } else if (r.products && r.products.length) {
          bot("Before checkout, parents often pick these too 👇");
          renderCards(r.products);
          bot("Add any you like, then tap Checkout again.");
        } else if (r.error) {
          bot(r.error);
        }
      })
      .catch(function () { bot("Sorry, something went wrong. Please try again."); })
      .then(function () { checkoutBtn.disabled = !cart.items.length; });
  }

  // ---------- chat ----------
  function send(text) {
    text = (text || "").trim();
    if (!text || busy) return;
    input.value = "";
    busy = true;
    me(text);
    var typing = bot("…");
    post("/chat", { message: text, session_id: ensureSid() })
      .then(function (r) {
        sid = r.session_id || sid;
        try { localStorage.setItem("clover_sid", sid); } catch (e) {}
        typing.textContent = r.reply || "Sorry, I didn't get that.";
        renderCards(r.products);
        updateCart(r.cart);
      })
      .catch(function () {
        typing.textContent = "Sorry, I'm unavailable right now. Please WhatsApp us on 0301 5676256.";
      })
      .then(function () { busy = false; scroll(); });
  }

  updateCart();
})();
