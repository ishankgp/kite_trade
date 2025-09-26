import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, RefreshCw } from "lucide-react";

import { useSummary, useTechnicals } from "../hooks/useAnalytics";
import { api } from "../lib/api";

type Instrument = {
  instrument_token: number;
  tradingsymbol: string | null;
  name: string | null;
  segment: string | null;
  exchange: string | null;
  lot_size: number | null;
  expiry: string | null;
  last_refreshed: string | null;
};

type ApiResponse = {
  items: Instrument[];
  total: number;
};

const fetchInstruments = async (search: string): Promise<ApiResponse> => {
  const params = new URLSearchParams();
  params.set("limit", "200");
  if (search) {
    params.set("search", search);
  }

  const { data } = await api.get<ApiResponse>(`/instruments`, { params });
  return data;
};

function InstrumentsPage() {
  const [search, setSearch] = useState("");
  const [selectedToken, setSelectedToken] = useState<number | null>(null);

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["instruments", search],
    queryFn: () => fetchInstruments(search),
  });

  const instruments = useMemo(() => data?.items ?? [], [data]);

  const summaryQuery = useSummary(selectedToken, "day");
  const technicalsQuery = useTechnicals(selectedToken, "day");

  return (
    <div className="space-y-8">
      <section className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold text-slate-900">Market Instruments</h2>
          <p className="text-sm text-slate-500">
            Browse tradable instruments stored in the local database.
          </p>
        </div>
        <button
          type="button"
          onClick={() => refetch()}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-slate-300 hover:bg-slate-50"
        >
          <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </section>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="w-full sm:max-w-xs">
            <label htmlFor="search" className="block text-sm font-medium text-slate-600">
              Search symbols
            </label>
            <input
              id="search"
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="e.g. NIFTY, BANKNIFTY"
              className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-800 shadow-sm transition focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-100"
            />
          </div>
          <div className="text-sm text-slate-500">
            Total instruments: <span className="font-semibold text-slate-700">{data?.total ?? 0}</span>
          </div>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-3">
          <div className="overflow-hidden rounded-xl border border-slate-200 lg:col-span-2">
          <table className="min-w-full divide-y divide-slate-200 bg-white">
            <thead className="bg-slate-100">
              <tr className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                <th className="px-4 py-3 text-left">Symbol</th>
                <th className="px-4 py-3 text-left">Name</th>
                <th className="px-4 py-3 text-left">Segment</th>
                <th className="px-4 py-3 text-left">Exchange</th>
                <th className="px-4 py-3 text-right">Lot Size</th>
                <th className="px-4 py-3 text-left">Last Refreshed</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm text-slate-700">
              {instruments.map((instrument) => {
                const isSelected = selectedToken === instrument.instrument_token;
                return (
                  <tr
                    key={instrument.instrument_token}
                    className={`cursor-pointer transition hover:bg-blue-50 ${
                      isSelected ? "bg-blue-50" : ""
                    }`}
                    onClick={() => setSelectedToken(instrument.instrument_token)}
                  >
                    <td className="px-4 py-3 font-medium text-slate-900">
                    {instrument.tradingsymbol ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{instrument.name ?? "—"}</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700">
                      {instrument.segment ?? "—"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-500">{instrument.exchange ?? "—"}</td>
                  <td className="px-4 py-3 text-right">
                    {instrument.lot_size !== null ? instrument.lot_size : "—"}
                  </td>
                  <td className="px-4 py-3 text-slate-500">
                    {instrument.last_refreshed
                      ? new Date(instrument.last_refreshed).toLocaleString()
                      : "—"}
                  </td>
                  </tr>
                );
              })}
              {!isLoading && instruments.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-sm text-slate-500">
                    No instruments matched your filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          {isLoading && (
            <div className="flex items-center justify-center gap-2 py-10 text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading instruments…
            </div>
          )}
        </div>
          <aside className="space-y-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-800">Summary</h3>
              {summaryQuery.isLoading ? (
                <div className="flex items-center gap-2 py-6 text-sm text-slate-500">
                  <Loader2 className="h-4 w-4 animate-spin" /> Fetching summary…
                </div>
              ) : summaryQuery.data ? (
                <dl className="mt-4 space-y-3 text-sm text-slate-600">
                  <div className="flex justify-between">
                    <dt>Last Close</dt>
                    <dd className="font-medium text-slate-900">
                      {summaryQuery.data.last_close?.toFixed(2) ?? "—"}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt>Change</dt>
                    <dd className="font-medium">
                      {summaryQuery.data.change !== null
                        ? `${summaryQuery.data.change.toFixed(2)} (${summaryQuery.data.change_pct?.toFixed(2)}%)`
                        : "—"}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt>20-bar avg volume</dt>
                    <dd className="font-medium">
                      {summaryQuery.data.average_volume !== null
                        ? summaryQuery.data.average_volume.toLocaleString()
                        : "—"}
                    </dd>
                  </div>
                  <div className="flex justify-between text-xs text-slate-400">
                    <dt>As of</dt>
                    <dd>
                      {summaryQuery.data.as_of
                        ? new Date(summaryQuery.data.as_of).toLocaleString()
                        : "—"}
                    </dd>
                  </div>
                </dl>
              ) : (
                <p className="py-4 text-sm text-slate-500">Select an instrument for analytics.</p>
              )}
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-800">Technicals</h3>
              {technicalsQuery.isLoading ? (
                <div className="flex items-center gap-2 py-6 text-sm text-slate-500">
                  <Loader2 className="h-4 w-4 animate-spin" /> Computing indicators…
                </div>
              ) : technicalsQuery.data ? (
                <div className="mt-4 space-y-3 text-sm text-slate-600">
                  <div className="grid grid-cols-2 gap-3">
                    {Object.entries(technicalsQuery.data.moving_averages).map(([label, value]) => (
                      <div key={label} className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                        <div className="text-xs uppercase tracking-wide text-slate-400">
                          {label.replace("_", " ")}
                        </div>
                        <div className="text-sm font-medium text-slate-900">
                          {value !== null ? value.toFixed(2) : "—"}
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs uppercase tracking-wide text-slate-400">RSI (14)</span>
                    <span className="text-sm font-medium text-slate-900">
                      {technicalsQuery.data.rsi !== null ? technicalsQuery.data.rsi.toFixed(2) : "—"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs uppercase tracking-wide text-slate-400">ATR (14)</span>
                    <span className="text-sm font-medium text-slate-900">
                      {technicalsQuery.data.atr !== null ? technicalsQuery.data.atr.toFixed(2) : "—"}
                    </span>
                  </div>
                </div>
              ) : (
                <p className="py-4 text-sm text-slate-500">Select an instrument for analytics.</p>
              )}
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}

export default InstrumentsPage;


