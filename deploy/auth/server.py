#!/usr/bin/env python3
"""FinBridge AI auth service (stdlib only). Binds 127.0.0.1; nginx proxies /api/auth/ and /api/users/.
- Passwords: scrypt (n=2^15,r=8,p=1) + per-user salt.
- MFA: TOTP (RFC 6238, SHA1, 30 s, 6 digits, ±1 step, replay-protected) + 8 one-time backup codes (stored hashed).
- Sessions: random token in httpOnly Secure SameSite=Strict cookie; only SHA-256 stored. Session stages:
  'setup' (must change password and/or enrol MFA), 'mfa' (password OK, awaiting code), 'full'. Only 'full' passes /check.
- Append-only user log (SQLite triggers block UPDATE/DELETE on events). Never logs passwords, codes or secrets.
- No hard delete of users: disable only."""
import base64, hashlib, hmac, json, os, re, secrets, sqlite3, struct, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, parse_qs, urlsplit

DB = os.environ.get('FB_DB', '/var/lib/finbridge-auth/auth.db')
PORT = int(os.environ.get('FB_PORT', '3420'))
ISSUER = 'FinBridge AI'
COOKIE = 'fb_session'; TTL = 12 * 3600; PENDING_TTL = 15 * 60
ROLES = ('global_admin', 'admin')
ACTING = ('PREPARER', 'VP_FINANCE', 'DIRECTOR_FINANCE')
# CredAssure gateway bridge: after a full (password + MFA) session, hand the browser a short-lived gateway JWT.
# FB_GATEWAY_USERS = JSON {"preparer": "<gateway user id>", "director_finance": "...", "vp_finance": "...", "evaluator": "..."}.
# The gateway re-checks the user row on every request, so a disabled gateway user stops working at once.
GW_SECRET = os.environ.get('FB_JWT_SECRET', ''); GW_TENANT = os.environ.get('FB_GATEWAY_TENANT', 'default'); GW_TTL = 900
try: GW_USERS = json.loads(os.environ.get('FB_GATEWAY_USERS', '{}'))
except ValueError: GW_USERS = {}
def b64u(b): return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
def gateway_jwt(sub, role, now):
    h = b64u(json.dumps({'alg': 'HS256', 'typ': 'JWT'}, separators=(',', ':')).encode())
    c = b64u(json.dumps({'iss': 'credassure', 'aud': 'credassure', 'sub': sub, 'role': role, 'tenant': GW_TENANT, 'iat': now, 'exp': now + GW_TTL}, separators=(',', ':')).encode())
    return f'{h}.{c}.' + b64u(hmac.new(GW_SECRET.encode(), f'{h}.{c}'.encode(), hashlib.sha256).digest())

def db():
    c = sqlite3.connect(DB, timeout=10); c.row_factory = sqlite3.Row; return c
def cols(c, t): return [r[1] for r in c.execute(f'pragma table_info({t})')]
def init():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    with db() as c:
        c.executescript('''create table if not exists users(username text primary key, name text not null, role text not null,
          pw text not null, must_change int not null default 1, disabled int not null default 0, created_at int, updated_at int);
          create table if not exists sessions(token_hash text primary key, username text not null, expires int not null);
          create table if not exists events(at int, actor text, action text, target text, ip text);''')
        uc = cols(c, 'users')
        for col, ddl in [('totp_secret', 'text'), ('totp_pending', 'text'), ('totp_enabled', 'int not null default 0'), ('totp_last_step', 'int not null default 0'), ('backup_codes', "text not null default '[]'")]:
            if col not in uc: c.execute(f'alter table users add column {col} {ddl}')
        if 'stage' not in cols(c, 'sessions'): c.execute("alter table sessions add column stage text not null default 'full'")
        ec = cols(c, 'events')
        for col in ('ua', 'detail'):
            if col not in ec: c.execute(f'alter table events add column {col} text')
        c.executescript('''create trigger if not exists events_no_update before update on events begin select raise(abort, 'append-only'); end;
          create trigger if not exists events_no_delete before delete on events begin select raise(abort, 'append-only'); end;''')

def hash_pw(p, salt=None):
    salt = salt or secrets.token_bytes(16)
    h = hashlib.scrypt(p.encode(), salt=salt, n=2**15, r=8, p=1, maxmem=64 * 1024 * 1024, dklen=32)
    return 'scrypt$' + salt.hex() + '$' + h.hex()
def check_pw(p, stored):
    try: _, s, h = stored.split('$'); return hmac.compare_digest(hash_pw(p, bytes.fromhex(s)).split('$')[2], h)
    except Exception: return False
