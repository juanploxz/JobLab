(() => {
  document.documentElement.classList.add("js");
  const field = document.querySelector("#id_company_description");
  const counter = document.querySelector("#company-description-counter");
  const form = document.querySelector("[data-generation-form]");

  if (field && counter) {
    const maximum = field.getAttribute("maxlength") || "5000";
    const updateCounter = () => {
      counter.textContent = `${field.value.length} / ${maximum}`;
    };
    field.addEventListener("input", updateCounter);
    updateCounter();
  }

  if (form && field) {
    const errorBox = form.querySelector("[data-client-error]");
    const minimum = Number(field.dataset.minLength || 0);
    const showError = (message) => {
      if (!errorBox) return;
      errorBox.textContent = message;
      field.setAttribute("aria-invalid", message ? "true" : "false");
      field.closest(".form-field")?.classList.toggle("has-error", Boolean(message));
    };

    field.addEventListener("input", () => {
      if (field.value.trim().length >= minimum) showError("");
    });

    form.addEventListener("submit", (event) => {
      if (field.value.trim().length < minimum) {
        event.preventDefault();
        showError(form.dataset.minError || "");
        field.focus();
        return;
      }
      const button = form.querySelector("button[type='submit']");
      const label = form.querySelector("[data-button-label]");
      if (button && label) {
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
        label.textContent = form.dataset.loadingLabel || label.textContent;
      }
    });
  }

  document.querySelectorAll("[data-auto-submit]").forEach((select) => {
    select.addEventListener("change", () => select.form?.submit());
  });

  const toggle = document.querySelector("[data-nav-toggle]");
  const links = document.querySelector("#primary-links");
  if (toggle && links) {
    toggle.addEventListener("click", () => {
      const open = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", String(!open));
      links.classList.toggle("is-open", !open);
    });
  }
})();
