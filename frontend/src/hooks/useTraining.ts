import { useMutation } from "@tanstack/react-query";
import { api } from "../lib/api";

export type TrainingModelResult = {
  model_name: string;
  metrics_overall: Record<string, number>;
  walk_forward: Array<{
    fold: number;
    train_start: string;
    train_end: string;
    test_start: string;
    test_end: string;
    rmse: number;
    mae: number;
    mape: number | null;
  }>;
  artifact_path: string | null;
  training_time_seconds: number;
};

export type TrainingRunResponse = {
  instrument_token: number;
  interval: string;
  forecast_horizon: number;
  models: TrainingModelResult[];
};

export type TrainingRequest = {
  instrument_token: number;
  interval: string;
  models: string[];
  forecast_horizon: number;
  lookback_window: number;
  walkforward_train_bars: number;
  walkforward_test_bars: number;
  step_size?: number | null;
};

export const useRunTraining = () =>
  useMutation({
    mutationFn: async (payload: TrainingRequest) => {
      const { data } = await api.post<TrainingRunResponse>("/training/run", payload);
      return data;
    },
  });


