const editor = document.getElementById("configEditor");
const statusEl = document.getElementById("status");
const outputsEl = document.getElementById("outputs");
const previewEl = document.getElementById("preview");
const previewNameEl = document.getElementById("previewName");

function setStatus(text) {
    statusEl.textContent = text;
}

function readConfig() {
    return JSON.parse(editor.value);
}

function writeConfig(cfg) {
    editor.value = JSON.stringify(cfg, null, 2);
    fillQuickFields(cfg);
}

function fillQuickFields(cfg) {
    document.getElementById("toolDiameter").value = cfg?.fraeser?.durchmesser ?? "";
    document.getElementById("flutes").value = cfg?.fraeser?.schneidenanzahl ?? "";
    document.getElementById("targetDiameter").value = cfg?.aktionen?.schneiden?.durchmesser_geschaerft ?? "";
    document.getElementById("frontXEnd").value = cfg?.aktionen?.front?.x_end ?? "";
}

function applyQuickFields() {
    const cfg = readConfig();
    cfg.fraeser = cfg.fraeser || {};
    cfg.aktionen = cfg.aktionen || {};
    cfg.aktionen.schneiden = cfg.aktionen.schneiden || {};
    cfg.aktionen.front = cfg.aktionen.front || {};

    const mappings = [
        ["toolDiameter", cfg.fraeser, "durchmesser"],
        ["flutes", cfg.fraeser, "schneidenanzahl"],
        ["targetDiameter", cfg.aktionen.schneiden, "durchmesser_geschaerft"],
        ["frontXEnd", cfg.aktionen.front, "x_end"],
    ];
    for (const [id, target, key] of mappings) {
        const value = document.getElementById(id).value;
        if (value !== "") target[key] = Number(value);
    }
    writeConfig(cfg);
}

async function loadTemplate(name) {
    setStatus("Lade Vorlage");
    const response = await fetch(`/api/templates/${encodeURIComponent(name)}`);
    if (!response.ok) throw new Error("Vorlage konnte nicht geladen werden.");
    writeConfig(await response.json());
    outputsEl.innerHTML = "";
    previewEl.textContent = "(Noch kein G-Code erzeugt)";
    previewNameEl.textContent = "";
    setStatus("Bereit");
}

async function generate() {
    outputsEl.innerHTML = "";
    previewEl.textContent = "";
    previewNameEl.textContent = "";
    setStatus("Generiere");

    let cfg;
    try {
        cfg = readConfig();
    } catch (error) {
        showErrors(["JSON ist ungueltig: " + error.message]);
        setStatus("Fehler");
        return;
    }

    const mode = document.querySelector("input[name=mode]:checked").value;
    const response = await fetch("/api/generate", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({mode, config: cfg}),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) {
        showErrors(result.errors || ["Unbekannter Fehler"]);
        setStatus("Fehler");
        return;
    }

    for (const file of result.files) {
        const item = document.createElement("div");
        item.className = "output-item";
        item.innerHTML = `<strong>${file.name}</strong><div>${file.bytes} Bytes</div><a href="${file.download_url}">Download</a>`;
        item.addEventListener("click", () => {
            previewNameEl.textContent = file.name;
            previewEl.textContent = file.preview;
        });
        outputsEl.appendChild(item);
    }
    if (result.files.length) {
        previewNameEl.textContent = result.files[0].name;
        previewEl.textContent = result.files[0].preview;
    }
    setStatus("Fertig");
}

function showErrors(errors) {
    outputsEl.innerHTML = "";
    const item = document.createElement("div");
    item.className = "output-item error";
    item.innerHTML = `<strong>Fehler</strong>${errors.map(e => `<div>${escapeHtml(e)}</div>`).join("")}`;
    outputsEl.appendChild(item);
}

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, ch => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "\"": "&quot;",
        "'": "&#39;",
    }[ch]));
}

document.getElementById("templateSelect").addEventListener("change", event => {
    loadTemplate(event.target.value).catch(error => {
        showErrors([error.message]);
        setStatus("Fehler");
    });
});

document.getElementById("applyQuick").addEventListener("click", () => {
    try {
        applyQuickFields();
        setStatus("Uebernommen");
    } catch (error) {
        showErrors(["JSON ist ungueltig: " + error.message]);
        setStatus("Fehler");
    }
});

document.getElementById("formatJson").addEventListener("click", () => {
    try {
        writeConfig(readConfig());
        setStatus("Formatiert");
    } catch (error) {
        showErrors(["JSON ist ungueltig: " + error.message]);
        setStatus("Fehler");
    }
});

document.getElementById("generate").addEventListener("click", () => {
    generate().catch(error => {
        showErrors([error.message]);
        setStatus("Fehler");
    });
});

fillQuickFields(window.initialConfig);
