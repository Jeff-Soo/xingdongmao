const CACHE_NAME = 'pattern-v2';
const urlsToCache = [
    '/',
    '/static/manifest.json',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png',
];

// 安装：缓存关键资源
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
    );
    // 强制立即激活，不等待旧 SW 释放页面
    self.skipWaiting();
});

// 激活：清理旧缓存
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        ).then(() => self.clients.claim())
    );
});

// 拦截请求：网络优先（有网拿最新），网络失败才走缓存
self.addEventListener('fetch', event => {
    // 跳过非 GET 请求和非 http/https 请求
    if (event.request.method !== 'GET') return;
    const url = new URL(event.request.url);
    if (!url.protocol.startsWith('http')) return;

    event.respondWith(
        fetch(event.request)
            .then(fetchResponse => {
                // 缓存成功的 GET 响应
                if (fetchResponse.status === 200) {
                    const cloned = fetchResponse.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(event.request, cloned));
                }
                return fetchResponse;
            })
            .catch(() => {
                // 网络失败 → 尝试缓存回退
                return caches.match(event.request).then(cached => {
                    if (cached) return cached;
                    // 如果是导航请求，返回离线页面
                    if (event.request.mode === 'navigate') {
                        return caches.match('/');
                    }
                    return new Response('Offline – 请检查网络连接', { status: 503 });
                });
            })
    );
});
