// Feedback while a turn is on its way (Jelle's phone play test, 2026-11-14: "The
// app should show immediately that I pressed the button or hit enter and that
// now we are waiting for the response"). The line sent appears in the story at
// once with a waiting note; the server's answer replaces it. The buttons and the
// input are disabled meanwhile (hx-disabled-elt on #controls).
(function () {
  function sentLine(elt) {
    if (elt.tagName === "FORM") {
      const input = elt.querySelector("input[name=line]");
      return input ? input.value.trim() : "";
    }
    try {
      return JSON.parse(elt.getAttribute("hx-vals")).line || "";
    } catch (e) {
      return "";
    }
  }

  document.addEventListener("htmx:beforeRequest", function (e) {
    const log = document.getElementById("log");
    if (!log || e.detail.target !== log) return;
    const line = sentLine(e.detail.elt);
    if (!line) return;
    const entry = document.createElement("div");
    entry.className = "entry pending";
    entry.id = "pending";
    const you = document.createElement("p");
    you.className = "you";
    you.textContent = line;
    const wait = document.createElement("p");
    wait.className = "dm waiting";
    wait.textContent = "The story continues…";
    entry.append(you, wait);
    log.append(entry);
    window.scrollTo(0, document.body.scrollHeight);
  });

  document.addEventListener("htmx:afterRequest", function (e) {
    const pending = document.getElementById("pending");
    if (!pending) return;
    if (e.detail.successful) {
      pending.remove();
      return;
    }
    pending.removeAttribute("id");
    const wait = pending.querySelector(".waiting");
    wait.className = "dm warn";
    wait.textContent = "No answer from the game. Nothing happened; try again.";
  });
})();
