document.addEventListener("DOMContentLoaded", function () {
  const dateInput = document.getElementById("i12");

  // Functie to convert YYYY/MM/DD to DD/MM/YYYY
  function formatDate(dateString) {
    const date = new Date(dateString);
    const day = String(date.getDate()).padStart(2, "0");
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const year = date.getFullYear();
    return `${day}/${month}/${year}`;
  }

  // Change initial value to DD/MM/YYYY
  if (dateInput && dateInput.value) {
    dateInput.value = formatDate(dateInput.value);
  }
});
