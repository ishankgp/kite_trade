import { FormEvent, useRef, useState } from "react";
import { Loader2, Play, Wand2 } from "lucide-react";
import { TrainingRunResponse, TrainingModelResult } from "../hooks/useTraining";

const MODEL_OPTIONS = [
  { id: "random_forest", label: "Random Forest" },
  { id: "xgboost", label: "XGBoost" },
  { id: "prophet", label: "Prophet" },
];

type TrainingEvent =
  | { type: "start"; models: string[]; total_folds: number }
  | { type: "model_start"; model: string; total_folds: number }
  | { type: "model_skipped"; model: string; reason: string }
  | {
      type: "fold";
      model: string;
      data: {
        fold: number;
        total_folds: number;
        train_start: string;
        train_end: string;
        test_start: string;
        test_end: string;
        rmse: number;
        mae: number;
        mape: number | null;
      };
    }
  | { type: "model_complete"; model: string; metrics: Record<string, number> }
  | { type: "complete"; results: TrainingRunResponse }
  | { type: "error"; message: string };

function TrainingPage() {
  const [instrumentToken, setInstrumentToken] = useState("256265");
  const [interval, setInterval] = useState("minute");
  const [forecastHorizon, setForecastHorizon] = useState(5);
  const [lookbackWindow, setLookbackWindow] = useState(40);
  const [trainBars, setTrainBars] = useState(300);
  const [testBars, setTestBars] = useState(60);
  const [selectedModels, setSelectedModels] = useState<string[]>(["random_forest", "xgboost"]);

  const [isRunning, setIsRunning] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [progressTotal, setProgressTotal] = useState(0);
  const [progressCompleted, setProgressCompleted] = useState(0);
  const progressTotalRef = useRef(0);
  const [currentModel, setCurrentModel] = useState<string | null>(null);
  const [foldEvents, setFoldEvents] = useState<TrainingEvent[]>([]);
  const [results, setResults] = useState<TrainingRunResponse | null>(null);

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!instrumentToken) return;

    setIsRunning(true);
    setStatusMessage("Preparing training run...");
    setErrorMessage(null);
    setProgressCompleted(0);
    setProgressTotal(0);
    setCurrentModel(null);
    setFoldEvents([]);
    setResults(null);

    startStreamingRun({
      instrument_token: Number(instrumentToken),
      interval,
      models: selectedModels,
      forecast_horizon: forecastHorizon,
      lookback_window: lookbackWindow,
      walkforward_train_bars: trainBars,
      walkforward_test_bars: testBars,
      step_size: undefined,
    }).catch((error) => {
      console.error(error);
      setErrorMessage(error.message ?? "Training failed");
      setIsRunning(false);
      setStatusMessage(null);
    });
  };

  const startStreamingRun = async (payload: {
    instrument_token: number;
    interval: string;
    models: string[];
    forecast_horizon: number;
    lookback_window: number;
    walkforward_train_bars: number;
    walkforward_test_bars: number;
    step_size?: number | undefined;
  }) => {
    const response = await fetch("/api/training/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...payload, stream: true }),
    });

    if (!response.ok || !response.body) {
      throw new Error(`Training request failed (${response.status})`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    const processEvent = (event: TrainingEvent) => {
      switch (event.type) {
        case "start":
          setStatusMessage("Initializing models...");
    const total = event.total_folds * event.models.length;
    progressTotalRef.current = total;
    setProgressTotal(total);
    setProgressCompleted(0);
          break;
        case "model_start":
          setCurrentModel(event.model);
          setStatusMessage(`Running ${event.model.replace("_", " ")}...`);
          break;
        case "model_skipped":
          setFoldEvents((prev) => [...prev, event]);
          break;
        case "fold":
          setFoldEvents((prev) => [...prev, event]);
          setProgressCompleted((prev) => prev + 1);
          setStatusMessage(
            `Model ${event.model.replace("_", " ")} · fold ${event.data.fold}/${event.data.total_folds}`
          );
          break;
        case "model_complete":
          setFoldEvents((prev) => [...prev, event]);
          setStatusMessage(`${event.model.replace("_", " ")} complete`);
          break;
        case "complete":
          setStatusMessage("Training finished");
          setResults(event.results);
          setIsRunning(false);
          break;
        case "error":
          setErrorMessage(event.message);
          setIsRunning(false);
          setStatusMessage(null);
          break;
      }
    };

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const chunk = buffer.slice(0, boundary).trim();
        buffer = buffer.slice(boundary + 2);
        if (chunk.startsWith("data:")) {
          const payload = chunk.replace(/^data:\s*/, "");
          try {
            const parsed = JSON.parse(payload) as TrainingEvent;
            processEvent(parsed);
          } catch (error) {
            console.error("Failed to parse training event", error, payload);
          }
        }
        boundary = buffer.indexOf("\n\n");
      }
    }

    setIsRunning(false);
    setStatusMessage((prev) => (prev ? `${prev} (idle)` : null));
  };

  const cappedCompleted = progressTotal > 0 ? Math.min(progressCompleted, progressTotal) : progressCompleted;
  const progressPercent = progressTotal > 0 ? Math.min(100, Math.round((cappedCompleted / progressTotal) * 100)) : 0;

  const lastRun = results;

  return (
    <div className="space-y-8">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <form className="grid gap-4 md:grid-cols-2" onSubmit={onSubmit}>
          <div>
            <label className="text-sm font-medium text-slate-600">Instrument Token</label>
            <input
              value={instrumentToken}
              onChange={(event) => setInstrumentToken(event.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-100"
              required
            />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-600">Interval</label>
            <select
              value={interval}
              onChange={(event) => setInterval(event.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-100"
            >
              <option value="minute">minute</option>
              <option value="5minute">5minute</option>
              <option value="15minute">15minute</option>
              <option value="day">day</option>
            </select>
          </div>

          <div>
            <label className="text-sm font-medium text-slate-600">Forecast horizon (bars)</label>
            <input
              type="number"
              min={1}
              value={forecastHorizon}
              onChange={(event) => setForecastHorizon(Number(event.target.value))}
              className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-100"
            />
          </div>

          <div>
            <label className="text-sm font-medium text-slate-600">Lookback window</label>
            <input
              type="number"
              min={10}
              value={lookbackWindow}
              onChange={(event) => setLookbackWindow(Number(event.target.value))}
              className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-100"
            />
          </div>

          <div>
            <label className="text-sm font-medium text-slate-600">Walk-forward train bars</label>
            <input
              type="number"
              min={100}
              value={trainBars}
              onChange={(event) => setTrainBars(Number(event.target.value))}
              className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-100"
            />
          </div>

          <div>
            <label className="text-sm font-medium text-slate-600">Walk-forward test bars</label>
            <input
              type="number"
              min={20}
              value={testBars}
              onChange={(event) => setTestBars(Number(event.target.value))}
              className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-100"
            />
          </div>

          <div className="md:col-span-2">
            <span className="text-sm font-medium text-slate-600">Models</span>
            <div className="mt-2 flex flex-wrap gap-3">
              {MODEL_OPTIONS.map((option) => {
                const checked = selectedModels.includes(option.id);
                return (
                  <label
                    key={option.id}
                    className={`inline-flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition ${
                      checked
                        ? "border-blue-500 bg-blue-50 text-blue-700"
                        : "border-slate-200 bg-slate-50 text-slate-600"
                    }`}
                  >
                    <input
                      type="checkbox"
                      className="hidden"
                      checked={checked}
                      onChange={() => {
                        setSelectedModels((prev) =>
                          checked ? prev.filter((id) => id !== option.id) : [...prev, option.id]
                        );
                      }}
                    />
                    <Wand2 className="h-4 w-4" />
                    {option.label}
                  </label>
                );
              })}
            </div>
          </div>

          <div className="md:col-span-2 flex justify-end">
            <button
              type="submit"
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700"
              disabled={isRunning}
            >
              {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              Run training
            </button>
          </div>
        </form>
      </section>

      {(isRunning || statusMessage) && (
        <div className="rounded-lg border border-blue-100 bg-blue-50 p-4 text-sm text-blue-700">
          <div className="flex items-center justify-between">
            <span className="font-medium">{statusMessage ?? "Waiting for status..."}</span>
            <span>{progressPercent}%</span>
          </div>
          <div className="mt-3 h-2 rounded-full bg-blue-100">
            <div
              className="h-2 rounded-full bg-blue-600 transition-all"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      )}

      {errorMessage && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-600">
          Training failed: {errorMessage}
        </div>
      )}

      {foldEvents.length > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Live metrics</h3>
          <div className="mt-3 grid gap-2 text-xs text-slate-600">
            {foldEvents.map((event, index) => {
              if (event.type === "fold") {
                return (
                  <div
                    key={`${event.model}-fold-${event.data.fold}-${index}`}
                    className="rounded-lg border border-slate-200 bg-slate-50 p-2"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-800">
                        {event.model.replace("_", " ")} · Fold {event.data.fold}/{event.data.total_folds}
                      </span>
                      <span>
                        RMSE {event.data.rmse.toFixed(3)} · MAE {event.data.mae.toFixed(3)} · MAPE {event.data.mape?.toFixed(2) ?? "—"}
                      </span>
                    </div>
                  </div>
                );
              }
              if (event.type === "model_complete") {
                return (
                  <div key={`${event.model}-complete-${index}`} className="rounded-lg border border-blue-200 bg-blue-50 p-2">
                    <span className="font-semibold text-blue-700">{event.model.replace("_", " ")} complete</span>
                    <span className="ml-2 text-blue-600">
                      RMSE {event.metrics.rmse.toFixed(3)} · MAE {event.metrics.mae.toFixed(3)} · MAPE {Number.isFinite(event.metrics.mape) ? event.metrics.mape.toFixed(2) : "—"}
                    </span>
                  </div>
                );
              }
              if (event.type === "model_skipped") {
                return (
                  <div key={`${event.model}-skipped-${index}`} className="rounded-lg border border-amber-200 bg-amber-50 p-2">
                    <span className="font-semibold text-amber-700">{event.model.replace("_", " ")} skipped:</span>
                    <span className="ml-2 text-amber-600">{event.reason}</span>
                  </div>
                );
              }
              return null;
            })}
            {foldEvents.length === 0 && <p className="text-slate-500">Waiting for metrics...</p>}
          </div>
        </div>
      )}

      {lastRun && lastRun.models.length > 0 && (
        <section className="space-y-6">
          <h2 className="text-xl font-semibold text-slate-900">Results</h2>
          <div className="grid gap-4 lg:grid-cols-2">
            {lastRun.models.map((model) => (
              <div key={model.model_name} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-slate-800">
                    {model.model_name.replace("_", " ")}
                  </h3>
                  <span className="text-xs uppercase tracking-wide text-slate-400">
                    {model.training_time_seconds.toFixed(1)}s
                  </span>
                </div>
                <dl className="mt-4 grid grid-cols-3 gap-4 text-sm text-slate-600">
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-slate-400">RMSE</dt>
                    <dd className="text-base font-semibold text-slate-900">
                      {model.metrics_overall.rmse.toFixed(3)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-slate-400">MAE</dt>
                    <dd className="text-base font-semibold text-slate-900">
                      {model.metrics_overall.mae.toFixed(3)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-slate-400">MAPE</dt>
                    <dd className="text-base font-semibold text-slate-900">
                      {model.metrics_overall.mape ? model.metrics_overall.mape.toFixed(2) : "—"}
                    </dd>
                  </div>
                </dl>

                <div className="mt-4">
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                    Walk-forward metrics
                  </h4>
                  <div className="mt-2 grid gap-2 text-xs text-slate-600">
                    {model.walk_forward.map((fold) => (
                      <div
                        key={`${model.model_name}_fold_${fold.fold}`}
                        className="rounded-lg border border-slate-200 bg-slate-50 p-2"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-slate-800">Fold {fold.fold}</span>
                          <span>
                            RMSE {fold.rmse.toFixed(3)} · MAE {fold.mae.toFixed(3)} · MAPE {fold.mape?.toFixed(2) ?? "—"}
                          </span>
                        </div>
                        <div className="text-slate-400">
                          {new Date(fold.train_start).toLocaleDateString()} –
                          {" "}
                          {new Date(fold.test_end).toLocaleDateString()}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {model.artifact_path && (
                  <div className="mt-4 rounded-lg border border-blue-100 bg-blue-50 p-3 text-xs text-blue-600">
                    Model saved at: {model.artifact_path}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

export default TrainingPage;


