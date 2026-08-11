// Sidebar toggle (mobile)
const menuToggle = document.getElementById('menuToggle');
const sidebar = document.getElementById('sidebar');
const sidebarOverlay = document.getElementById('sidebarOverlay');
const sidebarClose = document.getElementById('sidebarClose');

function openSidebar() {
    sidebar && sidebar.classList.add('open');
    sidebarOverlay && sidebarOverlay.classList.add('open');
}
function closeSidebar() {
    sidebar && sidebar.classList.remove('open');
    sidebarOverlay && sidebarOverlay.classList.remove('open');
}
menuToggle && menuToggle.addEventListener('click', openSidebar);
sidebarClose && sidebarClose.addEventListener('click', closeSidebar);
sidebarOverlay && sidebarOverlay.addEventListener('click', closeSidebar);

// Auto-dismiss alerts after 5 seconds
document.querySelectorAll('.alert').forEach(alert => {
    setTimeout(() => {
        alert.style.opacity = '0';
        alert.style.transform = 'translateY(-8px)';
        alert.style.transition = 'all 0.4s ease';
        setTimeout(() => alert.remove(), 400);
    }, 5000);
});

// Animate stat cards on load
document.querySelectorAll('.stat-card').forEach((card, i) => {
    card.style.opacity = '0';
    card.style.transform = 'translateY(20px)';
    setTimeout(() => {
        card.style.transition = 'all 0.4s ease';
        card.style.opacity = '1';
        card.style.transform = 'translateY(0)';
    }, i * 80);
});

// Animate bar chart fills
document.querySelectorAll('.bar-fill').forEach(bar => {
    const targetH = bar.style.height;
    bar.style.height = '0';
    setTimeout(() => {
        bar.style.transition = 'height 0.7s ease';
        bar.style.height = targetH;
    }, 300);
});

// Animate category bar fills
document.querySelectorAll('.cat-bar-fill').forEach(bar => {
    const targetW = bar.style.width;
    bar.style.width = '0';
    setTimeout(() => {
        bar.style.transition = 'width 0.8s ease';
        bar.style.width = targetW;
    }, 400);
});

// Book card hover tilt effect
document.querySelectorAll('.book-card').forEach(card => {
    card.addEventListener('mousemove', (e) => {
        const rect = card.getBoundingClientRect();
        const x = (e.clientX - rect.left) / rect.width - 0.5;
        const y = (e.clientY - rect.top) / rect.height - 0.5;
        card.style.transform = `translateY(-4px) rotateY(${x * 5}deg) rotateX(${-y * 4}deg)`;
    });
    card.addEventListener('mouseleave', () => {
        card.style.transform = '';
    });
});

// Confirm delete with custom style
document.querySelectorAll('form[onsubmit]').forEach(form => {
    form.addEventListener('submit', function(e) {
        // Already handled via inline onsubmit
    });
});

// Search input auto-submit after typing (debounce)
const searchInputs = document.querySelectorAll('.search-bar input');
searchInputs.forEach(input => {
    let timer;
    input.addEventListener('keyup', () => {
        clearTimeout(timer);
        timer = setTimeout(() => {
            if (input.value.length > 2 || input.value.length === 0) {
                input.closest('form') && input.closest('form').submit();
            }
        }, 600);
    });
});

console.log('%c Library Management System ', 'background:#e8650a;color:#fff;font-size:14px;padding:4px 10px;border-radius:4px;font-weight:700;');
console.log('%c Built with Flask + SQLite ', 'color:#94a3b8;font-size:11px;');
