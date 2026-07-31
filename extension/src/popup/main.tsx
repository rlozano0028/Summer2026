import { createRoot } from "react-dom/client";

import { Popup } from "./Popup";

const container = document.getElementById("root");
if (!container) {
  throw new Error("Popup root element is missing from popup.html");
}
createRoot(container).render(<Popup />);
