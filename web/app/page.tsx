"use client";

import { useEffect, useMemo, useState } from "react";

type Evidence = { kind: string; passed: boolean; summary: string; duration_ms: number };
type Finding = { severity: string; category: string; message: string; path?: string };
type Event = { sequence: number; timestamp: string; state: string; type: string; message: string; data: Record<string, unknown> };
type Run = {
  id: string;
  task: string;
  state: string;
  outcome: string;
  updated_at: string;
  changed_files: string[];
  evidence: Evidence[];
  findings: Finding[];
  events?: Event[];
  usage: { attempts: number; loops: number; tool_calls: number; input_tokens: number; output_tokens: number };
  plan?: { summary: string; steps: string[] };
};

const states = ["DISCOVER", "PLAN", "IMPLEMENT", "TEST", "ANALYZE_FAILURE", "REPAIR", "REVIEW", "VERIFY", "COMPLETE"];
const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Dashboard() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [selected, setSelected] = useState<Run | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    const load = async () => {
      try {
        const response = await fetch(`${api}/api/runs`, { cache: "no-store" });
        if (!response.ok) throw new Error(`API returned ${response.status}`);
        const nextRuns = (await response.json()) as Run[];
        setRuns(nextRuns);
        setSelectedId((current) => current || nextRuns[0]?.id || "");
        setError("");
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "API unavailable");
      }
    };
    void load();
    const timer = window.setInterval(load, 5000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    const load = async () => {
      const response = await fetch(`${api}/api/runs/${selectedId}`, { cache: "no-store" });
      if (response.ok) setSelected((await response.json()) as Run);
    };
    void load();
    const timer = window.setInterval(load, 2500);
    return () => window.clearInterval(timer);
  }, [selectedId]);

  const contextEvents = useMemo(
    () => selected?.events?.filter((event) => event.type.startsWith("context.")) ?? [],
    [selected],
  );
  const toolEvents = useMemo(
    () => selected?.events?.filter((event) => event.type === "tool.completed") ?? [],
    [selected],
  );

  return (
    <main>
      <header>
        <div className="mark">AD</div>
        <div>
          <p className="eyebrow">AUTONOMOUSDEV / CONTROL PLANE</p>
          <h1>Harness observatory</h1>
        </div>
        <div className={`health ${error ? "bad" : ""}`}><span />{error || "API connected"}</div>
      </header>

      <section className="hero">
        <div>
          <p className="eyebrow">ENGINEERING SIGNAL, NOT AGENT THEATER</p>
          <h2>Every transition earns its evidence.</h2>
          <p>Inspect selected context, controlled actions, sandbox runs, repairs, review findings, and independent exit checks—without exposing hidden reasoning.</p>
        </div>
        <div className="heroMetric"><strong>{runs.length}</strong><span>persisted runs</span></div>
      </section>

      <div className="layout">
        <aside>
          <div className="sectionTitle"><span>RUN QUEUE</span><span>{runs.length}</span></div>
          {runs.length === 0 && <p className="empty">No runs yet. Start one with <code>adev run</code>.</p>}
          {runs.map((run) => (
            <button className={`run ${run.id === selectedId ? "active" : ""}`} key={run.id} onClick={() => setSelectedId(run.id)}>
              <div><span className={`dot ${run.outcome.toLowerCase()}`} />{run.id}</div>
              <strong>{run.task}</strong>
              <small>{run.state} · {new Date(run.updated_at).toLocaleString()}</small>
            </button>
          ))}
        </aside>

        <section className="workspace">
          {!selected && <div className="empty panel">Select a run to inspect its evidence.</div>}
          {selected && <>
            <div className="runHeader">
              <div><p className="eyebrow">RUN {selected.id}</p><h3>{selected.task}</h3></div>
              <span className={`outcome ${selected.outcome.toLowerCase()}`}>{selected.outcome}</span>
            </div>

            <div className="loop" aria-label="Harness state machine">
              {states.map((state, index) => <div key={state} className={`${state === selected.state ? "current" : ""} ${index < states.indexOf(selected.state) ? "done" : ""}`}><span>{String(index + 1).padStart(2, "0")}</span>{state}</div>)}
            </div>

            <div className="metrics">
              <Metric label="Attempts" value={selected.usage.attempts} />
              <Metric label="Repair loops" value={selected.usage.loops} />
              <Metric label="Tool calls" value={selected.usage.tool_calls} />
              <Metric label="Model tokens" value={selected.usage.input_tokens + selected.usage.output_tokens} />
            </div>

            <div className="grid">
              <Panel title="Plan" count={selected.plan?.steps.length ?? 0}>
                <p>{selected.plan?.summary ?? "Plan pending"}</p>
                <ol>{selected.plan?.steps.map((step) => <li key={step}>{step}</li>)}</ol>
              </Panel>
              <Panel title="Files modified" count={selected.changed_files.length}>
                <ul className="files">{selected.changed_files.map((path) => <li key={path}><code>{path}</code></li>)}</ul>
              </Panel>
              <Panel title="Verification evidence" count={selected.evidence.length}>
                {selected.evidence.map((item, index) => <div className="evidence" key={`${item.kind}-${index}`}><span className={item.passed ? "pass" : "fail"}>{item.passed ? "PASS" : "FAIL"}</span><div><strong>{item.kind}</strong><p>{item.summary}</p></div><small>{item.duration_ms}ms</small></div>)}
              </Panel>
              <Panel title="Review findings" count={selected.findings.length}>
                {selected.findings.length === 0 && <p className="empty">No findings recorded.</p>}
                {selected.findings.map((item, index) => <div className="finding" key={index}><span>{item.severity}</span><div><strong>{item.category}</strong><p>{item.message}</p>{item.path && <code>{item.path}</code>}</div></div>)}
              </Panel>
              <Panel title="Context selections" count={contextEvents.length}>
                {contextEvents.slice().reverse().map((event) => <EventRow event={event} key={event.sequence} />)}
              </Panel>
              <Panel title="Controlled tool calls" count={toolEvents.length}>
                {toolEvents.slice().reverse().map((event) => <EventRow event={event} key={event.sequence} />)}
              </Panel>
            </div>
          </>}
        </section>
      </div>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: number }) { return <div><strong>{value.toLocaleString()}</strong><span>{label}</span></div>; }
function Panel({ title, count, children }: { title: string; count: number; children: React.ReactNode }) { return <article className="panel"><div className="sectionTitle"><span>{title}</span><span>{count}</span></div><div className="panelBody">{children}</div></article>; }
function EventRow({ event }: { event: Event }) { return <details><summary><span>{event.state}</span>{event.message}</summary><pre>{JSON.stringify(event.data, null, 2)}</pre></details>; }
