import { KeyboardEvent, useEffect, useRef, useState } from "react";
import { DashboardPage } from "./pages/DashboardPage";
import { RunJobPage } from "./pages/RunJobPage";
import { ResultsPage } from "./pages/ResultsPage";
import { ToastProvider } from "./components/Toast";
import { AppTab as Tab, nextTab, parseTabHash, tabToHash } from "./pages/tabState";

export function App() {
  const [tab, setTab] = useState<Tab>(() => (typeof window !== "undefined" ? parseTabHash(window.location.hash) : "dashboard"));
  const tabButtonRefs = useRef<Record<Tab, HTMLButtonElement | null>>({ dashboard: null, run: null, results: null });

  useEffect(() => {
    const onHashChange = () => {
      setTab(parseTabHash(window.location.hash));
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  useEffect(() => {
    const nextHash = tabToHash(tab);
    if (window.location.hash !== nextHash) {
      window.history.replaceState(null, "", nextHash);
    }
  }, [tab]);

  function moveTabFocus(currentTab: Tab, direction: 1 | -1) {
    const target = nextTab(currentTab, direction);
    setTab(target);
    tabButtonRefs.current[target]?.focus();
  }

  function onTabKeyDown(currentTab: Tab, e: KeyboardEvent<HTMLButtonElement>) {
    if (e.key === "ArrowRight") {
      e.preventDefault();
      moveTabFocus(currentTab, 1);
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      moveTabFocus(currentTab, -1);
    } else if (e.key === "Home") {
      e.preventDefault();
      setTab("dashboard");
      tabButtonRefs.current.dashboard?.focus();
    } else if (e.key === "End") {
      e.preventDefault();
      setTab("results");
      tabButtonRefs.current.results?.focus();
    }
  }

  return (
    <ToastProvider>
      <main className="container">
        <header className="header">
          <h1>Spline-LSTM GUI Prototype</h1>
          <p>React + Vite + TypeScript 기반 최소 동작 UI 골격</p>
        </header>

        <nav className="tabs" role="tablist" aria-label="페이지 탭">
          <button
            id="tab-dashboard"
            ref={(node) => { tabButtonRefs.current.dashboard = node; }}
            role="tab"
            aria-selected={tab === "dashboard"}
            aria-controls="panel-dashboard"
            className={tab === "dashboard" ? "active" : ""}
            onClick={() => setTab("dashboard")}
            onKeyDown={(e) => onTabKeyDown("dashboard", e)}
          >
            Dashboard
          </button>
          <button
            id="tab-run"
            ref={(node) => { tabButtonRefs.current.run = node; }}
            role="tab"
            aria-selected={tab === "run"}
            aria-controls="panel-run"
            className={tab === "run" ? "active" : ""}
            onClick={() => setTab("run")}
            onKeyDown={(e) => onTabKeyDown("run", e)}
          >
            Run Job
          </button>
          <button
            id="tab-results"
            ref={(node) => { tabButtonRefs.current.results = node; }}
            role="tab"
            aria-selected={tab === "results"}
            aria-controls="panel-results"
            className={tab === "results" ? "active" : ""}
            onClick={() => setTab("results")}
            onKeyDown={(e) => onTabKeyDown("results", e)}
          >
            Results
          </button>
        </nav>

        <section id="panel-dashboard" role="tabpanel" aria-labelledby="tab-dashboard" hidden={tab !== "dashboard"} tabIndex={0}>
          {tab === "dashboard" && <DashboardPage />}
        </section>
        <section id="panel-run" role="tabpanel" aria-labelledby="tab-run" hidden={tab !== "run"} tabIndex={0}>
          {tab === "run" && <RunJobPage />}
        </section>
        <section id="panel-results" role="tabpanel" aria-labelledby="tab-results" hidden={tab !== "results"} tabIndex={0}>
          {tab === "results" && <ResultsPage />}
        </section>
      </main>
    </ToastProvider>
  );
}
