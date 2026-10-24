// Function to change the button text to "LOADING" when clicked
function changeButtonText() {
    console.log('Hit');
    var submitButton = document.getElementById("submit-button");
    submitButton.value = "LADEN";
    submitButton.disabled = true; // Optionally, disable the button to prevent multiple submissions
    submitButton.style.backgroundColor = 'gray'; // Color the button gray whenever it is hit
    setTimeout(function () {
            submitButton.value = "Verwerk";
            submitButton.disabled = false; // Re-enable the button
        }, 3000); // Change back after 3 seconds (adjust as needed)
}

// Add an event listener to the form to call the function when the form is submitted
// Use the form of the submit button itself: the page has other forms as well (e.g. the logout form in the navbar)
document.getElementById('submit-button').form.addEventListener('submit', changeButtonText);
