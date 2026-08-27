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

const researchTimeline = document.querySelector("[data-research-timeline]");
if (researchTimeline) {
  const phaseLinks = Array.from(
    researchTimeline.querySelectorAll("[data-research-phase-nav]")
  );
  const phaseSections = Array.from(
    researchTimeline.querySelectorAll("[data-research-phase]")
  );
  let ticking = false;

  function setActiveResearchPhase(phase) {
    phaseLinks.forEach((link) => {
      link.classList.toggle("is-active", link.dataset.researchPhaseNav === phase);
    });
  }

  function updateResearchPhase() {
    const readingLine = window.innerHeight * 0.42;
    let activePhase = phaseSections[0]?.dataset.researchPhase;

    phaseSections.forEach((section) => {
      if (section.getBoundingClientRect().top <= readingLine) {
        activePhase = section.dataset.researchPhase;
      }
    });

    if (activePhase) setActiveResearchPhase(activePhase);
    ticking = false;
  }

  function requestResearchPhaseUpdate() {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(updateResearchPhase);
  }

  updateResearchPhase();
  window.addEventListener("scroll", requestResearchPhaseUpdate, { passive: true });
  window.addEventListener("resize", requestResearchPhaseUpdate);
}
