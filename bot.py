import json, os, time, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(ROOT, "config.json")))
STATE_PATH = os.path.join(ROOT, "state.json")
WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")
TORN_KEY = os.environ.get("TORN_API_KEY", "")
DRY = os.environ.get("DRY_RUN") == "1"
UA = {"User-Agent": "monstro-preto-bot"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return json.load(r)


def send(role_id, text):
    msg = f"<@&{role_id}> {text}"
    print(msg)
    if DRY or not WEBHOOK:
        return
    body = json.dumps({"content": msg, "allowed_mentions": {"roles": [role_id]}}).encode()
    req = urllib.request.Request(WEBHOOK, body, {**UA, "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=20)


def check_foreign(state):
    data = get("https://yata.yt/api/v1/travel/export/")
    seen = state.setdefault("foreign", {})
    for country, info in data.get("stocks", {}).items():
        for it in info.get("stocks", []):
            for rule in CFG["foreign"]:
                if not any(m.lower() in it["name"].lower() for m in rule["match"]):
                    continue
                key = f"{country}:{it['name']}"
                in_stock = it["quantity"] >= rule["min_quantity"]
                if in_stock and not seen.get(key):
                    send(rule["role_id"],
                         f"✈️ **{it['name']}** is in stock in **{country.upper()}**: "
                         f"{it['quantity']} available at ${it['cost']:,}")
                seen[key] = in_stock


def check_armory(state):
    cats = sorted({r["category"] for r in CFG["armory"]})
    data = get(f"https://api.torn.com/faction/?selections={','.join(cats)}&key={TORN_KEY}")
    if "error" in data:
        raise RuntimeError(data["error"])
    last = state.setdefault("armory", {})
    now = time.time()
    for rule in CFG["armory"]:
        items = data.get(rule["category"]) or []
        if isinstance(items, dict):
            items = list(items.values())
        have = {i["name"]: i.get("available", 0) for i in items}
        names = rule.get("watch") or list(have)
        for name in names:
            minimum = rule.get("overrides", {}).get(name, rule["min_available"])
            avail = have.get(name, 0)
            if avail >= minimum:
                continue
            key = f"{rule['category']}:{name}"
            if now - last.get(key, 0) >= rule.get("cooldown_hours", 6) * 3600:
                send(rule["role_id"], f"📦 Armory low on **{name}**: {avail} left (want {minimum}+)")
                last[key] = now


def main():
    try:
        state = json.load(open(STATE_PATH))
    except Exception:
        state = {}
    failed = False
    for fn in (check_foreign, check_armory):
        try:
            fn(state)
        except Exception as e:
            failed = True
            print(f"{fn.__name__} failed: {e}")
    json.dump(state, open(STATE_PATH, "w"), indent=1)
    if failed:
        raise SystemExit(1)


main()
                           
