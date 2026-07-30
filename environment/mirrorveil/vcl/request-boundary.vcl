# Starter request boundary: route ordinary traffic without scored edge policy.

sub mirror_request_boundary_recv {
    unset req.http.X-Mirror-Control;
    unset req.http.X-Ban-Class;

    if (req.method != "GET" && req.method != "HEAD") {
        return (pass);
    }

    return (pass);
}
