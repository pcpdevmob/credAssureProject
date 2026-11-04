import type { paths } from "@credassure/api-client";

export function App() {
  const routeCount = Object.keys({} as paths).length;
  return (
    <main>
      <h1>CredAssure</h1>
      <p>Working-capital proposal review. Screens arrive in the UI lane (U0–U6).</p>
      <p>Generated API client loaded ({routeCount} routes in this bundle).</p>
    </main>
  );
}
