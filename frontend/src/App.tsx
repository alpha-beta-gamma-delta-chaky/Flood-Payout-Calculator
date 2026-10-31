import { useEffect, useState } from "react";
import { navigate, routeFromHash, type Route } from "./nav";
import { emptyAnswers, type Answers, type EstimateRequest, type EstimateResponse } from "./types";
import { EstimateForm } from "./views/EstimateForm";
import { Home } from "./views/Home";
import { HowItWorks } from "./views/HowItWorks";
import { Result } from "./views/Result";

interface Estimate {
  request: EstimateRequest;
  response: EstimateResponse;
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => routeFromHash(window.location.hash));
  const [answers, setAnswers] = useState<Answers>(emptyAnswers);
  const [estimate, setEstimate] = useState<Estimate | null>(null);

  useEffect(() => {
    const onHash = () => {
      setRoute(routeFromHash(window.location.hash));
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  // A result needs an estimate: opening #/result directly (or after a reload) goes to the form.
  const view: Route = route === "result" && !estimate ? "form" : route;

  if (view === "form")
    return (
      <EstimateForm
        answers={answers}
        onAnswers={setAnswers}
        onDone={(request, response) => {
          setEstimate({ request, response });
          navigate("result");
        }}
      />
    );

  if (view === "result" && estimate)
    return (
      <Result
        request={estimate.request}
        response={estimate.response}
        onChange={() => navigate("form")}
        onStartOver={() => {
          setAnswers(emptyAnswers);
          setEstimate(null);
          navigate("home");
        }}
      />
    );

  if (view === "how") return <HowItWorks />;
  return <Home />;
}
