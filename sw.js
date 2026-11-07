/* 画面の部品は保存して素早く開き、データ(calendar_data.js, news.js)は、つながるときは常に最新を取る */
var CACHE = "fukubukuro-v7";
var SHELL = ["./", "index.html", "manifest.webmanifest", "icons/icon-192.png", "icons/icon-512.png"];
self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(SHELL); }));
  self.skipWaiting();
});
self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (ks) {
    return Promise.all(ks.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }));
  self.clients.claim();
});
self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET" || new URL(req.url).origin !== location.origin) return;
  var isData = /calendar_data\.js|news\.js|genres_data\.js/.test(req.url);
  if (isData || req.mode === "navigate") {   // 最新を優先。つながらないときだけ、保存したものを出す
    // データは、ブラウザが覚えている古いものを使わず、毎回、サーバーから取り直す
    var go = isData ? fetch(req.url, { cache: "no-store" }) : fetch(req);
    e.respondWith(go.then(function (r) {
      var copy = r.clone(); caches.open(CACHE).then(function (c) { c.put(req, copy); }); return r;
    }).catch(function () { return caches.match(req).then(function (m) { return m || caches.match("index.html"); }); }));
    return;
  }
  e.respondWith(caches.match(req).then(function (m) { return m || fetch(req); }));
});
