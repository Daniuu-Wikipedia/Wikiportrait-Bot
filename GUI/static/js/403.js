document.addEventListener('DOMContentLoaded', () => {
    const mainText = document.querySelector('.main-text');

    document.addEventListener('mousemove', (e) => {
        const rect = mainText.getBoundingClientRect();
        
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        mainText.style.setProperty('--mouse-x', `${x}px`);
        mainText.style.setProperty('--mouse-y', `${y}px`);
    });
});
