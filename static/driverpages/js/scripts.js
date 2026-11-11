// Stagger the fade-in animation of each section on driver pages.
// (Page-specific code such as the earnings chart lives in that page's template.)
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('section').forEach((section, i) => {
    section.style.animationDelay = `${i * 0.15}s`;
  });
});
