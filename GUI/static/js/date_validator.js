document.addEventListener("DOMContentLoaded", function () {
  const birthDateInput = document.getElementById("i14");
  const deathDateInput = document.getElementById("i13");
  const imageDateInput = document.getElementById("i12");

function validateDates() {

  const birthDateStr = birthDateInput.value;
  const deathDateStr = deathDateInput.value;
  const imageDateStr = imageDateInput.value;

  birthDateInput.classList.remove("date-error");
  deathDateInput.classList.remove("date-error");
  imageDateInput.classList.remove("date-error");

  const birthDate = birthDateStr ? new Date(birthDateStr) : null;
  const deathDate = deathDateStr ? new Date(deathDateStr) : null;
  const imageDate = imageDateStr ? new Date(imageDateStr) : null;

  // birthDate <= deathDate
  if (birthDate > deathDate || imageDate > deathDate) {
    birthDateInput.classList.add("date-error");
  }

  // birthDate <= imageDate
  if (birthDate > imageDate) {
    birthDateInput.classList.add("date-error");
  }

  // imageDate <= deathDate
  if (imageDate && deathDate && imageDate > deathDate) {
    imageDateInput.classList.add("date-error");
  }
}
  birthDateInput.addEventListener("change", validateDates);
  deathDateInput.addEventListener("change", validateDates);
  imageDateInput.addEventListener("change", validateDates);

  validateDates();
});
