# /// script
# requires-python = ">=3.11"
# dependencies = ["PyYAML==6.0.3", "markdown-it-py==4.0.0"]
# ///
import sys
sys.dont_write_bytecode = True
import hashlib, json, subprocess, tempfile
from pathlib import Path
import yaml

out = Path(__file__).resolve().parent
root = Path(tempfile.mkdtemp(prefix="sdd-apply-native-")) / "project"
change = root / "sdd/changes/add"
meta = dict(schema_version=1, change_id="add", language="en")
def doc(path, metadata, records=(), prose=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + yaml.safe_dump(metadata) + "---\n\n" + prose + "\n" + "\n".join("### Record\n\n```yaml\n" + yaml.safe_dump(r) + "```\n" for r in records), encoding="utf-8")
task = dict(sdd_record="task", id="TASK-add", number=1, covers=["AC-add", "AC-invalid"], depends_on=[], status="pending", verification=[dict(criteria=["AC-add", "AC-invalid"], test_description="Exercise numeric addition and reject invalid/non-finite inputs and results", location="check.py", run={"setup_required":"Create check.py as a PEP 723 standard-library entry point plus uv lockfile. Run uv run --locked --script check.py; assert finite numeric addition and reject invalid inputs and overflow."})])
doc(change / "proposal.md", {**meta, "document_type":"proposal"}, prose="Replace string-concatenating add(a,b) with finite numeric addition.")
doc(change / "design.md", {**meta, "document_type":"design"}, prose="Keep add(a,b) in calculator.py. Accept Python int and float excluding bool. Reject other types with TypeError. Reject non-finite floats and non-finite results with ValueError. Preserve arbitrary precision integer addition. No external runtime dependencies.")
doc(change / "tasks.md", {**meta, "document_type":"tasks"}, [task], "Implement calculator.py and create check.py plus check.py.lock. These are the task owned paths.")
doc(change / "specs/calculator/spec.md", {**meta,"document_type":"spec","capability":"calculator"}, [dict(sdd_record="requirement", id="REQ-add", operation="add"), dict(sdd_record="acceptance", id="AC-add", requirement="REQ-add", conditions="Two int/float operands, excluding bool, finite when floating point", expected="Return arithmetic sum; integers retain arbitrary precision."), dict(sdd_record="acceptance",id="AC-invalid",requirement="REQ-add",conditions="Operands include bool, strings, None, containers, NaN or infinity; or floating result overflows to infinity",expected="TypeError for invalid types; ValueError for non-finite operands or result.")])
records=[]
for stage,kind in (("document_review","document_approval"),("plan_review","plan_approval")):
    names=["design.md","proposal.md","specs/calculator/spec.md"]+(["tasks.md"] if stage=="plan_review" else [])
    manifest=[dict(path=n,sha256=hashlib.sha256((change/n).read_bytes()).hexdigest()) for n in sorted(names)]
    for decision in (kind,"review_waiver"):
        records.append(dict(sdd_record="user", id="USER-"+stage.replace("_","-")+"-"+decision.replace("_","-"), kind=decision,scope={"stage":stage,**({"lenses":["plan" if stage=="plan_review" else "consistency"]} if decision=="review_waiver" else {})},response="Synthetic fixture approval authorized by the parent behavioral-evaluation assignment; no separate user approval is asserted.",date="2026-10-08T00:00:00Z",inputs=manifest))
doc(change/"review/decisions.md",{"schema_version":1},records)
doc(change/"state.md",{**meta,"document_type":"state","phase":"plan_approved","awaiting":"none","updated_at":"2026-10-08T00:00:00Z","document_links":["tasks.md"],"review_links":["review/decisions.md"],"approval_refs":[r["id"] for r in records]})
(root/"calculator.py").write_text('def add(a, b):\n    return str(a) + str(b)\n',encoding="utf-8")
for args in (("init",),("config","user.name","Behavioral Fixture"),("config","user.email","fixture@example.invalid"),("add","."),("commit","-m","Approved numeric-add fixture")):
    subprocess.run(["git","-C",str(root),*args],check=True,capture_output=True)
(out/"fixture.json").write_text(json.dumps({"project_root":str(root),"directory":str(change/"execution"),"change":"add","approval_source":"parent assignment: approved synthetic behavioral fixture","python":sys.executable},indent=2),encoding="utf-8")
print(root)
