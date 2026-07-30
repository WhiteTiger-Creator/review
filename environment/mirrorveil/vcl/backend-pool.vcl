# Backend pool and probe definitions for the two artifact origins.

probe mirror_health {
    .request =
        "GET /__mirror_health HTTP/1.1"
        "Host: health.mirrorveil.invalid"
        "Connection: close";
    .timeout = 200ms;
    .interval = 250ms;
    .window = 4;
    .threshold = 2;
    .initial = 1;
}

backend primary_origin {
    .host = "127.0.0.1";
    .port = "18191";
    .probe = mirror_health;
}

backend secondary_origin {
    .host = "127.0.0.1";
    .port = "18192";
    .probe = mirror_health;
}

sub mirror_backend_init {
    new mirror_pool = directors.fallback();
    mirror_pool.add_backend(primary_origin);
    mirror_pool.add_backend(secondary_origin);
}
