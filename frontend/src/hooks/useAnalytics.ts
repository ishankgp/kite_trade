import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";

type SummaryResponse = {
  instrument_token: number;
  interval: string;
  as_of: string;
  last_close: number | null;
  previous_close: number | null;
  change: number | null;
  change_pct: number | null;
  average_volume: number | null;
};

type TechnicalsResponse = {
  instrument_token: number;
  interval: string;
  as_of: string;
  moving_averages: Record<string, number | null>;
  rsi: number | null;
  atr: number | null;
};

export const useSummary = (instrumentToken: number | null, interval: string) =>
  useQuery({
    queryKey: ["analytics", "summary", instrumentToken, interval],
    queryFn: async () => {
      if (!instrumentToken) return null;
      const { data } = await api.get<SummaryResponse>("/analytics/summary", {
        params: { instrument_token: instrumentToken, interval },
      });
      return data;
    },
    enabled: Boolean(instrumentToken),
  });

export const useTechnicals = (instrumentToken: number | null, interval: string) =>
  useQuery({
    queryKey: ["analytics", "technicals", instrumentToken, interval],
    queryFn: async () => {
      if (!instrumentToken) return null;
      const { data } = await api.get<TechnicalsResponse>("/analytics/technicals", {
        params: { instrument_token: instrumentToken, interval },
      });
      return data;
    },
    enabled: Boolean(instrumentToken),
  });


