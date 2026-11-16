# Environments

TODO owner: [Name 1].

## dev
## test
## demo

## Hosted web (nginx, scope #52)
`deploy/nginx/finbridge.conf` serves the static export and proxies `/v1/` to the gateway. Install
`deploy/nginx/security-headers.conf` as `/etc/nginx/snippets/credassure-security-headers.conf`, then run `nginx -t`.
nginx drops every inherited `add_header` in a block that sets its own, so each such `location` includes the snippet
again; `tests/test_nginx_headers.py` fails if one does not.
