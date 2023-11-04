// Control the state of text input fields (deactivate them if the associated checkbox is not active)
// Script gracefully supplied by ChatGPT
document.addEventListener("DOMContentLoaded", function() {
    // Get all checkboxes in the form
    const checkboxes = document.querySelectorAll('input[type="checkbox"]');

    checkboxes.forEach(function(checkbox) {
        // Check if the checkbox matches your naming convention (e.g., "checkXX")
        if (checkbox.id.startsWith("check")) {
            // Get the corresponding input field
            const inputId = checkbox.id.replace("check", "i");
            const inputField = document.getElementById(inputId);

            // Add an event listener to the checkbox
            checkbox.addEventListener("change", function() {
                if (this.checked) {
                    inputField.removeAttribute("disabled");
                } else {
                    inputField.setAttribute("disabled", "disabled");
                }
            });
        }
    });
});
