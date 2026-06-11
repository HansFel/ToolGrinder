const editor = document.getElementById("configEditor");
const statusEl = document.getElementById("status");
const outputsEl = document.getElementById("outputs");
const previewEl = document.getElementById("preview");
const previewNameEl = document.getElementById("previewName");
const readoutToolEl = document.getElementById("readoutTool");
const readoutFlutesEl = document.getElementById("readoutFlutes");
const readoutTargetEl = document.getElementById("readoutTarget");
const measureGroupEl = document.getElementById("measureGroup");
const languageSelectEl = document.getElementById("languageSelect");
const translations = {
    de: {
        language: "Sprache",
        subtitle: "4-Achs Werkzeugschleifen XYZA · Z0 im Werkzeug-Drehmittelpunkt",
        generate: "G-Code erzeugen",
        machineVisual: "Schematische Schleifsituation mit Drallfräser und Topfscheibe",
        axisLabel: "A-Achse dreht um X",
        wheelLabel: "Topfscheibe / Z-Spindel",
        contactLabel: "Schleifkontakt",
        cutter: "Fräser",
        flutes: "Schneiden",
        targetDiameter: "Ziel Ø",
        template: "Vorlage",
        mode: "Modus",
        measure: "Vermessen",
        cutterDiameter: "Fräser Ø",
        frontXEnd: "Front X Ende",
        probeTool: "Werkzeug antasten",
        helixDirection: "Drallrichtung",
        right: "Rechts",
        left: "Links",
        probeBallDiameter: "Tastkugel Ø",
        probeFeed: "Tastvorschub",
        safeZ: "Sicheres Z",
        retract: "Rückzug",
        frontProbeTarget: "Stirnkante X Ziel",
        diameterProbeTarget: "Durchmesser Z Ziel",
        aStart: "A Start",
        aEnd: "A Ende",
        aStep: "A Schritt",
        machineLimits: "Maschinenlimits",
        applyValues: "Werte übernehmen",
        jsonConfig: "Konfiguration JSON",
        format: "Formatieren",
        gcodePreview: "G-Code Vorschau",
        emptyPreview: "(Noch kein G-Code erzeugt)",
        ready: "Bereit",
        loadingTemplate: "Lade Vorlage",
        generating: "Generiere",
        error: "Fehler",
        finished: "Fertig",
        applied: "Übernommen",
        formatted: "Formatiert",
        templateLoadError: "Vorlage konnte nicht geladen werden.",
        invalidJson: "JSON ist ungültig: ",
        unknownError: "Unbekannter Fehler",
        bytes: "Bytes",
        download: "Download",
    },
    en: {
        language: "Language",
        subtitle: "4-axis XYZA tool grinding · Z0 at the tool rotation center",
        generate: "Generate G-code",
        machineVisual: "Schematic grinding setup with helical cutter and cup wheel",
        axisLabel: "A axis rotates around X",
        wheelLabel: "Cup wheel / Z spindle",
        contactLabel: "Grinding contact",
        cutter: "Cutter",
        flutes: "Flutes",
        targetDiameter: "Target Ø",
        template: "Template",
        mode: "Mode",
        measure: "Measure",
        cutterDiameter: "Cutter Ø",
        frontXEnd: "Front X end",
        probeTool: "Probe tool",
        helixDirection: "Helix direction",
        right: "Right",
        left: "Left",
        probeBallDiameter: "Probe ball Ø",
        probeFeed: "Probe feed",
        safeZ: "Safe Z",
        retract: "Retract",
        frontProbeTarget: "Front edge X target",
        diameterProbeTarget: "Diameter Z target",
        aStart: "A start",
        aEnd: "A end",
        aStep: "A step",
        machineLimits: "Machine limits",
        applyValues: "Apply values",
        jsonConfig: "JSON configuration",
        format: "Format",
        gcodePreview: "G-code preview",
        emptyPreview: "(No G-code generated yet)",
        ready: "Ready",
        loadingTemplate: "Loading template",
        generating: "Generating",
        error: "Error",
        finished: "Done",
        applied: "Applied",
        formatted: "Formatted",
        templateLoadError: "Template could not be loaded.",
        invalidJson: "JSON is invalid: ",
        unknownError: "Unknown error",
        bytes: "bytes",
        download: "Download",
    },
};
let currentLanguage = localStorage.getItem("toolgrinder-language") === "en" ? "en" : "de";
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
    ["probeAStart", "a_such_start"],
    ["probeAEnd", "a_such_ende"],
    ["probeAStep", "a_such_schritt"],
];
const defaultProbeConfig = {
    steuerung: "linuxcnc",
    drallrichtung: "rechts",
    tastkugel_durchmesser: 3.0,
    probe_feed: 50.0,
    rapid_feed: 800.0,
    safe_z: 20.0,
    retract: 2.0,
    front_x_probe_target: -5.0,
    diameter_z_probe_target: -2.0,
    a_such_start: 0.0,
    a_such_schritt: 2.0,
    ausgabe_datei: "fraeser_vermessen.ngc",
};

