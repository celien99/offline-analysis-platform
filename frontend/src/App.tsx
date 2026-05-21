import AppRouter from "./app/router";
import AppLayout from "./app/layout";

export default function App() {
  return (
    <AppLayout>
      <AppRouter />
    </AppLayout>
  );
}
