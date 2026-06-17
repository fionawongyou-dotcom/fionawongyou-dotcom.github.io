const menu = document.querySelector("[data-menu]");
const openButtons = document.querySelectorAll("[data-menu-open]");
const closeButton = document.querySelector("[data-menu-close]");

function openMenu() {
  if (!menu) return;
  menu.hidden = false;
  document.documentElement.classList.add("menu-active");
}

function closeMenu() {
  if (!menu) return;
  menu.hidden = true;
  document.documentElement.classList.remove("menu-active");
}

openButtons.forEach((button) => button.addEventListener("click", openMenu));
closeButton?.addEventListener("click", closeMenu);
menu?.addEventListener("click", (event) => {
  if (event.target === menu || event.target.closest("a")) closeMenu();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeMenu();
});
