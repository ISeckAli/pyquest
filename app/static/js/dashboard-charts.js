/*
  Dashboard progress charts (spec FR14), drawn with Chart.js from the
  analytics data the page provides. Each chart also has a text summary in
  the page, so nothing is shown only as a picture.
*/
(function () {
  "use strict";

  const dataElement = document.getElementById("analytics-data");
  if (!dataElement || !window.Chart) {
    return;
  }

  const data = JSON.parse(dataElement.textContent);
  const Chart = window.Chart;

  // Match the dark theme: light text, faint grid lines.
  Chart.defaults.color = "#e8e8f0";
  Chart.defaults.borderColor = "rgba(255, 255, 255, 0.08)";
  Chart.defaults.font.family = "inherit";

  function draw(canvasId, config) {
    const canvas = document.getElementById(canvasId);
    if (canvas) {
      new Chart(canvas, config);
    }
  }

  draw("accuracy-chart", {
    type: "line",
    data: {
      labels: data.accuracy.labels,
      datasets: [
        {
          label: "Pass rate (%)",
          data: data.accuracy.pass_rate,
          borderColor: "#00d4ff",
          backgroundColor: "rgba(0, 212, 255, 0.2)",
          // Weeks without attempts have no value; the line skips them
          // instead of dropping to a misleading 0%.
          spanGaps: true,
          tension: 0.3,
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      scales: { y: { min: 0, max: 100 } },
    },
  });

  draw("errors-chart", {
    type: "bar",
    data: {
      labels: data.errors.map((error) => error.name),
      datasets: [
        {
          label: "Times seen",
          data: data.errors.map((error) => error.count),
          backgroundColor: "#ff3d81",
        },
      ],
    },
    options: {
      indexAxis: "y",
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
    },
  });

  draw("topics-chart", {
    type: "bar",
    data: {
      labels: data.topics.map((topic) => topic.name),
      datasets: [
        {
          label: "Solved",
          data: data.topics.map((topic) => topic.solved),
          backgroundColor: "#8b5cf6",
        },
        {
          label: "Available",
          data: data.topics.map((topic) => topic.total),
          backgroundColor: "rgba(255, 255, 255, 0.15)",
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
    },
  });
})();