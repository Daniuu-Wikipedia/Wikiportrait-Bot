document.addEventListener("DOMContentLoaded", function () {
  const birthDateInput = document.getElementById("i14");
  const deathDateInput = document.getElementById("i13");
  const imageDateInput = document.getElementById("i12");


  birthDateInput.classList.remove("date-error");
  deathDateInput.classList.remove("date-error");
  imageDateInput.classList.remove("date-error");

  const birthDate = birthDateStr ? new Date(birthDateStr) : null;
  const deathDate = deathDateStr ? new Date(deathDateStr) : null;
  const imageDate = imageDateStr ? new Date(imageDateStr) : null;

  // birthDate <= deathDate
  if (birthDate > deathDate || imageDate > deathDate || birthDate > imageDate) {
    birthDateInput.classList.add("date-error");
    deathDateInput.classList.add("date-error");
    imageDateInput.classList.add("date-error");
  }


  birthDateInput.addEventListener("change", validateDates);
  deathDateInput.addEventListener("change", validateDates);
  imageDateInput.addEventListener("change", validateDates);

  validateDates();
});
