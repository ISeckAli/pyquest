/*
  Runs learner code with Pyodide (Python compiled to WebAssembly) inside a
  Web Worker: a background thread separate from the page (spec FR05,
  decision DR-03).

  Running in a worker keeps the page responsive while code runs, and means
  code that never finishes (such as an infinite loop) can be stopped: the
  page terminates the whole worker when the time limit passes and starts a
  new one. The server never runs learner code.

  Messages:
    to the page   {type: "ready"} once Python has loaded
                  {type: "load-error", message} if it could not load
                  {type: "results", results, elapsedMs} after a run
    from the page {code, tests: [{id, input}], outputLimit}
*/
"use strict";

// Pinned so every learner runs exactly the same Python.
const PYODIDE_VERSION = "0.27.2";
const PYODIDE_URL = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

importScripts(`${PYODIDE_URL}pyodide.js`);

// Python helper loaded once. For each test it feeds the test's input to
// input(), captures everything printed, and reports any error with the
// line number in the learner's code.
const RUNNER = `
import io
import sys
import traceback


class OutputLimitExceeded(Exception):
    pass


class LimitedOutput(io.StringIO):
    """Collects printed text, stopping the program if it prints too much."""

    def __init__(self, limit):
        super().__init__()
        self.limit = limit

    def write(self, text):
        if self.tell() + len(text) > self.limit:
            raise OutputLimitExceeded("the program printed more than the output limit")
        return super().write(text)


def describe_error(exc):
    """The error's last line, such as "NameError: name 'x' is not defined",
    with the line number in the learner's code when it is known."""
    lines = "".join(traceback.format_exception_only(type(exc), exc)).strip().splitlines()
    message = lines[-1] if lines else type(exc).__name__
    line_number = exc.lineno if isinstance(exc, SyntaxError) else None
    if line_number is None:
        for frame in traceback.extract_tb(exc.__traceback__):
            if frame.filename == "solution.py":
                line_number = frame.lineno
    return f"{message} (line {line_number})" if line_number else message


def run_solution(code, stdin_text, output_limit):
    # Pasted code can carry Windows (\\r\\n) or old Mac (\\r) line endings,
    # which make Python count lines differently from the editor. Converting
    # them to plain \\n keeps reported line numbers matching what the
    # learner sees.
    code = code.replace("\\r\\n", "\\n").replace("\\r", "\\n")

    output = LimitedOutput(output_limit)
    saved_stdin, saved_stdout = sys.stdin, sys.stdout
    sys.stdin, sys.stdout = io.StringIO(stdin_text), output
    error = None
    try:
        # A fresh set of globals for every run, so one test cannot leave
        # variables behind that change the next test's result.
        exec(compile(code, "solution.py", "exec"), {"__name__": "__main__"})
    except SystemExit:
        pass
    except BaseException as exc:
        error = describe_error(exc)
    finally:
        sys.stdin, sys.stdout = saved_stdin, saved_stdout
    return output.getvalue(), error
`;

let runSolution = null;

const ready = (async () => {
  const pyodide = await loadPyodide({ indexURL: PYODIDE_URL });
  pyodide.runPython(RUNNER);
  runSolution = pyodide.globals.get("run_solution");
  self.postMessage({ type: "ready" });
})().catch((error) => {
  self.postMessage({ type: "load-error", message: String(error) });
});

self.onmessage = async (event) => {
  await ready;
  if (runSolution === null) {
    return;
  }

  const { code, tests, outputLimit } = event.data;
  const started = performance.now();

  const results = tests.map((test) => {
    const outcome = runSolution(code, test.input, outputLimit);
    const [output, error] = outcome.toJs();
    // Frees the memory Pyodide holds for the returned Python value.
    outcome.destroy();
    return { test_id: test.id, output, error: error ?? null };
  });

  self.postMessage({
    type: "results",
    results,
    elapsedMs: Math.round(performance.now() - started),
  });
};