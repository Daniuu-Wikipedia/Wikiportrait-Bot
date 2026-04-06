document.addEventListener("DOMContentLoaded", function () {
  const progressBar = document.querySelector(".progress");
  const loadingMessage = document.getElementById("loading-message");
  let progress = 0;

  function updateProgress() {
    progress += 20;
    progressBar.style.width = progress + "%";

    if (progress >= 100) {
      loadingMessage.textContent = "Voltooid! Doorsturen...";
      setTimeout(function () {
        window.location.href = "/statussubmit";
      }, 3000);
    } else {
      loadingMessage.textContent = "Gegevens laden: " + progress + "%";
      setTimeout(updateProgress, 3000);
    }
  }
  setTimeout(function () {
    updateProgress();
  }, 3000);
});
