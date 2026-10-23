import { useLocation } from "react-router";

/** True on the landing page, where section links are in-page anchors. */
export const useIsHome = (): boolean => useLocation().pathname === "/";
