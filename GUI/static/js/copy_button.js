function copyText() {
    var copyText = document.getElementById("copyText");
    copyText.select();
    copyText.setSelectionRange(0, 99999);
    document.execCommand("copy");
    // alert("Text copied to clipboard");
}