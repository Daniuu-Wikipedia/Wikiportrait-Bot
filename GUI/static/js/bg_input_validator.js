function checkForProhibitedCharacters(value) {
    var inputField = document.getElementById('Article');

    // Define the prohibited characters
    var prohibitedCharacters = "<>{};";

    // Praise the Lord: do some processing on the input
    value = value.trim();  // Remove leading and trailing spaces

    // Check if the input value contains any prohibited characters
    var containsProhibitedCharacters = [...value].some(function(char) {
        return prohibitedCharacters.includes(char);
    });

    if (containsProhibitedCharacters) {
        inputField.style.backgroundColor = '#ff0000';
    } else {
        inputField.style.backgroundColor = 'rgb(185, 233, 255)';
    }
}