DUMMY = hash_pw('dummy-password-for-timing')

WORDS = 'amber river cedar falcon maple orbit pixel quartz saffron tiger lotus monsoon copper delta harbor indigo jasmine kestrel lagoon meadow nebula opal pepper ridge summit tamarind velvet willow'.split()
def temp_password():
    return f"{secrets.choice(WORDS).capitalize()}-{secrets.choice(WORDS)}-{secrets.choice(WORDS)}-{secrets.randbelow(900)+100}"
def valid_new(p): return len(p) >= 12 and re.search(r'[A-Za-z]', p) and re.search(r'\d', p)

# ---- TOTP (RFC 6238) ----
def totp_at(secret_b32, step):
    key = base64.b32decode(secret_b32 + '=' * (-len(secret_b32) % 8))
    h = hmac.new(key, struct.pack('>Q', step), hashlib.sha1).digest(); o = h[-1] & 15
    return '%06d' % ((struct.unpack('>I', h[o:o + 4])[0] & 0x7fffffff) % 1000000)
def totp_match(secret, code, last_step=0):
    """Returns matched step or None. Window ±1 step; rejects steps <= last_step (replay)."""
    code = re.sub(r'\s', '', str(code))
    if not re.fullmatch(r'\d{6}', code): return None
    now = int(time.time()) // 30
    for st in (now - 1, now, now + 1):
        if st > last_step and hmac.compare_digest(totp_at(secret, st), code): return st
    return None
def bc_hash(code): return hashlib.sha256(('fb-bc:' + code.replace('-', '').lower()).encode()).hexdigest()
def new_backup_codes():
    codes = ['%s-%s' % (secrets.token_hex(2), secrets.token_hex(2)) for _ in range(8)]
    return codes, json.dumps([bc_hash(x) for x in codes])

# rate limiting (in-memory, sliding 15 min)
fails = {}; flock = threading.Lock()
def limited(key, maxn):
    with flock:
        now = time.time(); keep = [t for t in fails.get(key, []) if now - t < 900]; fails[key] = keep; return len(keep) >= maxn
def fail(key):
    with flock: fails.setdefault(key, []).append(time.time())

def public(u, stage=None):
    d = {'username': u['username'], 'name': u['name'], 'accountRole': u['role'], 'mustChangePassword': bool(u['must_change']),
         'disabled': bool(u['disabled']), 'mfaEnabled': bool(u['totp_enabled'])}
    if stage: d['stage'] = stage
    return d
def stage_for(u): return 'setup' if (u['must_change'] or not u['totp_enabled']) else 'mfa'

