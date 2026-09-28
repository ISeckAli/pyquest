/*
  Instructor tool: runs a challenge's reference solution against every test,
  hidden ones included, before publishing (spec FR12).

  A mistake in a hidden test's expected output would fail every learner who
  tries the challenge, so this lets the instructor confirm the tests and the
  solution agree. It uses the same in-browser Python as learners
  (python-worker.js), so a passing check means learners' correct solutions
  will pass too.

  Results are added with textContent only, never as HTML.
*/
(function () {
  "use strict";

  const RUN_LIMIT_MS = 10000; // Same time limit learners get (spec FR06).
  const LOAD_LIMIT_MS = 60000; // Python can take a while to download the first time.
  const OUTPUT_LIMIT = 65536;

  const configElement = document.getElementById("reference-check-data");
  if (!configElement) {
    return;
  }

  const config = JSON.parse(configElement.textContent);
  const button = document.getElementById("reference-check-button");
  const resultsElement = document.getElementById("reference-check-results");

  // Mirrors normalise_output() in app/services/grading.py.
  function normaliseOutput(text) {
    return text
      .replace(/\r\n?/g, "\n")
      .split("\n")
      .map((line) => line.replace(/\s+$/, ""))
      .join("\n")
      .replace(/\n+$/, "");
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined) {
      node.textContent = text;
    }
    return node;
  }

  function labelled(label, text) {
    const wrapper = element("div");
    wrapper.append(element("p", "result-label", label), element("pre", "code-block", text));
    return wrapper;
  }

  function showMessage(className, message) {
    resultsElement.replaceChildren(element("p", className, message));
  }

  // Starts a fresh Python worker, runs the code once it is ready, and
  // resolves with the results. The worker is always shut down afterwards.
  function runReference(code, tests) {
    return new Promise((resolve, reject) => {
      const worker = new Worker(config.workerUrl);
      let timer = setTimeout(() => {
        worker.terminate();
        reject(new Error("Python took too long to load. Check your internet connection and try again."));
      }, LOAD_LIMIT_MS);

      worker.onmessage = (event) => {
        const message = event.data;

        if (message.type === "ready") {
          clearTimeout(timer);
          timer = setTimeout(() => {
            worker.terminate();
            reject(new Error(`The reference solution did not finish within ${RUN_LIMIT_MS / 1000} seconds.`));
          }, RUN_LIMIT_MS);
          worker.postMessage({
            code,
            tests: tests.map((test) => ({ id: test.id, input: test.input })),
            outputLimit: OUTPUT_LIMIT,
          });
        } else if (message.type === "results") {
          clearTimeout(timer);
          worker.terminate();
          resolve(message.results);
        } else if (message.type === "load-error") {
          clearTimeout(timer);
          worker.terminate();
          reject(new Error("Python could not be loaded. Check your internet connection and try again."));
        }
      };
    });
  }

  function showResults(tests, results) {
    const resultsById = new Map(results.map((result) => [result.test_id, result]));
    let failures = 0;
    const items = [];

    tests.forEach((test, index) => {
      const result = resultsById.get(test.id);
      const passed =
        result.error === null &&
        normaliseOutput(result.output) === normaliseOutput(test.expected);
      if (!passed) {
        failures += 1;
      }

      const box = element("div", `result-item ${passed ? "is-pass" : "is-fail"}`);
      const kind = test.hidden ? "Hidden test" : "Visible test";
      box.append(element("h3", null, `${kind} ${index + 1}: ${passed ? "passed" : "failed"}`));

      // Instructors wrote the tests, so failed hidden tests show full details.
      if (!passed) {
        box.append(labelled("Input", test.input || "(no input)"));
        box.append(labelled("Expected output", test.expected));
        if (result.error) {
          box.append(labelled("Error", result.error));
        } else {
          box.append(labelled("Reference solution printed", result.output || "(no output)"));
        }
      }
      items.push(box);
    });

    const summary =
      failures === 0
        ? element("p", "result-summary is-pass", `The reference solution passes all ${tests.length} tests.`)
        : element(
            "p",
            "result-summary is-fail",
            `The reference solution fails ${failures} of ${tests.length} tests. ` +
              "Fix the solution or the expected outputs before publishing.",
          );

    resultsElement.replaceChildren(summary, ...items);
  }

  async function check() {
    button.disabled = true;
    showMessage("result-note", "Loading Python and running the reference solution…");

    try {
      const response = await fetch(config.checkUrl, {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        throw new Error(`The check could not start (${response.status}). Reload the page and try again.`);
      }

      const data = await response.json();
      if (!data.code.trim()) {
        showMessage("form-alert", "Add a reference solution in the Details section first.");
        return;
      }
      if (data.tests.length === 0) {
        showMessage("form-alert", "Add test cases first.");
        return;
      }

      const results = await runReference(data.code, data.tests);
      showResults(data.tests, results);
    } catch (error) {
      showMessage("form-alert", error.message);
    } finally {
      button.disabled = false;
    }
  }

  button.addEventListener("click", check);
})();