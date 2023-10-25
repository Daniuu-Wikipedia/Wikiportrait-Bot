// script.js (by ChatGPT)
// We need to define separate functions for all relevant input fields

function changeBackgroundColorFile(value) {
    var inputField = document.getElementById('File');

    // Define the acceptable file extensions
    var validExtensions = [".png", ".jpeg", ".gif", ".bmp", ".svg", ".jpg", ".tiff"];

    // Praise the Lord: do some processing on the input
    value = value.trim();  // Remove leading and trailing spaces
    value = value.toLowerCase();  // Make the function case-insensitive (and convert input to lowercase)

    // Check if the input value ends with a valid extension
    var isValidExtension = validExtensions.some(function(extension) {
        return value.endsWith(extension);
    });

    if (isValidExtension) {
        // Note: value for the color objects.startcol had to be hardcoded here :(
        inputField.style.backgroundColor = '#ceffaa';
    } else if (value === 'file' || value === 'test' || value === 'bestand'){
        inputField.style.backgroundColor = 'red';
    } else {
        inputField.style.backgroundColor = 'rgb(185, 233, 255)';
    }
    // Unfortunately, we need to hardcode the color code for Wikiportret & the input layer in here
}