class H(BaseHTTPRequestHandler):
    server_version = 'fb-auth'; sys_version = ''
    def log_message(self, fmt, *a): sys.stderr.write('%s %s\n' % (self.ip(), fmt % a))  # request line only, never bodies
    def ip(self): return self.headers.get('X-Real-IP') or self.client_address[0]
    def ua(self): return (self.headers.get('User-Agent') or '')[:300]
    def log(self, actor, action, target='', detail=''):
        with db() as c: c.execute('insert into events(at,actor,action,target,ip,ua,detail) values(?,?,?,?,?,?,?)', (int(time.time()), actor, action, target, self.ip(), self.ua(), detail[:300]))
    def send(self, code, obj=None, cookie=None):
        b = json.dumps(obj if obj is not None else {}).encode(); self.send_response(code)
        self.send_header('Content-Type', 'application/json'); self.send_header('Cache-Control', 'no-store')
        if cookie is not None: self.send_header('Set-Cookie', cookie)
        self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
    def body(self):
        n = int(self.headers.get('Content-Length') or 0)
        if n > 10000: return {}
        try: return json.loads(self.rfile.read(n) or b'{}')
        except Exception: return {}
    def token(self):
        m = re.search(COOKIE + r'=([A-Za-z0-9_\-]+)', self.headers.get('Cookie', '')); return m.group(1) if m else None
    def sess(self):
        """(user_row, stage, token_hash) or (None, None, None)."""
        t = self.token()
        if not t: return None, None, None
        th = hashlib.sha256(t.encode()).hexdigest()
        with db() as c:
            s = c.execute('select * from sessions where token_hash=? and expires>?', (th, int(time.time()))).fetchone()
            if not s: return None, None, None
            u = c.execute('select * from users where username=? and disabled=0', (s['username'],)).fetchone()
            return (u, s['stage'], th) if u else (None, None, None)
    def new_session(self, un, stage):
        tok = secrets.token_urlsafe(32); ttl = TTL if stage == 'full' else PENDING_TTL
        with db() as c:
            c.execute('delete from sessions where expires<?', (int(time.time()),))
            c.execute('insert into sessions(token_hash,username,expires,stage) values(?,?,?,?)', (hashlib.sha256(tok.encode()).hexdigest(), un, int(time.time()) + ttl, stage))
        return f'{COOKIE}={tok}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age={ttl}'
    def upgrade(self, th, un):
        with db() as c: c.execute("update sessions set stage='full', expires=? where token_hash=?", (int(time.time()) + TTL, th))
    def csrf_ok(self):
        return self.headers.get('Content-Type', '').startswith('application/json') and self.headers.get('X-Requested-With') == 'finbridge'

    def do_GET(self):
        p = self.path.split('?')[0]
        if p == '/api/auth/check':
            u, st, _ = self.sess(); return self.send(204 if u and st == 'full' else 401)
        if p == '/api/auth/me':
            u, st, _ = self.sess(); return self.send(200, public(u, st)) if u else self.send(401, {'error': 'Not signed in'})
        if p == '/api/auth/gateway-token':
            u, st, _ = self.sess()
            if not u or st != 'full': return self.send(401, {'error': 'Not signed in'})
            if self.headers.get('X-Requested-With') != 'finbridge': return self.send(403, {'error': 'Forbidden'})
            role = (parse_qs(urlsplit(self.path).query).get('role') or [''])[0]
            if len(GW_SECRET) < 32 or role not in GW_USERS: return self.send(503, {'error': 'Gateway bridge is not configured'})
            if role == 'evaluator' and u['role'] != 'global_admin': return self.send(403, {'error': 'Global Admin only'})
            self.log(u['username'], 'GATEWAY_TOKEN', u['username'], role)
            return self.send(200, {'token': gateway_jwt(GW_USERS[role], role, int(time.time())), 'expiresIn': GW_TTL})
        u, st, _ = self.sess()
        if not u or st != 'full': return self.send(401, {'error': 'Not signed in'})
        if u['role'] != 'global_admin': return self.send(403, {'error': 'Global Admin only'})
        with db() as c:
            if p == '/api/users/':
                return self.send(200, [public(x) | {'createdAt': x['created_at']} for x in c.execute('select * from users order by role desc, name')])
            if p == '/api/users/logs':
                rows = c.execute('select rowid as id, at, actor, action, target, ip, ua, detail from events order by at desc, rowid desc limit 5000').fetchall()
                return self.send(200, [dict(r) for r in rows])
        self.send(404, {'error': 'Not found'})

    def do_POST(self):
        p = self.path.split('?')[0]
        if not self.csrf_ok(): return self.send(400, {'error': 'Bad request'})
        b = self.body(); ip = self.ip()
        if p == '/api/auth/login':
            un = str(b.get('username', '')).strip().lower()[:64]; pw = str(b.get('password', ''))[:200]
            if limited('ip:' + ip, 20) or limited('u:' + un, 5):
                self.log(un, 'LOGIN_FAIL', un, 'rate limited'); return self.send(429, {'error': 'Too many attempts. Try again in 15 minutes.'})
            with db() as c: u = c.execute('select * from users where username=?', (un,)).fetchone()
            ok = check_pw(pw, u['pw'] if u else DUMMY) and u and not u['disabled']
            if not ok:
                fail('ip:' + ip); fail('u:' + un)
                self.log(un, 'LOGIN_FAIL', un, 'invalid credentials' if not (u and u['disabled']) else 'account disabled')
                return self.send(401, {'error': 'Invalid username or password'})
            st = stage_for(u)
            self.log(un, 'LOGIN_PASSWORD_OK', un, 'awaiting MFA code' if st == 'mfa' else ('must change password' if u['must_change'] else 'MFA enrolment required'))
            return self.send(200, public(u, st), self.new_session(un, st))
        if p == '/api/auth/logout':
            t = self.token()
            if t:
                u, _, _ = self.sess()
                with db() as c: c.execute('delete from sessions where token_hash=?', (hashlib.sha256(t.encode()).hexdigest(),))
                if u: self.log(u['username'], 'LOGOUT', u['username'])
            return self.send(200, {}, f'{COOKIE}=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0')
        u, st, th = self.sess()
        if not u: return self.send(401, {'error': 'Not signed in'})
        un = u['username']
        if p == '/api/auth/mfa/verify':  # second factor at login
            if st != 'mfa': return self.send(400, {'error': 'No MFA challenge pending'})
            if limited('mfa:' + un, 5):
                self.log(un, 'LOGIN_FAIL', un, 'MFA rate limited'); return self.send(429, {'error': 'Too many attempts. Try again in 15 minutes.'})
            code = str(b.get('code', '')).strip()[:20]
            stp = totp_match(u['totp_secret'], code, u['totp_last_step'])
            if stp:
                with db() as c: c.execute('update users set totp_last_step=? where username=?', (stp, un))
                how = 'authenticator code'
            else:
                hs = json.loads(u['backup_codes'] or '[]'); h = bc_hash(code)
                if h not in hs:
                    fail('mfa:' + un); self.log(un, 'LOGIN_FAIL', un, 'invalid MFA code'); return self.send(401, {'error': 'Invalid code'})
                hs.remove(h)
                with db() as c: c.execute('update users set backup_codes=? where username=?', (json.dumps(hs), un))
                how = f'backup code ({len(hs)} left)'
            self.upgrade(th, un); self.log(un, 'LOGIN_SUCCESS', un, 'MFA via ' + how)
            return self.send(200, public(u, 'full'))
        if p == '/api/auth/change-password':
            cur, new = str(b.get('currentPassword', '')), str(b.get('newPassword', ''))
            if st == 'mfa': return self.send(400, {'error': 'Complete sign-in first'})
            if limited('cp:' + un, 5): return self.send(429, {'error': 'Too many attempts. Try again later.'})
            if not check_pw(cur, u['pw']):
                fail('cp:' + un); self.log(un, 'PASSWORD_CHANGE_FAIL', un, 'wrong current password'); return self.send(400, {'error': 'Current password or code is incorrect'})
            stp = None
            if u['totp_enabled']:
                stp = totp_match(u['totp_secret'], b.get('code', ''), u['totp_last_step'])
                if not stp:
                    fail('cp:' + un); self.log(un, 'PASSWORD_CHANGE_FAIL', un, 'invalid MFA code'); return self.send(400, {'error': 'Current password or code is incorrect'})
            if not valid_new(new) or new == cur: return self.send(400, {'error': 'New password must be at least 12 characters, include letters and a number, and differ from the current one'})
            with db() as c:
                c.execute('update users set pw=?, must_change=0, updated_at=?' + (', totp_last_step=?' if stp else '') + ' where username=?',
                          ((hash_pw(new), int(time.time()), stp, un) if stp else (hash_pw(new), int(time.time()), un)))
                c.execute('delete from sessions where username=? and token_hash<>?', (un, th))  # sign out other sessions
            self.log(un, 'PASSWORD_CHANGED', un, 'first-login change' if u['must_change'] else 'self-service (password + MFA)')
            with db() as c: u2 = c.execute('select * from users where username=?', (un,)).fetchone()
            return self.send(200, public(u2, st))
        if p == '/api/auth/mfa/setup':  # start enrolment: returns otpauth URI (secret shown to the user only)
            if st != 'setup' or u['must_change'] or u['totp_enabled']: return self.send(400, {'error': 'MFA enrolment not available'})
            sec = base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')
            with db() as c: c.execute('update users set totp_pending=? where username=?', (sec, un))
            uri = f'otpauth://totp/{quote(ISSUER)}:{quote(un)}?secret={sec}&issuer={quote(ISSUER)}&algorithm=SHA1&digits=6&period=30'
            return self.send(200, {'secret': sec, 'otpauthUri': uri})
        if p == '/api/auth/mfa/enable':
            if st != 'setup' or u['must_change'] or u['totp_enabled'] or not u['totp_pending']: return self.send(400, {'error': 'MFA enrolment not available'})
            if limited('mfa:' + un, 5): return self.send(429, {'error': 'Too many attempts. Try again in 15 minutes.'})
            stp = totp_match(u['totp_pending'], b.get('code', ''))
            if not stp: fail('mfa:' + un); self.log(un, 'MFA_ENROL_FAIL', un, 'invalid code'); return self.send(400, {'error': 'That code did not match. Check the time on your phone and try again.'})
            codes, hashes = new_backup_codes()
            with db() as c: c.execute('update users set totp_secret=totp_pending, totp_pending=null, totp_enabled=1, totp_last_step=?, backup_codes=?, updated_at=? where username=?', (stp, hashes, int(time.time()), un))
            self.upgrade(th, un); self.log(un, 'MFA_ENROLLED', un, '8 backup codes issued'); self.log(un, 'LOGIN_SUCCESS', un, 'after MFA enrolment')
            return self.send(200, {'backupCodes': codes})
        if st != 'full': return self.send(401, {'error': 'Not signed in'})
        if p == '/api/auth/event':  # client-reported workflow events (whitelisted)
            role = str(b.get('actingRole', ''))
            if b.get('action') == 'ACTING_ROLE_SWITCH' and role in ACTING:
                self.log(un, 'ACTING_ROLE_SWITCH', un, role); return self.send(200, {})
            return self.send(400, {'error': 'Bad request'})
        if not p.startswith('/api/users/'): return self.send(404, {'error': 'Not found'})
        if u['role'] != 'global_admin': return self.send(403, {'error': 'Global Admin only'})
        if p == '/api/users/':
            name = str(b.get('name', '')).strip()[:80]; nu = str(b.get('username', '')).strip().lower()[:64]; role = b.get('role', 'admin')
            if not name or not re.fullmatch(r'[a-z][a-z0-9.\-]{2,63}', nu) or role not in ROLES: return self.send(400, {'error': 'Name, username (lowercase, e.g. first.last) and role are required'})
            tp = temp_password()
            try:
                with db() as c: c.execute('insert into users(username,name,role,pw,must_change,disabled,created_at,updated_at) values(?,?,?,?,1,0,?,?)', (nu, name, role, hash_pw(tp), int(time.time()), int(time.time())))
            except sqlite3.IntegrityError: return self.send(409, {'error': 'Username already exists'})
            self.log(un, 'USER_CREATED', nu, role)
            return self.send(201, {'username': nu, 'temporaryPassword': tp})
        m = re.fullmatch(r'/api/users/([a-z0-9.\-]+)/(reset-password|disable|enable|reset-mfa)', p)
        if not m: return self.send(404, {'error': 'Not found'})
        tu, act = m.groups()
        if tu == un and act in ('disable', 'reset-mfa'): return self.send(400, {'error': 'You cannot do that to your own account'})
        tp = None
        with db() as c:
            if not c.execute('select 1 from users where username=?', (tu,)).fetchone(): return self.send(404, {'error': 'No such user'})
            if act == 'reset-password':
                tp = temp_password(); c.execute('update users set pw=?, must_change=1, updated_at=? where username=?', (hash_pw(tp), int(time.time()), tu))
            elif act == 'reset-mfa':
                c.execute("update users set totp_secret=null, totp_pending=null, totp_enabled=0, totp_last_step=0, backup_codes='[]', updated_at=? where username=?", (int(time.time()), tu))
            else:
                c.execute('update users set disabled=?, updated_at=? where username=?', (1 if act == 'disable' else 0, int(time.time()), tu))
            if act != 'enable': c.execute('delete from sessions where username=?', (tu,))
        self.log(un, {'reset-password': 'USER_PASSWORD_RESET', 'disable': 'USER_DISABLED', 'enable': 'USER_ENABLED', 'reset-mfa': 'USER_MFA_RESET'}[act], tu)
        return self.send(200, {'username': tu, 'temporaryPassword': tp} if tp else {'username': tu, 'disabled': act == 'disable'})