function t(key) {
    return translations[currentLanguage][key] || translations.de[key] || key;
}

function setStatus(key) {
    statusEl.dataset.statusKey = key;
    statusEl.textContent = t(key);
}

function applyLanguage(language) {
    currentLanguage = language === "en" ? "en" : "de";
    localStorage.setItem("toolgrinder-language", currentLanguage);
    document.documentElement.lang = currentLanguage;
    languageSelectEl.value = currentLanguage;
    document.querySelectorAll("[data-i18n]").forEach(element => {
        element.textContent = t(element.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-aria-label]").forEach(element => {
        element.setAttribute("aria-label", t(element.dataset.i18nAriaLabel));
    });
    setStatus(statusEl.dataset.statusKey || "ready");
    if (previewEl.dataset.emptyPreview === "true") {
        previewEl.textContent = t("emptyPreview");
    }
    fillQuickFields(readConfig());
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
    probe.a_such_ende = probe.a_such_ende ?? computeAEndFromFlutes(flutes, probe.a_such_start);
    document.getElementById("probeHelixDirection").value = probe.drallrichtung || defaultProbeConfig.drallrichtung;
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
    cfg.aktionen.vermessen.drallrichtung = document.getElementById("probeHelixDirection").value || defaultProbeConfig.drallrichtung;
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
    setStatus("loadingTemplate");
    const response = await fetch(`/api/templates/${encodeURIComponent(name)}`);
    if (!response.ok) throw new Error(t("templateLoadError"));
    writeConfig(await response.json());
    outputsEl.innerHTML = "";
    previewEl.dataset.emptyPreview = "true";
    previewEl.textContent = t("emptyPreview");
    previewNameEl.textContent = "";
    setStatus("ready");
}

async function generate() {
    outputsEl.innerHTML = "";
    previewEl.dataset.emptyPreview = "false";
    previewEl.textContent = "";
    previewNameEl.textContent = "";
    setStatus("generating");

    let cfg;
    try {
        applyQuickFields();
        cfg = readConfig();
    } catch (error) {
        showErrors([t("invalidJson") + error.message]);
        setStatus("error");
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
        showErrors(result.errors || [t("unknownError")]);
        setStatus("error");
        return;
    }

    for (const file of result.files) {
        const item = document.createElement("div");
        item.className = "output-item";
        item.innerHTML = `<strong>${file.name}</strong><div>${file.bytes} <span data-i18n="bytes">${t("bytes")}</span></div><a href="${file.download_url}" data-i18n="download">${t("download")}</a>`;
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
    setStatus("finished");
}

function showErrors(errors) {
    outputsEl.innerHTML = "";
    const item = document.createElement("div");
    item.className = "output-item error";
    item.innerHTML = `<strong data-i18n="error">${t("error")}</strong>${errors.map(e => `<div>${escapeHtml(e)}</div>`).join("")}`;
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
        setStatus("error");
    });
});

languageSelectEl.addEventListener("change", event => {
    applyLanguage(event.target.value);
});

document.querySelectorAll("input[name=mode]").forEach(input => {
    input.addEventListener("change", updateModePanels);
});

document.getElementById("flutes").addEventListener("input", () => {
    const start = document.getElementById("probeAStart").value || 0;
    document.getElementById("probeAEnd").value = computeAEndFromFlutes(document.getElementById("flutes").value, start);
});

document.getElementById("applyQuick").addEventListener("click", () => {
    try {
        applyQuickFields();
        setStatus("applied");
    } catch (error) {
        showErrors([t("invalidJson") + error.message]);
        setStatus("error");
    }
});

document.getElementById("formatJson").addEventListener("click", () => {
    try {
        writeConfig(readConfig());
        setStatus("formatted");
    } catch (error) {
        showErrors([t("invalidJson") + error.message]);
        setStatus("error");
    }
});

document.getElementById("generate").addEventListener("click", () => {
    generate().catch(error => {
        showErrors([error.message]);
        setStatus("error");
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
        document.getElementById("probeHelixDirection").value = defaultProbeConfig.drallrichtung;
        for (const [id] of limitMappings) {
            document.getElementById(id).value = "";
        }
    }
});

function formatNumber(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return value;
    return number.toLocaleString(currentLanguage === "en" ? "en-US" : "de-DE", {maximumFractionDigits: 2});
}

function computeAEndFromFlutes(flutes, start = 0) {
    const count = Number(flutes);
    const startAngle = Number(start) || 0;
    if (!Number.isFinite(count) || count <= 0) return 360 + startAngle;
    return startAngle + (360 / count);
}

function updateModePanels() {
    const mode = document.querySelector("input[name=mode]:checked").value;
    measureGroupEl.hidden = mode !== "measure";
}

applyLanguage(currentLanguage);
updateModePanels();
