document.addEventListener("DOMContentLoaded", function () {
  const birthDateInput = document.getElementById("i12");
  const deathDateInput = document.getElementById("i14"); 

  function validateDates() {
    const birthDateStr = birthDateInput.value;
    const deathDateStr = deathDateInput.value;

    birthDateInput.classList.remove("date-error");

    if (birthDateStr && deathDateStr) {
      const birthDate = new Date(birthDateStr);
      const deathDate = new Date(deathDateStr);

      if (birthDate > deathDate) {
        birthDateInput.classList.add("date-error");
      }
    }
  }

  birthDateInput.addEventListener("change", validateDates);
  deathDateInput.addEventListener("change", validateDates);

  validateDates();
});
