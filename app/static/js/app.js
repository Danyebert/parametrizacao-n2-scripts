window.sqlEditors = window.sqlEditors || {};

window.initSqlEditor = function (elementId, readOnly) {
  const textarea = document.getElementById(elementId);

  if (!textarea || typeof CodeMirror === "undefined") {
    return null;
  }

  const editor = CodeMirror.fromTextArea(textarea, {
    mode: "text/x-sql",
    theme: "material-darker",
    lineNumbers: true,
    lineWrapping: true,
    readOnly: !!readOnly,
    viewportMargin: Infinity
  });

  window.sqlEditors[elementId] = editor;

  return editor;
};

document.addEventListener("click", async function (event) {
  const copyBtn = event.target.closest("[data-copy-target]");

  if (copyBtn) {
    const id = copyBtn.getAttribute("data-copy-target");
    const editor = window.sqlEditors[id];
    const textarea = document.getElementById(id);
    const text = editor ? editor.getValue() : textarea ? textarea.value : "";

    if (text) {
      await navigator.clipboard.writeText(text);

      const original = copyBtn.innerHTML;
      copyBtn.innerHTML = '<i class="bi bi-check2"></i> Copiado';

      setTimeout(function () {
        copyBtn.innerHTML = original;
      }, 1600);
    }
  }

  const sidebarBtn = event.target.closest("[data-toggle-sidebar]");

  if (sidebarBtn) {
    const sidebar = document.querySelector(".sidebar");

    if (!sidebar) {
      return;
    }

    if (window.innerWidth <= 992) {
      sidebar.classList.toggle("open");
    } else {
      sidebar.classList.toggle("sidebar-collapsed");
      document.body.classList.toggle("sidebar-is-collapsed");
    }
  }
});