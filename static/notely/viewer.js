(() => {
  const canvases = [...document.querySelectorAll(".lazy-page")];
  const images = new WeakMap();

  function draw(canvas) {
    const image = images.get(canvas);
    if (!image) return;
    const context = canvas.getContext("2d");
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
  }

  async function load(canvas) {
    const response = await fetch(canvas.dataset.src, {
      credentials: "same-origin",
      cache: "no-store",
    });
    if (!response.ok) return;
    const bitmap = await createImageBitmap(await response.blob());
    images.set(canvas, bitmap);
    draw(canvas);
    delete canvas.dataset.src;
  }

  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          observer.unobserve(entry.target);
          load(entry.target).catch(() => {});
        }
      }
    }, { rootMargin: "320px" });
    canvases.forEach((canvas) => observer.observe(canvas));
  } else {
    canvases.forEach((canvas) => load(canvas).catch(() => {}));
  }

  const clearPages = () => canvases.forEach((canvas) => {
    const context = canvas.getContext("2d");
    context.clearRect(0, 0, canvas.width, canvas.height);
  });
  const redrawPages = () => canvases.forEach(draw);

  document.addEventListener("contextmenu", (event) => event.preventDefault());
  document.addEventListener("selectstart", (event) => event.preventDefault());
  document.addEventListener("dragstart", (event) => event.preventDefault());
  document.addEventListener("copy", (event) => event.preventDefault());
  document.addEventListener("cut", (event) => event.preventDefault());
  document.addEventListener("keydown", (event) => {
    const key = event.key.toLowerCase();
    if (event.key === "PrintScreen") {
      clearPages();
      setTimeout(redrawPages, 1000);
    }
    if (
      event.key === "F12" ||
      ((event.ctrlKey || event.metaKey) && ["p", "s", "c", "u"].includes(key)) ||
      (event.ctrlKey && event.shiftKey && ["i", "j"].includes(key))
    ) event.preventDefault();
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) clearPages();
    else redrawPages();
  });
  window.addEventListener("blur", clearPages);
  window.addEventListener("focus", redrawPages);
})();
