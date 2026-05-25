// ── Sidebar Toggle ────────────────────────────────────────────────────────────
const sidebarToggle = document.getElementById('sidebarToggle');
const sidebar = document.getElementById('sidebar');
const body = document.body;

if (sidebarToggle) {
  sidebarToggle.addEventListener('click', () => {
    if (window.innerWidth <= 768) {
      sidebar.classList.toggle('show');
    } else {
      body.classList.toggle('sidebar-collapsed');
    }
  });
}

// Close sidebar on mobile when clicking outside
document.addEventListener('click', (e) => {
  if (window.innerWidth <= 768 && sidebar && sidebar.classList.contains('show')) {
    if (!sidebar.contains(e.target) && e.target !== sidebarToggle) {
      sidebar.classList.remove('show');
    }
  }
});

// ── Delete Confirmation Modal ─────────────────────────────────────────────────
function confirmDelete(url, message) {
  const modal = document.getElementById('deleteModal');
  const form = document.getElementById('deleteForm');
  const body = document.getElementById('deleteModalBody');
  if (body) body.innerHTML = message || 'Are you sure you want to delete this item?';
  if (form) form.action = url;
  const bsModal = new bootstrap.Modal(modal);
  bsModal.show();
}

// ── Toast Notifications ───────────────────────────────────────────────────────
function showToast(message, type = 'success') {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const icons = { success: 'check-circle-fill', danger: 'x-circle-fill', warning: 'exclamation-triangle-fill', info: 'info-circle-fill' };
  const colors = { success: 'text-success', danger: 'text-danger', warning: 'text-warning', info: 'text-info' };
  const toast = document.createElement('div');
  toast.className = 'toast show align-items-center border-0 shadow';
  toast.setAttribute('role', 'alert');
  toast.innerHTML = `
    <div class="d-flex">
      <div class="toast-body d-flex align-items-center gap-2">
        <i class="bi bi-${icons[type] || 'info-circle-fill'} ${colors[type] || ''}"></i>
        ${message}
      </div>
      <button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast"></button>
    </div>`;
  container.appendChild(toast);
  setTimeout(() => { toast.classList.remove('show'); setTimeout(() => toast.remove(), 300); }, 3500);
}

// ── Auto-dismiss alerts ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.alert:not(.low-stock-banner)').forEach(alert => {
    setTimeout(() => {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      if (bsAlert) bsAlert.close();
    }, 4000);
  });
});
