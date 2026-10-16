(function () {
  var script = document.currentScript;
  if (!script || !script.src) return;
  var origin = new URL(script.src).origin;
  var button = document.createElement("button");
  button.type = "button";
  button.textContent = "Chat with Bright";
  button.style.cssText = [
    "position:fixed",
    "right:16px",
    "bottom:16px",
    "z-index:99999",
    "background:#0e6b62",
    "color:#f7f3ea",
    "border:0",
    "border-radius:999px",
    "padding:12px 16px",
    "font:600 15px/1.2 Georgia,serif",
    "cursor:pointer",
    "box-shadow:0 8px 24px rgba(28,25,21,.18)",
  ].join(";");
  var frame = document.createElement("iframe");
  frame.title = "BrightSmile chat";
  frame.src = origin + "/widget";
  frame.style.cssText = [
    "position:fixed",
    "right:16px",
    "bottom:72px",
    "width:min(400px,calc(100vw - 24px))",
    "height:min(640px,calc(100vh - 96px))",
    "border:0",
    "border-radius:24px",
    "z-index:99998",
    "display:none",
    "background:#fffdf8",
    "box-shadow:0 16px 40px rgba(28,25,21,.2)",
  ].join(";");
  button.addEventListener("click", function () {
    var opening = frame.style.display === "none";
    frame.style.display = opening ? "block" : "none";
    button.textContent = opening ? "Close chat" : "Chat with Bright";
  });
  document.body.appendChild(frame);
  document.body.appendChild(button);
})();
