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
        window.location.href = "/review";
      }, 1000);
    } else {
      loadingMessage.textContent = "Gegevens laden: " + progress + "%";
      setTimeout(updateProgress, 500);
    }
  }
  setTimeout(function () {
    updateProgress();
  }, 1000);
});
