import AppRouter from "./app/router";
import AppLayout from "./app/layout";
import ScrollToTop from "./components/ui/ScrollToTop";

export default function App() {
  return (
    <>
      <ScrollToTop />
      <AppLayout>
        <AppRouter />
      </AppLayout>
    </>
  );
}
