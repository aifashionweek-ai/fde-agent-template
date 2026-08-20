"""update.py — regenerate derived artifacts from MASTERSCHEMA + MANIFEST and prove guards.
Usage: python update.py [--check] [--evals <experiment>]
  --check : drift checks + pytest (catch-proven guards)
  --evals : additionally run evals/gate.py against a Braintrust experiment (D-014)
"""
import re, subprocess, sys, json, pathlib
ROOT = pathlib.Path(__file__).parent

def parse_manifest():
    rows = []
    for line in (ROOT/"MANIFEST.md").read_text().splitlines():
        m = re.match(r"\|\s*(D-\d{3}|D-0xx)\s*\|(.*?)\|(.*?)\|(.*?)\|", line)
        if m: rows.append(dict(id=m[1], directive=m[2].strip(), guard=m[3].strip(), status=m[4].strip()))
    return rows

def parse_tools():
    tools = []
    in_tools = False
    for line in (ROOT/"MASTERSCHEMA.md").read_text().splitlines():
        if line.startswith("## Tool registry"): in_tools = True; continue
        if in_tools and line.startswith("## "): break
        if in_tools:
            m = re.match(r"\|\s*(\w+)\s*\|\s*(\w+)\s*\|\s*(\w+)\s*\|\s*(\d+)s", line)
            if m: tools.append(dict(name=m[1], side_effect=m[2].lower()=="yes",
                                    approval=m[3].lower()=="yes", timeout=int(m[4])))
    return tools

def main():
    manifest = parse_manifest(); tools = parse_tools()
    reg = ROOT/"agent"/"tool_registry.json"
    reg.write_text(json.dumps(tools, indent=2))
    print(f"[update] wrote {reg} ({len(tools)} tools)")
    print(f"[update] MANIFEST rows: {len(manifest)}; open: {[r['id'] for r in manifest if '⬜' in r['status']]}")
    # Drift checks: every tool in code is in MASTERSCHEMA, every D-row has a guard path that exists.
    import importlib.util
    spec = importlib.util.spec_from_file_location("t", ROOT/"agent"/"tools.py"); 
    names_in_schema = {t["name"] for t in tools}
    code = (ROOT/"agent"/"tools.py").read_text()
    decl = set(re.findall(r"^def (\w+)\(", code, re.M)) - {"tool_needs_approval"}
    missing = decl - names_in_schema
    if missing: print(f"[update] DRIFT: tools in code not in MASTERSCHEMA: {sorted(missing)}"); sys.exit(2)
    extra = names_in_schema - decl
    if extra: print(f"[update] DRIFT: tools in MASTERSCHEMA not in code (parse error or stale?): {sorted(extra)}"); sys.exit(2)
    # Count cross-check: a @tool in code must have produced a registry row. If the table parsed fewer
    # rows than the code has tools, a MASTERSCHEMA row failed the regex (e.g. a stray unicode char).
    n_code = len([d for d in decl])
    if len(tools) != n_code:
        print(f"[update] DRIFT: parsed {len(tools)} registry rows but code declares {n_code} @tool fns.")
        print(f"         code tools: {sorted(decl)}")
        print(f"         parsed:     {sorted(names_in_schema)}")
        print(f"         A MASTERSCHEMA tool-table row failed to parse. Check for trailing spaces / unicode dashes / 'yes' vs digits.")
        sys.exit(2)
    for r in manifest:
        g = r["guard"].split("::")[0].split(" ")[0].strip(" ·")
        if g and not (ROOT/g).exists() and r["id"] != "D-0xx":
            print(f"[update] DRIFT: {r['id']} guard path missing: {g}"); sys.exit(2)
    if "--check" in sys.argv:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"], cwd=ROOT)
        if r.returncode: sys.exit(r.returncode)
        if "--evals" in sys.argv:
            exp = (sys.argv[sys.argv.index("--evals")+1:] or ["baseline"])[0]
            r = subprocess.run([sys.executable, "-m", "evals.gate", exp], cwd=ROOT); sys.exit(r.returncode)
        sys.exit(0)

if __name__ == "__main__": main()