def cli():
    # python3 server.py create [--password-stdin] <username> <role> <name...>  -> prints JSON (temp password only if generated)
    # python3 server.py disable <username>
    init(); args = sys.argv[1:]; from_stdin = '--password-stdin' in args; args = [a for a in args if a != '--password-stdin']
    def ev(action, target, detail=''):
        with db() as c: c.execute('insert into events(at,actor,action,target,ip,ua,detail) values(?,?,?,?,?,?,?)', (int(time.time()), 'cli', action, target, 'server', 'cli', detail))
    if args[0] == 'disable':
        with db() as c: c.execute('update users set disabled=1 where username=?', (args[1],)); c.execute('delete from sessions where username=?', (args[1],))
        ev('USER_DISABLED', args[1]); print(json.dumps({'username': args[1], 'disabled': True})); return
    cmd, un, role, *name = args
    assert cmd == 'create' and role in ROLES
    tp = sys.stdin.readline().rstrip('\n') if from_stdin else temp_password()
    assert len(tp) >= 12
    with db() as c: c.execute('insert into users(username,name,role,pw,must_change,disabled,created_at,updated_at) values(?,?,?,?,1,0,?,?)', (un, ' '.join(name), role, hash_pw(tp), int(time.time()), int(time.time())))
    ev('USER_CREATED', un, role)
    print(json.dumps({'username': un} if from_stdin else {'username': un, 'temporaryPassword': tp}))

if __name__ == '__main__':
    if len(sys.argv) > 1: cli()
    else:
        init(); print(f'fb-auth listening on 127.0.0.1:{PORT}', flush=True)
        ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()
