/*
 * Clover.pk order assistant widget.
 * Add to the Shopify theme (theme.liquid, just before </body>):
 *   <script src="https://YOUR-RENDER-URL.onrender.com/widget.js" defer></script>
 * Change the brand colour below to match the site.
 */
(function () {
  var script = document.currentScript;
  var API = (script && script.dataset.api) || (script ? new URL(script.src).origin : "");
  var BRAND = "#1f6f43";
  var WHATSAPP = "0301 5676256";
  var sessionId = null;

  try { sessionId = localStorage.getItem("cloverbot_session"); } catch (e) {}

  // Wake the server (free Render plans sleep) so the first answer is quicker.
  fetch(API + "/").catch(function () {});

  var css = "\
.cb-btn,.cb-panel,.cb-panel *{box-sizing:border-box;font-family:inherit}\
.cb-btn{position:fixed;right:16px;bottom:16px;z-index:99998;background:" + BRAND + ";color:#fff;border:0;border-radius:24px;padding:12px 18px;font-size:15px;cursor:pointer}\
.cb-panel{position:fixed;right:16px;bottom:16px;z-index:99999;width:360px;max-width:calc(100vw - 32px);height:540px;max-height:calc(100vh - 32px);background:#fff;color:#1b1f1c;border:1px solid #d9ded8;border-radius:10px;display:none;flex-direction:column;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.12)}\
.cb-panel.cb-open{display:flex}\
.cb-head{background:" + BRAND + ";color:#fff;padding:12px 14px;display:flex;justify-content:space-between;align-items:center;gap:8px}\
.cb-title{font-size:16px;font-weight:600;line-height:1.2}\
.cb-sub{font-size:13px;opacity:.9;margin-top:2px}\
.cb-close{background:none;border:0;color:#fff;font-size:22px;line-height:1;cursor:pointer;padding:4px 8px}\
.cb-log{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:8px;background:#f6f7f5}\
.cb-msg{max-width:88%;padding:9px 12px;border-radius:10px;font-size:15px;line-height:1.45;white-space:pre-wrap;word-wrap:break-word}\
.cb-bot{background:#fff;border:1px solid #d9ded8;align-self:flex-start}\
.cb-user{background:" + BRAND + ";color:#fff;align-self:flex-end}\
.cb-msg a{color:inherit;font-weight:600;text-decoration:underline}\
.cb-chips{display:flex;flex-wrap:wrap;gap:6px}\
.cb-chip{background:#fff;border:1px solid " + BRAND + ";color:" + BRAND + ";border-radius:16px;padding:6px 12px;font-size:14px;cursor:pointer}\
.cb-row{display:flex;gap:8px;padding:10px;border-top:1px solid #d9ded8;background:#fff}\
.cb-input{flex:1;font-size:16px;padding:9px 10px;border:1px solid #b8c0b7;border-radius:8px;min-width:0}\
.cb-send{background:" + BRAND + ";color:#fff;border:0;border-radius:8px;padding:0 16px;font-size:15px;cursor:pointer}\
.cb-send:disabled{opacity:.5;cursor:default}\
.cb-btn:focus-visible,.cb-close:focus-visible,.cb-chip:focus-visible,.cb-send:focus-visible,.cb-input:focus-visible{outline:3px solid #f2b705;outline-offset:2px}\
@media(max-width:480px){.cb-panel{right:0;bottom:0;width:100vw;max-width:100vw;height:100%;max-height:100%;border-radius:0}}";

  var style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text) n.textContent = text;
    return n;
  }

  var btn = el("button", "cb-btn", "Chat to order");
  var panel = el("div", "cb-panel");
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "Clover.pk order assistant");

  var head = el("div", "cb-head");
  var titles = el("div");
  var sub = el("div", "cb-sub", "Books, bundles and stationery");
  titles.appendChild(el("div", "cb-title", "Clover.pk"));
  titles.appendChild(sub);
  var close = el("button", "cb-close", "\u00d7");
  close.setAttribute("aria-label", "Close chat");
  head.appendChild(titles);
  head.appendChild(close);

  var log = el("div", "cb-log");
  log.setAttribute("role", "log");
  log.setAttribute("aria-live", "polite");

  var row = el("div", "cb-row");
  var input = el("input", "cb-input");
  input.type = "text";
  input.maxLength = 500;
  input.placeholder = "Type your message";
  input.setAttribute("aria-label", "Your message");
  var send = el("button", "cb-send", "Send");
  row.appendChild(input);
  row.appendChild(send);

  panel.appendChild(head);
  panel.appendChild(log);
  panel.appendChild(row);
  document.body.appendChild(btn);
  document.body.appendChild(panel);

  function esc(s) {
    return s.replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function linkify(s) {
    return esc(s).replace(/https?:\/\/[^\s<]+[^\s<.,;:!?)]/g, function (url) {
      var label = url.indexOf("/cart/") > -1 ? "Open my cart and checkout" : url;
      return '<a href="' + url + '" target="_blank" rel="noopener">' + label + "</a>";
    });
  }

  function addMsg(text, who) {
    var m = el("div", "cb-msg " + (who === "user" ? "cb-user" : "cb-bot"));
    if (who === "user") m.textContent = text;
    else m.innerHTML = linkify(text);
    log.appendChild(m);
    log.scrollTop = log.scrollHeight;
    return m;
  }

  function showCart(cart) {
    var n = 0;
    (cart.items || []).forEach(function (i) { n += i.qty; });
    sub.textContent = n
      ? "Cart: " + n + (n === 1 ? " item" : " items") + " \u00b7 " + cart.subtotal
      : "Books, bundles and stationery";
  }

  var busy = false;
  function ask(text) {
    text = text.trim();
    if (!text || busy) return;
    busy = true;
    send.disabled = true;
    input.value = "";
    var chips = log.querySelector(".cb-chips");
    if (chips) chips.remove();
    addMsg(text, "user");
    var wait = addMsg("Typing\u2026", "bot");

    fetch(API + "/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, session_id: sessionId }),
    })
      .then(function (r) {
        if (!r.ok) throw new Error("bad status");
        return r.json();
      })
      .then(function (data) {
        sessionId = data.session_id;
        try { localStorage.setItem("cloverbot_session", sessionId); } catch (e) {}
        wait.innerHTML = linkify(data.reply);
        showCart(data.cart || {});
      })
      .catch(function () {
        wait.textContent = "Sorry, I can't reach the assistant right now. Please WhatsApp us on " + WHATSAPP + ".";
      })
      .then(function () {
        busy = false;
        send.disabled = false;
        log.scrollTop = log.scrollHeight;
        input.focus();
      });
  }

  function greet() {
    addMsg("Assalam o Alaikum! I can help you find books and stationery and prepare your order. What are you looking for?", "bot");
    var chips = el("div", "cb-chips");
    ["Book bundle for my child's class", "Stationery", "Payment and delivery"].forEach(function (t) {
      var c = el("button", "cb-chip", t);
      c.onclick = function () { ask(t); };
      chips.appendChild(c);
    });
    log.appendChild(chips);
  }

  var greeted = false;
  function open() {
    panel.classList.add("cb-open");
    btn.style.display = "none";
    if (!greeted) { greeted = true; greet(); }
    input.focus();
  }
  function shut() {
    panel.classList.remove("cb-open");
    btn.style.display = "";
    btn.focus();
  }

  btn.onclick = open;
  close.onclick = shut;
  send.onclick = function () { ask(input.value); };
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter") ask(input.value);
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && panel.classList.contains("cb-open")) shut();
  });
})();
