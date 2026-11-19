#!/usr/bin/env python3
"""Static safety linter for PostgreSQL migrations (stdlib only).

Exit codes: 0 = clean (or only waived findings), 1 = blocking findings, 2 = usage error.
Waive a rule per file with:  -- lint:allow R004 reason="why this is safe here"
Waivers never silently pass: they set needs_approval=true, which gates prod behind a DBRE reviewer.
"""
import argparse, json, os, re, sys
from dataclasses import dataclass, asdict

RULES = {
 "R001": "CREATE INDEX without CONCURRENTLY blocks writes for the whole build",
 "R002": "CONCURRENTLY needs '-- migrate:no-transaction' and exactly one statement in the file",
 "R003": "Destructive change (drop/truncate): not reversible by the pipeline",
 "R004": "ALTER COLUMN TYPE usually rewrites the table under ACCESS EXCLUSIVE",
 "R005": "ADD COLUMN forces a full table rewrite (volatile default / serial / stored generated / identity)",
 "R006": "SET NOT NULL scans the whole table under ACCESS EXCLUSIVE",
 "R007": "FOREIGN KEY / CHECK added without NOT VALID validates under a blocking lock",
 "R008": "ADD PRIMARY KEY / UNIQUE builds an index under ACCESS EXCLUSIVE",
 "R009": "RENAME breaks the previous app version still running during rollout",
 "R010": "Migrations must not override lock_timeout/statement_timeout; the pipeline owns them",
 "R011": "DROP INDEX without CONCURRENTLY takes ACCESS EXCLUSIVE",
 "R012": "UPDATE/DELETE without WHERE in a migration: bulk DML belongs in a batched backfill job",
 "R013": "No .down.sql and no '-- irreversible: <reason>' annotation",
 "R014": "Table-locking maintenance command (VACUUM FULL / CLUSTER / REINDEX / LOCK TABLE / SET TABLESPACE)",
 "R015": "ADD COLUMN NOT NULL without DEFAULT fails on non-empty tables and breaks old writers",
 "R017": "CREATE EXTENSION needs rds_superuser: human review",
 "R018": "Privilege / role / system changes are never self-service",
}
VOLATILE = r"random\s*\(|gen_random_uuid\s*\(|uuid_generate_v\w*\s*\(|clock_timestamp\s*\(|nextval\s*\(|timeofday\s*\(|txid_current\s*\("

@dataclass
class Finding:
    file: str; line: int; rule: str; message: str; waived: bool = False; reason: str = ""

def split_statements(sql):
    """Return [(start_line, masked_lowercase_statement)]; strings/comments/$$ bodies are masked."""
    out, buf, i, n, line, start = [], [], 0, len(sql), 1, None
    def flush():
        nonlocal buf, start
        s = re.sub(r"\s+", " ", "".join(buf)).strip().lower()
        if s: out.append((start or 1, s))
        buf, start = [], None
    while i < n:
        c = sql[i]
        if sql.startswith("--", i):
            j = sql.find("\n", i); i = n if j < 0 else j; continue
        if sql.startswith("/*", i):
            j = sql.find("*/", i + 2); j = n if j < 0 else j + 2
            line += sql.count("\n", i, j); i = j; buf.append(" "); continue
        if c in "'\"":
            j = i + 1
            while j < n:
                if sql[j] == c:
                    if j + 1 < n and sql[j + 1] == c: j += 2; continue
                    break
                j += 1
            lit = sql[i:j + 1]; line += lit.count("\n")
            if start is None: start = line
            buf.append("''" if c == "'" else lit.replace('"', "")); i = j + 1; continue
        m = re.match(r"\$[A-Za-z_]*\$", sql[i:]) if c == "$" else None
        if m:
            tag = m.group(0); j = sql.find(tag, i + len(tag)); j = n if j < 0 else j + len(tag)
            line += sql.count("\n", i, j)
            if start is None: start = line
            buf.append("$$"); i = j; continue
        if c == ";": flush(); i += 1; continue
        if c == "\n": line += 1
        if start is None and not c.isspace(): start = line
        buf.append(c); i += 1
    flush(); return out

def top_level_commas(s):
    parts, depth, cur = [], 0, []
    for ch in s:
        depth += ch == "("; depth -= ch == ")"
        if ch == "," and depth == 0: parts.append("".join(cur).strip()); cur = []
        else: cur.append(ch)
    parts.append("".join(cur).strip()); return parts

def norm_table(t): return t.replace('"', "").replace("public.", "").strip("() ")

