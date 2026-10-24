import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router";

import { Home } from "./pages/Home";

gsap.registerPlugin(useGSAP, ScrollTrigger);

// Loaded on demand, so the landing page bundle doesn't carry the guide.
const Assembly = lazy(() => import("./pages/Assembly").then((m) => ({ default: m.Assembly })));
const Simulation = lazy(() => import("./pages/Simulation").then((m) => ({ default: m.Simulation })));

export function App() {
  return (
    <Routes>
      <Route index element={<Home />} />
      <Route
        path="assembly"
        element={
          <Suspense fallback={null}>
            <Assembly />
          </Suspense>
        }
      />
      <Route path="*" element={<Home />} />
      <Route
        path="simulation"
        element={
          <Suspense fallback={null}>
            <Simulation />
          </Suspense>
        }
      />
    </Routes>
  );
}
