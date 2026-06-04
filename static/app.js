const editor = document.getElementById("configEditor");
const statusEl = document.getElementById("status");
const outputsEl = document.getElementById("outputs");
const previewEl = document.getElementById("preview");
const previewNameEl = document.getElementById("previewName");
const readoutToolEl = document.getElementById("readoutTool");
const readoutFlutesEl = document.getElementById("readoutFlutes");
const readoutTargetEl = document.getElementById("readoutTarget");
const measureGroupEl = document.getElementById("measureGroup");
const limitMappings = [
    ["limitXMin", "x_min"],
    ["limitXMax", "x_max"],
    ["limitYMin", "y_min"],
    ["limitYMax", "y_max"],
    ["limitZMin", "z_min"],
    ["limitZMax", "z_max"],
    ["limitAMin", "a_min"],
    ["limitAMax", "a_max"],
];
const probeMappings = [
    ["probeBallDiameter", "tastkugel_durchmesser"],
    ["probeFeed", "probe_feed"],
    ["probeSafeZ", "safe_z"],
    ["probeRetract", "retract"],
    ["probeFrontXTarget", "front_x_probe_target"],
    ["probeDiameterZTarget", "diameter_z_probe_target"],
];
const defaultProbeConfig = {
    steuerung: "linuxcnc",
    tastkugel_durchmesser: 3.0,
    probe_feed: 50.0,
    rapid_feed: 800.0,
    safe_z: 20.0,
    retract: 2.0,
    front_x_probe_target: -5.0,
    diameter_z_probe_target: -2.0,
    ausgabe_datei: "fraeser_vermessen.ngc",
};

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
    const diameter = cfg?.fraeser?.durchmesser ?? "";
    const flutes = cfg?.fraeser?.schneidenanzahl ?? "";
    const target = cfg?.aktionen?.schneiden?.durchmesser_geschaerft ?? "";

    document.getElementById("toolDiameter").value = diameter;
    document.getElementById("flutes").value = flutes;
    document.getElementById("targetDiameter").value = target;
    document.getElementById("frontXEnd").value = cfg?.aktionen?.front?.x_end ?? "";
    const probe = {...defaultProbeConfig, ...(cfg?.aktionen?.vermessen || {})};
    for (const [id, key] of probeMappings) {
        document.getElementById(id).value = probe[key] ?? "";
    }
    for (const [id, key] of limitMappings) {
        document.getElementById(id).value = cfg?.maschine?.limits?.[key] ?? "";
    }

    readoutToolEl.textContent = diameter === "" ? "-" : `${formatNumber(diameter)} mm`;
    readoutFlutesEl.textContent = flutes === "" ? "-" : `${flutes}`;
    readoutTargetEl.textContent = target === "" ? "-" : `${formatNumber(target)} mm`;
}

function applyQuickFields() {
    const cfg = readConfig();
    cfg.fraeser = cfg.fraeser || {};
    cfg.aktionen = cfg.aktionen || {};
    cfg.aktionen.schneiden = cfg.aktionen.schneiden || {};
    cfg.aktionen.front = cfg.aktionen.front || {};
    cfg.aktionen.vermessen = {...defaultProbeConfig, ...(cfg.aktionen.vermessen || {})};
    cfg.maschine = cfg.maschine || {};
    cfg.maschine.limits = cfg.maschine.limits || {};

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
    for (const [id, key] of probeMappings) {
        const value = document.getElementById(id).value;
        if (value === "") {
            delete cfg.aktionen.vermessen[key];
        } else {
            cfg.aktionen.vermessen[key] = Number(value);
        }
    }
    cfg.aktionen.vermessen.rapid_feed = Number(cfg.aktionen.vermessen.rapid_feed || defaultProbeConfig.rapid_feed);
    cfg.aktionen.vermessen.steuerung = cfg.aktionen.vermessen.steuerung || defaultProbeConfig.steuerung;
    cfg.aktionen.vermessen.ausgabe_datei = cfg.aktionen.vermessen.ausgabe_datei || defaultProbeConfig.ausgabe_datei;
    for (const [id, key] of limitMappings) {
        const value = document.getElementById(id).value;
        if (value === "") {
            delete cfg.maschine.limits[key];
        } else {
            cfg.maschine.limits[key] = Number(value);
        }
    }
    if (!Object.keys(cfg.maschine.limits).length) {
        delete cfg.maschine.limits;
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
        applyQuickFields();
        cfg = readConfig();
    } catch (error) {
        showErrors(["JSON ist ungültig: " + error.message]);
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

document.querySelectorAll("input[name=mode]").forEach(input => {
    input.addEventListener("change", updateModePanels);
});

document.getElementById("applyQuick").addEventListener("click", () => {
    try {
        applyQuickFields();
        setStatus("Übernommen");
    } catch (error) {
        showErrors(["JSON ist ungültig: " + error.message]);
        setStatus("Fehler");
    }
});

document.getElementById("formatJson").addEventListener("click", () => {
    try {
        writeConfig(readConfig());
        setStatus("Formatiert");
    } catch (error) {
        showErrors(["JSON ist ungültig: " + error.message]);
        setStatus("Fehler");
    }
});

document.getElementById("generate").addEventListener("click", () => {
    generate().catch(error => {
        showErrors([error.message]);
        setStatus("Fehler");
    });
});

document.getElementById("generateTop").addEventListener("click", () => {
    document.getElementById("generate").click();
});

editor.addEventListener("input", () => {
    try {
        fillQuickFields(readConfig());
    } catch {
        readoutToolEl.textContent = "-";
        readoutFlutesEl.textContent = "-";
        readoutTargetEl.textContent = "-";
        for (const [id] of probeMappings) {
            document.getElementById(id).value = "";
        }
        for (const [id] of limitMappings) {
            document.getElementById(id).value = "";
        }
    }
});

function formatNumber(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return value;
    return number.toLocaleString("de-DE", {maximumFractionDigits: 2});
}

function updateModePanels() {
    const mode = document.querySelector("input[name=mode]:checked").value;
    measureGroupEl.hidden = mode !== "measure";
}

fillQuickFields(window.initialConfig);
updateModePanels();
