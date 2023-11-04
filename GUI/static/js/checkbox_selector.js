document.addEventListener("DOMContentLoaded", function() {
    // Get the checkbox element
    const checkbox = document.getElementById("check23");

    // Get the selection element
    const select = document.getElementById("license");

    // Add an event listener to the checkbox
    checkbox.addEventListener("change", function() {
        if (this.checked) {
            select.removeAttribute("disabled");
        } else {
            select.setAttribute("disabled", "disabled");
        }
    });
});
