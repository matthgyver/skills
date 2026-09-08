// Point d'entrée JS unique. Pour un petit site servi par Jinja2, préférer la délégation
// d'événements sur document plutôt que d'attacher des listeners un par un — ça fonctionne
// aussi pour du contenu injecté dynamiquement (ex: fragments HTMX).

document.addEventListener("DOMContentLoaded", () => {
  // Exemple : toggle d'un menu mobile
  const navToggle = document.querySelector("[data-nav-toggle]");
  const nav = document.querySelector(".site-nav__links");
  if (navToggle && nav) {
    navToggle.addEventListener("click", () => {
      nav.classList.toggle("is-open");
    });
  }
});

// Délégation générique : pratique pour du contenu ajouté après coup (ex: via HTMX)
document.addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-confirm]");
  if (trigger && !window.confirm(trigger.dataset.confirm)) {
    event.preventDefault();
    event.stopPropagation();
  }
});
