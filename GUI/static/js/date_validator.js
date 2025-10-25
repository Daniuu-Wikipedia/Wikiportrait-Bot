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
  if (birthDate != null && deathDate != null) {
      if (birthDate > deathDate) {
        birthDateInput.classList.add("date-error");
        deathDateInput.classList.add("date-error");
      }
  }

  // birthDate <= imageDate
  if (birthDate != null && imageDate != null) {
      if (birthDate > imageDate) {
      birthDateInput.classList.add("date-error");
      imageDateInput.classList.add("date-error");
    }
  }

  // Ideally, no images taken after the chap died
  if (imageDate != null && deathDate != null) {
      if (imageDate > deathDate) {
      imageDateInput.classList.add("date-error");
      deathDateInput.classList.add("date-error");
    }
  }
}

  birthDateInput.addEventListener("change", validateDates);
  deathDateInput.addEventListener("change", validateDates);
  imageDateInput.addEventListener("change", validateDates);

  validateDates();
});
