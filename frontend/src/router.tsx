import { createBrowserRouter } from "react-router-dom";
import AppLayout from "./routes/app-layout";
import InstrumentsPage from "./routes/instruments";
import TrainingPage from "./routes/training";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      {
        index: true,
        element: <InstrumentsPage />,
      },
      {
        path: "training",
        element: <TrainingPage />,
      },
    ],
  },
]);


