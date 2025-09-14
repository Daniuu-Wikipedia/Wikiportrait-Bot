document.addEventListener("DOMContentLoaded", function () {
  const ids = ["i12", "i13", "i14"];

  function isValidDateNotFuture(dateString) {
    const date = new Date(dateString);
    if (isNaN(date)) return false; // not a valid date
    const today = new Date();
    today.setHours(0, 0, 0, 0); // strip time
    date.setHours(0, 0, 0, 0);
    return date <= today;
  }

  ids.forEach(id => {
    const input = document.getElementById(id);
    if (input) {
      input.addEventListener("change", () => {
        if (!isValidDateNotFuture(input.value)) {
          alert(`The date in ${id} must not be later than today.`);
          input.value = ""; // clear invalid value
          input.focus();
        }
      });
    }
  });
});
