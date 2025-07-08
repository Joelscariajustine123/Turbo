const ctx = document.getElementById('earningsChart').getContext('2d');
const earningsChart = new Chart(ctx, {
type: 'bar',
data: {
 labels: ['Total', 'This Week', 'This Month', 'Completed Rides'],
 datasets: [{
 label: 'Earnings Overview',
 data: [2450, 320, 1100, 88],
 backgroundColor: ['#4CAF50', '#2196F3', '#FFC107', '#FF5722'],
 borderRadius: 8
}]
     },
options: {
responsive: true,
plugins: {
legend: {
display: false
  }
 },
scales: {
y: {
beginAtZero: true,
title: {
  display: true,
  text: 'Amount ($ or Count)'
}
}
}
}
});


document.addEventListener('DOMContentLoaded', () => {
    const sections = document.querySelectorAll('section');
    sections.forEach((section, i) => {
      section.style.animationDelay = `${i * 0.15}s`;
    });
  });

  document.querySelector(".settings-form").addEventListener("submit", function (e) {
    e.preventDefault();
    alert("Your settings have been saved.");
  });