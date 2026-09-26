/*
  Challenge workspace: the code editor, running Python in the browser,
  saving work, and submitting results for grading (spec FR05, FR06,
  decision DR-03).

  - Run examples: runs the learner's code on the visible tests only and
    compares the output here. Nothing is sent to the server; no XP.
  - Submit: runs every test (hidden ones included), sends the outputs to
    the server, and shows its verdict. The server holds the hidden expected
    outputs, decides pass or fail, and awards XP.
  - Autosave: the code is saved shortly after the learner stops typing, so
    leaving the page and coming back never loses work.

  All results are added to the page with textContent, never as HTML, so
  anything a program prints is displayed as plain text and can never be
  run as code in the page.
*/
(function () {
  "use strict";

  const TIME_LIMIT_MS = 10000; // Spec FR06 and SRS UC-02 exception 4e.
  const OUTPUT_LIMIT = 65536; // 64 KB of output per test.
  const MAX_REPORTED_MS = 60000; // Matches the server's accepted range.

  // Wait this long after the last keystroke before saving. Saving on every
  // keystroke would send a request per character typed.
  const SAVE_DELAY_MS = 1500;

  const configElement = document.getElementById("challenge-data");
  if (!configElement) {
    return;
  }

  const config = JSON.parse(configElement.textContent);
  const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute("content");

  const runButton = document.getElementById("run-button");
  const submitButton = document.getElementById("submit-button");
  const resetButton = document.getElementById("reset-button");
  const statusElement = document.getElementById("run-status");
  const resultsElement = document.getElementById("results");

  // Shows the autosave state beside the buttons. Created here rather than
  // in the template because only this script updates it.
  const saveStatusElement = document.createElement("span");
  saveStatusElement.className = "keyboard-tip";
  saveStatusElement.setAttribute("aria-live", "polite");
  resetButton.after(saveStatusElement);

  let editor = null;
  let tests = null;
  let worker = null;
  let workerReady = false;
  let pendingRun = null;
  let busy = false;
  let saveTimer = null;
  let lastSavedCode = config.initialCode;

  // -------------------------------------------------------------------------
  // Status and buttons
  // -------------------------------------------------------------------------

  function setStatus(message) {
    statusElement.textContent = message;
  }

  function setSaveStatus(message) {
    saveStatusElement.textContent = message;
  }

  function updateButtons() {
    const ready = editor !== null && tests !== null && workerReady && !busy;
    runButton.disabled = !ready;
    submitButton.disabled = !ready;
    resetButton.disabled = editor === null || busy;
  }

  function announceIfReady() {
    if (editor !== null && tests !== null && workerReady) {
      setStatus("Ready. Run the examples, or submit your solution.");
    }
  }

  // -------------------------------------------------------------------------
  // The Python worker
  // -------------------------------------------------------------------------

  function startWorker() {
    workerReady = false;
    worker = new Worker(config.workerUrl);
    worker.onmessage = handleWorkerMessage;
    worker.onerror = () => {
      setStatus("Python could not be started. Reload the page to try again.");
    };
  }

  function handleWorkerMessage(event) {
    const message = event.data;

    if (message.type === "ready") {
      workerReady = true;
      announceIfReady();
      updateButtons();
    } else if (message.type === "load-error") {
      setStatus("Python could not be loaded. Check your internet connection and reload the page.");
    } else if (message.type === "results" && pendingRun !== null) {
      clearTimeout(pendingRun.timer);
      const { resolve } = pendingRun;
      pendingRun = null;
      resolve({ results: message.results, elapsedMs: message.elapsedMs });
    }
  }

  function runInWorker(selectedTests) {
    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        // Code that never finishes cannot be interrupted from inside the
        // worker, so the whole worker is stopped and a fresh one started.
        pendingRun = null;
        worker.terminate();
        startWorker();
        resolve({
          elapsedMs: TIME_LIMIT_MS,
          results: selectedTests.map((test) => ({
            test_id: test.id,
            output: "",
            error: `TimeoutError: the time limit of ${TIME_LIMIT_MS / 1000} seconds was exceeded`,
          })),
        });
      }, TIME_LIMIT_MS);

      pendingRun = { resolve, timer };
      worker.postMessage({
        code: editor.getValue(),
        tests: selectedTests.map((test) => ({ id: test.id, input: test.input })),
        outputLimit: OUTPUT_LIMIT,
      });
    });
  }

  // -------------------------------------------------------------------------
  // Loading the editor and the tests
  // -------------------------------------------------------------------------

  function loadEditor() {
    const vsPath = `${config.monacoBase}/min/vs`;

    // Monaco starts helper workers from its own files, but browsers do not
    // let a page start a worker straight from another website's address.
    // This small same-origin wrapper (a data: address) loads Monaco's
    // worker script instead: the approach Monaco documents for CDN use.
    window.MonacoEnvironment = {
      getWorkerUrl() {
        const source =
          `self.MonacoEnvironment = { baseUrl: "${config.monacoBase}/min/" };` +
          `importScripts("${vsPath}/base/worker/workerMain.js");`;
        return `data:text/javascript;charset=utf-8,${encodeURIComponent(source)}`;
      },
    };

    window.require.config({ paths: { vs: vsPath } });
    window.require(
      ["vs/editor/editor.main"],
      () => {
        editor = window.monaco.editor.create(document.getElementById("editor"), {
          // The learner's saved work if there is any, otherwise the starter code.
          value: config.initialCode,
          language: "python",
          theme: "vs-dark",
          automaticLayout: true,
          minimap: { enabled: false },
          fontSize: 15,
          tabSize: 4,
          insertSpaces: true,
          scrollBeyondLastLine: false,
          ariaLabel: "Python code editor",
        });
        editor.onDidChangeModelContent(scheduleSave);
        announceIfReady();
        updateButtons();
      },
      () => {
        setStatus("The code editor could not be loaded. Check your internet connection and reload the page.");
      },
    );
  }

  async function loadTests() {
    const response = await fetch(config.testsUrl, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      throw new Error(await errorMessage(response));
    }
    tests = (await response.json()).tests;
    announceIfReady();
    updateButtons();
  }

  async function errorMessage(response) {
    try {
      const body = await response.json();
      return body.error || `Request failed (${response.status}).`;
    } catch {
      return `Request failed (${response.status}).`;
    }
  }

  // -------------------------------------------------------------------------
  // Autosave
  // -------------------------------------------------------------------------

  function saveRequest(code, keepalive) {
    return fetch(config.saveUrl, {
      method: "PUT",
      credentials: "same-origin",
      // keepalive lets the request finish even while the page is closing.
      keepalive,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-CSRFToken": csrfToken,
      },
      body: JSON.stringify({ code }),
    });
  }

  function scheduleSave() {
    clearTimeout(saveTimer);
    setSaveStatus("Unsaved changes");
    saveTimer = setTimeout(saveNow, SAVE_DELAY_MS);
  }

  async function saveNow() {
    clearTimeout(saveTimer);
    saveTimer = null;

    const code = editor.getValue();
    if (code === lastSavedCode) {
      setSaveStatus("All changes saved");
      return;
    }

    setSaveStatus("Saving…");
    try {
      const response = await saveRequest(code, false);
      if (!response.ok) {
        throw new Error(await errorMessage(response));
      }
      lastSavedCode = code;
      // The learner may have kept typing while the save was in flight.
      setSaveStatus(editor.getValue() === code ? "All changes saved" : "Unsaved changes");
    } catch {
      setSaveStatus("Could not save. Your code is still here; keep this tab open and try again.");
    }
  }

  // Sends any unsaved change as the learner leaves or closes the page.
  window.addEventListener("pagehide", () => {
    if (editor !== null && editor.getValue() !== lastSavedCode) {
      saveRequest(editor.getValue(), true);
    }
  });

  // -------------------------------------------------------------------------
  // Run and Submit
  // -------------------------------------------------------------------------

  // Mirrors normalise_output() in app/services/grading.py, so Run and
  // Submit judge output the same way.
  function normaliseOutput(text) {
    return text
      .replace(/\r\n?/g, "\n")
      .split("\n")
      .map((line) => line.replace(/\s+$/, ""))
      .join("\n")
      .replace(/\n+$/, "");
  }

  async function withBusy(message, task) {
    busy = true;
    updateButtons();
    setStatus(message);
    try {
      await task();
    } catch (error) {
      showError("Something went wrong. Check your internet connection and try again.");
      setStatus("Something went wrong.");
    } finally {
      busy = false;
      updateButtons();
    }
  }

  function runExamples() {
    const visible = tests.filter((test) => !test.hidden);

    return withBusy("Running the examples…", async () => {
      const run = await runInWorker(visible);
      const resultsById = new Map(run.results.map((result) => [result.test_id, result]));

      const items = visible.map((test, index) => {
        const result = resultsById.get(test.id);
        const passed =
          result.error === null &&
          normaliseOutput(result.output) === normaliseOutput(test.expected);
        return {
          number: index + 1,
          hidden: false,
          passed,
          input: test.input,
          expected: test.expected,
          actual: result.output,
          error: result.error,
        };
      });

      const passedCount = items.filter((item) => item.passed).length;
      showResults({
        heading: `Examples: ${passedCount} of ${items.length} passed.`,
        passed: passedCount === items.length,
        items,
        note: "Running the examples does not submit your solution or earn XP.",
      });
      setStatus("Examples finished.");
    });
  }

  function submitSolution() {
    return withBusy("Running all tests…", async () => {
      // Save first, so the working copy always matches what was submitted.
      await saveNow();

      const run = await runInWorker(tests);
      setStatus("Grading…");

      const response = await fetch(config.submitUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          code: editor.getValue(),
          results: run.results,
          execution_ms: Math.min(Math.round(run.elapsedMs), MAX_REPORTED_MS),
        }),
      });

      if (!response.ok) {
        showError(await errorMessage(response));
        setStatus("Your submission could not be graded.");
        return;
      }

      const feedback = await response.json();
      showResults({
        heading: feedback.passed
          ? `Solved! All ${feedback.total_count} tests passed.`
          : `${feedback.passed_count} of ${feedback.total_count} tests passed.`,
        passed: feedback.passed,
        items: feedback.tests,
        feedback,
      });
      setStatus(feedback.passed ? "Submission passed." : "Submission graded. Keep going!");
    });
  }

  function resetCode() {
    if (window.confirm("Replace your code with the starter code?")) {
      // Setting the value counts as a change, so the reset is autosaved too.
      editor.setValue(config.starterCode);
      resultsElement.replaceChildren();
    }
  }

  // -------------------------------------------------------------------------
  // Showing results (plain text only; see the note at the top)
  // -------------------------------------------------------------------------

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

  function resultItem(item) {
    const box = element("div", `result-item ${item.passed ? "is-pass" : "is-fail"}`);
    const kind = item.hidden ? "Hidden test" : "Test";
    box.append(element("h3", null, `${kind} ${item.number}: ${item.passed ? "passed" : "failed"}`));

    // Hidden tests report only passed or failed, so their answers stay secret.
    if (!item.hidden && !item.passed) {
      box.append(labelled("Input", item.input || "(no input)"));
      box.append(labelled("Expected output", item.expected));
      if (item.error) {
        box.append(labelled("Error", item.error));
      } else {
        box.append(labelled("Your output", item.actual || "(no output)"));
      }
    }
    return box;
  }

  function outcomeMessage(feedback) {
    if (!feedback.passed) {
      return element(
        "p",
        "result-note",
        "Hidden tests check cases beyond the examples. Think about edge cases, such as very short or unusual input.",
      );
    }
    if (feedback.xp_awarded > 0) {
      return element(
        "p",
        "xp-banner",
        `+${feedback.xp_awarded} XP! You now have ${feedback.total_xp} XP and are level ${feedback.level}.`,
      );
    }
    return element("p", "result-note", "Solved again. XP is awarded for the first solve only.");
  }

  function showResults({ heading, passed, items, note, feedback }) {
    resultsElement.replaceChildren(
      element("p", `result-summary ${passed ? "is-pass" : "is-fail"}`, heading),
    );
    if (feedback) {
      resultsElement.append(outcomeMessage(feedback));
    }
    for (const item of items) {
      resultsElement.append(resultItem(item));
    }
    if (note) {
      resultsElement.append(element("p", "result-note", note));
    }
  }

  function showError(message) {
    resultsElement.replaceChildren(element("p", "form-alert", message));
  }

  // -------------------------------------------------------------------------
  // Start
  // -------------------------------------------------------------------------

  runButton.addEventListener("click", runExamples);
  submitButton.addEventListener("click", submitSolution);
  resetButton.addEventListener("click", resetCode);

  startWorker();
  loadEditor();
  loadTests().catch((error) => setStatus(error.message));
})();