(() => {
  const field = document.querySelector("#id_company_description");
  const counter = document.querySelector("#company-description-counter");
  const form = document.querySelector("[data-generation-form]");

  if (field && counter) {
    const updateCounter = () => {
      counter.textContent = `${field.value.length} / 5000`;
    };
    field.addEventListener("input", updateCounter);
    updateCounter();
  }

  if (form) {
    form.addEventListener("submit", () => {
      const button = form.querySelector("button[type='submit']");
      const label = form.querySelector("[data-button-label]");
      if (button && label && form.checkValidity()) {
        button.disabled = true;
        label.textContent = "Generando plan...";
      }
    });
  }
})();
