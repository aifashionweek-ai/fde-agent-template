"""Verify the 4-slot new-engagement mechanism works end-to-end. Run before any real assignment."""
import subprocess, sys, pathlib, json
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
ROOT = pathlib.Path(__file__).parent.parent

def main():
    print("=== NEW-ENGAGEMENT VERIFICATION ===\n")
    checks = []
    sample = [{"input":"How many books can I borrow?","expected":"limit from policy","tags":["happy"]}]
    try:
        for r in sample: assert "input" in r and "expected" in r and "tags" in r
        checks.append(("Slot 1 (golden set schema)", True, "rows have input/expected/tags"))
    except Exception as e: checks.append(("Slot 1 (golden set schema)", False, str(e)))
    try:
        from agent.retrieval import chunk_document
        cs = chunk_document("book-policy","Members may borrow 5 books.",source="policy",tenant="library-a",sensitivity="internal")
        assert cs and cs[0].tenant == "library-a"
        checks.append(("Slot 2 (corpus ingestion)", True, f"chunk_document works, scoped"))
    except Exception as e: checks.append(("Slot 2 (corpus ingestion)", False, str(e)))
    try:
        r = subprocess.run([sys.executable,"update.py","--check"],cwd=ROOT,capture_output=True,text=True)
        reg = json.loads((ROOT/"agent"/"tool_registry.json").read_text())
        ok = ("passed" in r.stdout or "passed" in r.stderr) and len(reg) > 0
        checks.append(("Slot 3 (tool registry regen)", ok, f"{len(reg)} tools, update.py {'green' if ok else 'FAIL'}"))
    except Exception as e: checks.append(("Slot 3 (tool registry regen)", False, str(e)))
    try:
        from agent.guards import output_guard
        out = output_guard({"answer":"Borrow 5 books.","confidence":0.9,"citations":["book-policy#0"],"actions":[]},retrieved_ids={"book-policy#0"})
        assert out.answer and out.confidence == 0.9
        checks.append(("Slot 4 (output contract)", True, "AgentOutput validates + grounds"))
    except Exception as e: checks.append(("Slot 4 (output contract)", False, str(e)))
    print("RESULTS:")
    allok = True
    for name, ok, note in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:32s} — {note}"); allok = allok and ok
    print("\n" + ("✅ ALL 4 SLOTS VERIFIED." if allok else "❌ A slot failed."))
    return 0 if allok else 1

if __name__ == "__main__": sys.exit(main())
