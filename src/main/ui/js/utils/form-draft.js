function serializeForm(form) {
  if (!form) return "";
  const entries = [];
  new FormData(form).forEach((value, key) => {
    entries.push([String(key), typeof value === "string" ? value : value.name]);
  });
  return JSON.stringify(entries);
}

export function createFormDraftGuard({
  form,
  indicator = null,
  entityLabel = "form",
  showConfirmModal,
}) {
  let baseline = serializeForm(form);
  let dirty = false;
  let bound = false;

  function render() {
    if (indicator) indicator.hidden = !dirty;
    form?.toggleAttribute("data-dirty", dirty);
  }

  function sync() {
    dirty = serializeForm(form) !== baseline;
    render();
    return dirty;
  }

  function capture() {
    baseline = serializeForm(form);
    dirty = false;
    render();
  }

  function bind() {
    if (!form || bound) return;
    form.addEventListener("input", sync);
    form.addEventListener("change", sync);
    bound = true;
    render();
  }

  function isDirty() {
    return dirty;
  }

  async function confirmDiscard() {
    if (!dirty) return true;
    return showConfirmModal({
      title: `Discard ${entityLabel} changes?`,
      message: `You have unsaved changes in this ${entityLabel.toLowerCase()}. Discard them and close?`,
      confirmLabel: "Discard Changes",
      cancelLabel: "Keep Editing",
    });
  }

  return {
    bind,
    capture,
    confirmDiscard,
    isDirty,
    sync,
  };
}
