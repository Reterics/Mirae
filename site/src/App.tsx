import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router";

import { Home } from "./pages/Home";

gsap.registerPlugin(useGSAP, ScrollTrigger);

// Loaded on demand, so the landing page bundle doesn't carry the guide.
const Assembly = lazy(() => import("./pages/Assembly").then((m) => ({ default: m.Assembly })));

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
    </Routes>
  );
}