def lint_text(path, text, has_down):
    f, findings = os.path.basename(path), []
    stmts = split_statements(text)
    no_tx = bool(re.search(r"^--\s*migrate:no-transaction", text, re.M))
    irreversible = re.search(r"^--\s*irreversible:\s*\S+", text, re.M)
    waivers = {m.group(1): m.group(2) for m in re.finditer(r'^--\s*lint:allow\s+(R\d{3})\s+reason="([^"]{5,})"', text, re.M)}
    created = {norm_table(m.group(1)) for _, s in stmts for m in [re.match(r"create (?:unlogged )?table (?:if not exists )?([\w.]+)", s)] if m}
    def add(line, rule, extra=""):
        findings.append(Finding(f, line, rule, RULES[rule] + (f" ({extra})" if extra else ""),
                                rule in waivers, waivers.get(rule, "")))
    if not has_down and not irreversible: add(1, "R013")
    if any("concurrently" in s for _, s in stmts):
        if not no_tx: add(1, "R002", "missing -- migrate:no-transaction")
    if no_tx and len(stmts) != 1: add(1, "R002", f"{len(stmts)} statements; a mid-file failure would leave partial state")
    for ln, s in stmts:
        if re.match(r"(set|reset)\s+(session\s+|local\s+)?(lock_timeout|statement_timeout)", s) or re.search(r"set_config\s*\(\s*''", s) and "timeout" in s:
            add(ln, "R010")
        if re.match(r"(create|alter|drop) (role|user)|grant |revoke |alter system|alter default privileges|alter owner", s): add(ln, "R018")
        if s.startswith("create extension"): add(ln, "R017")
        if re.match(r"create (unique )?index", s):
            m = re.search(r"\bon (?:only )?([\w.]+)", s)
            if not (m and norm_table(m.group(1)) in created) and not re.match(r"create (unique )?index concurrently", s): add(ln, "R001")
        if re.match(r"drop index", s) and "concurrently" not in s: add(ln, "R011")
        if re.match(r"drop (table|schema|database|type|view|materialized view|function|trigger|sequence|extension|column)|truncate", s): add(ln, "R003", s.split(" ")[0] + " " + s.split(" ")[1])
        if re.match(r"(update|delete from) ", s) and " where " not in s: add(ln, "R012")
        if re.match(r"(vacuum full|vacuum \(.*full|cluster|reindex|lock table)", s) and "concurrently" not in s: add(ln, "R014")
        m = re.match(r"alter table (?:if exists )?(?:only )?([\w.]+) (.*)$", s)
        if not m: continue
        tbl, rest = norm_table(m.group(1)), m.group(2)
        if tbl in created: continue
        if re.search(r"set tablespace", rest): add(ln, "R014", "SET TABLESPACE")
        for a in top_level_commas(rest):
            if re.match(r"rename ", a): add(ln, "R009")
            elif re.match(r"drop (column|constraint)", a) and a.startswith("drop column"): add(ln, "R003", "drop column")
            elif re.match(r"alter (column )?\S+ (set data )?type", a): add(ln, "R004")
            elif re.match(r"alter (column )?\S+ set not null", a): add(ln, "R006")
            elif re.match(r"add (constraint \S+ )?(foreign key|check)", a) and "not valid" not in a: add(ln, "R007")
            elif re.match(r"add (constraint \S+ )?(primary key|unique)", a) and "using index" not in a: add(ln, "R008")
            elif re.match(r"add (column )?(if not exists )?\S+ ", a) and not re.match(r"add (constraint|primary|foreign|unique|check|exclude)", a):
                if re.search(r"\bserial\b|\bbigserial\b|\bsmallserial\b|generated (always|by default) as identity|generated always as .* stored", a) \
                   or re.search(r"default[^,]*(" + VOLATILE + ")", a): add(ln, "R005")
                if "not null" in a and "default" not in a and not re.search(r"serial|generated", a): add(ln, "R015")
                if re.search(r"\breferences\b", a) and "not valid" not in a: add(ln, "R007", "inline REFERENCES")
                if re.search(r"\bunique\b|primary key", a): add(ln, "R008", "inline UNIQUE/PK")
    return findings

def collect(paths):
    for p in paths:
        if os.path.isdir(p):
            for fn in sorted(os.listdir(p)):
                if fn.endswith(".sql") and not fn.endswith(".down.sql"): yield os.path.join(p, fn)
        elif p.endswith(".sql") and not p.endswith(".down.sql"): yield p

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+"); ap.add_argument("--json", action="store_true")
    ap.add_argument("--github", action="store_true", help="emit GitHub annotations")
    a = ap.parse_args(argv)
    allf = []
    for p in collect(a.paths):
        down = p[:-4] + ".down.sql"
        allf += lint_text(p, open(p).read(), os.path.exists(down))
    blocking = [x for x in allf if not x.waived]; waived = [x for x in allf if x.waived]
    needs_approval = bool(waived)
    if a.json: print(json.dumps({"blocking": [asdict(x) for x in blocking], "waived": [asdict(x) for x in waived], "needs_approval": needs_approval}, indent=2))
    else:
        for x in allf:
            tag = "WAIVED" if x.waived else "ERROR"
            print(f"{tag} {x.file}:{x.line} {x.rule} {x.message}" + (f" | reason: {x.reason}" if x.waived else ""))
            if a.github: print(f"::{'warning' if x.waived else 'error'} file={x.file},line={x.line}::{x.rule} {x.message}")
        print(f"\n{len(blocking)} blocking, {len(waived)} waived, needs_approval={str(needs_approval).lower()}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as o: o.write(f"needs_approval={str(needs_approval).lower()}\n")
    return 1 if blocking else 0

if __name__ == "__main__": sys.exit(main())
