/*
  AI Coach chat, code review, and ratings on the challenge page (spec
  PR-C3, PR-C4, PR-C6). Hints and failure explanations live in
  challenge.js; this script adds the conversational features alongside it.

  Everything added to the page uses textContent, never HTML, so Coach
  replies are always shown as plain text and can never run as code.
*/
(function () {
  "use strict";

  const configElement = document.getElementById("challenge-data");
  if (!configElement) {
    return;
  }

  const config = JSON.parse(configElement.textContent);
  const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute("content");

  const chatLog = document.getElementById("chat-log");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const chatSend = document.getElementById("chat-send");
  const chatStatus = document.getElementById("chat-status");
  const reviewButton = document.getElementById("review-button");
  const reviewOutput = document.getElementById("review-output");

  // -------------------------------------------------------------------------
  // Helpers
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

  function jsonHeaders() {
    return {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-CSRFToken": csrfToken,
    };
  }

  async function errorMessage(response) {
    try {
      const body = await response.json();
      return body.error || `Request failed (${response.status}).`;
    } catch {
      return `Request failed (${response.status}).`;
    }
  }

  // The code currently in the editor, read from Monaco's shared model so
  // the Coach always sees what the learner is working on.
  function currentCode() {
    const models = window.monaco ? window.monaco.editor.getModels() : [];
    return models.length > 0 ? models[0].getValue() : config.initialCode;
  }

  function sourceLabel(message, fallbackLabel) {
    return message.source === "ai" ? "AI Coach · AI-generated" : fallbackLabel;
  }

  // -------------------------------------------------------------------------
  // Ratings (PR-C6)
  // -------------------------------------------------------------------------

  function ratingControls(message) {
    const wrapper = element("div", "coach-rating");
    wrapper.append(element("span", "coach-rating-label", "Helpful?"));

    const buttons = {};
    for (const [rating, symbol, label] of [
      ["up", "👍", "Helpful"],
      ["down", "👎", "Not helpful"],
    ]) {
      const button = element("button", "rating-button", symbol);
      button.type = "button";
      button.setAttribute("aria-label", label);
      // aria-pressed tells screen readers which rating is currently chosen.
      button.setAttribute("aria-pressed", String(message.rating === rating));
      button.addEventListener("click", () => rate(message.id, rating, buttons));
      buttons[rating] = button;
      wrapper.append(button);
    }
    return wrapper;
  }

  async function rate(messageId, rating, buttons) {
    try {
      const response = await fetch(config.ratingUrlTemplate.replace("{id}", messageId), {
        method: "POST",
        credentials: "same-origin",
        headers: jsonHeaders(),
        body: JSON.stringify({ rating }),
      });
      if (response.ok) {
        for (const [value, button] of Object.entries(buttons)) {
          button.setAttribute("aria-pressed", String(value === rating));
        }
      }
    } catch {
      // A failed rating is not worth interrupting the learner for.
    }
  }

  function coachCard(label, message) {
    const card = element("div", "coach-card");
    card.append(element("p", "coach-label", label), element("p", "coach-text", message.text));
    // Saved messages have an id and can be rated; an unsaved fallback cannot.
    if (message.id) {
      card.append(ratingControls(message));
    }
    return card;
  }

  // -------------------------------------------------------------------------
  // Ask the Coach (PR-C4)
  // -------------------------------------------------------------------------

  function showChatMessage(message) {
    if (message.sender === "learner") {
      const bubble = element("div", "chat-bubble");
      bubble.append(element("p", "coach-label", "You"), element("p", "coach-text", message.text));
      chatLog.append(bubble);
    } else {
      chatLog.append(coachCard(sourceLabel(message, "Coach unavailable"), message));
    }
  }

  async function sendMessage(event) {
    // The form only exists so Enter sends the message; the page stays put.
    event.preventDefault();
    const text = chatInput.value.trim();
    if (!text) {
      return;
    }

    chatSend.disabled = true;
    chatStatus.textContent = "The Coach is thinking…";

    try {
      const response = await fetch(config.chatUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: jsonHeaders(),
        body: JSON.stringify({ message: text, code: currentCode() }),
      });
      if (!response.ok) {
        chatStatus.textContent = await errorMessage(response);
        return;
      }
      const data = await response.json();
      showChatMessage(data.learner);
      showChatMessage(data.coach);
      chatInput.value = "";
      chatStatus.textContent = "";
    } catch {
      chatStatus.textContent = "The Coach could not be reached. Check your connection and try again.";
    } finally {
      chatSend.disabled = false;
    }
  }

  // -------------------------------------------------------------------------
  // Review my solution (PR-C3)
  // -------------------------------------------------------------------------

  function showReview(review) {
    reviewOutput.replaceChildren(coachCard(sourceLabel(review, "Review unavailable"), review));
    // One saved AI review per challenge; an unavailable one can be retried.
    if (review.source === "ai") {
      reviewButton.remove();
    }
  }

  async function requestReview() {
    reviewButton.disabled = true;
    reviewOutput.replaceChildren(element("p", "result-note", "The Coach is reading your solution…"));

    try {
      const response = await fetch(config.reviewUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: jsonHeaders(),
      });
      if (!response.ok) {
        reviewOutput.replaceChildren(element("p", "result-note", await errorMessage(response)));
        return;
      }
      showReview(await response.json());
    } catch {
      reviewOutput.replaceChildren(
        element("p", "form-alert", "The Coach could not be reached. Check your connection and try again."),
      );
    } finally {
      reviewButton.disabled = false;
    }
  }

  // -------------------------------------------------------------------------
  // Start
  // -------------------------------------------------------------------------

  chatForm.addEventListener("submit", sendMessage);
  reviewButton.addEventListener("click", requestReview);

  config.chat.forEach(showChatMessage);
  if (config.review) {
    showReview(config.review);
  }
})();