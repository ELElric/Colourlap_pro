"""Multi-page QWebEngineView demo for ColorLab Pro.

Run from the repository root with the virtual environment activated:

    python src/colorlab_pro/ui/web_demo.py

The demo window has a left sidebar to switch between the four workspace
pages. Each page loads its improved HTML mockup and exchanges live data
with Python through QWebChannel.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QTimer, QUrl, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Make src/ importable when running this file directly
ROOT = Path(__file__).resolve().parent.parent.parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from colorlab_pro.controllers.color_controller import ColorController
from colorlab_pro.controllers.main_controller import MainController
from colorlab_pro.controllers.optimization_controller import OptimizationController
from colorlab_pro.controllers.project_controller import ProjectController
from colorlab_pro.controllers.spectrum_controller import SpectrumController
from colorlab_pro.dto.spectrum import Spectrum

# --------------------------------------------------------------------------- #
# Qt's qwebchannel.js inlined so the demo works without extra files.
# --------------------------------------------------------------------------- #
_QWEBCHANNEL_JS = """
// Copyright (C) 2016 The Qt Company Ltd.
// Copyright (C) 2016 Klarälvdalens Datakonsult AB, a KDAB Group company, info@kdab.com, author Milian Wolff <milian.wolff@kdab.com>
// SPDX-License-Identifier: LicenseRef-Qt-Commercial OR LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only

"use strict";

var QWebChannelMessageTypes = {
    signal: 1,
    propertyUpdate: 2,
    init: 3,
    idle: 4,
    debug: 5,
    invokeMethod: 6,
    connectToSignal: 7,
    disconnectFromSignal: 8,
    setProperty: 9,
    response: 10,
};

var QWebChannel = function(transport, initCallback, converters)
{
    if (typeof transport !== "object" || typeof transport.send !== "function") {
        console.error("The QWebChannel expects a transport object with a send function and onmessage callback property." +
                      " Given is: transport: " + typeof(transport) + ", transport.send: " + typeof(transport.send));
        return;
    }

    var channel = this;
    this.transport = transport;

    var converterRegistry =
    {
        Date : function(response) {
            if (typeof response === "string"
                && response.match(
                        /^-?\\d+-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d*)?([-+\u2212](\\d{2}):(\\d{2})|Z)?$/)) {
                var date = new Date(response);
                if (!isNaN(date))
                    return date;
            }
            return undefined;
        }
    };

    this.usedConverters = [];

    this.addConverter = function(converter)
    {
        if (typeof converter === "string") {
            if (converterRegistry.hasOwnProperty(converter))
                this.usedConverters.push(converterRegistry[converter]);
            else
                console.error("Converter '" + converter + "' not found");
        } else if (typeof converter === "function") {
            this.usedConverters.push(converter);
        } else {
            console.error("Invalid converter object type " + typeof converter);
        }
    }

    if (Array.isArray(converters)) {
        for (const converter of converters)
            this.addConverter(converter);
    } else if (converters !== undefined) {
        this.addConverter(converters);
    }

    this.send = function(data)
    {
        if (typeof(data) !== "string") {
            data = JSON.stringify(data);
        }
        channel.transport.send(data);
    }

    this.transport.onmessage = function(message)
    {
        var data = message.data;
        if (typeof data === "string") {
            data = JSON.parse(data);
        }
        switch (data.type) {
            case QWebChannelMessageTypes.signal:
                channel.handleSignal(data);
                break;
            case QWebChannelMessageTypes.response:
                channel.handleResponse(data);
                break;
            case QWebChannelMessageTypes.propertyUpdate:
                channel.handlePropertyUpdate(data);
                break;
            default:
                console.error("invalid message received:", message.data);
                break;
        }
    }

    this.execCallbacks = {};
    this.execId = 0;
    this.exec = function(data, callback)
    {
        if (!callback) {
            channel.send(data);
            return;
        }
        if (channel.execId === Number.MAX_VALUE) {
            channel.execId = Number.MIN_VALUE;
        }
        if (data.hasOwnProperty("id")) {
            console.error("Cannot exec message with property id: " + JSON.stringify(data));
            return;
        }
        data.id = channel.execId++;
        channel.execCallbacks[data.id] = callback;
        channel.send(data);
    };

    this.objects = {};

    this.handleSignal = function(message)
    {
        var object = channel.objects[message.object];
        if (object) {
            object.signalEmitted(message.signal, message.args);
        } else {
            console.warn("Unhandled signal: " + message.object + "::" + message.signal);
        }
    }

    this.handleResponse = function(message)
    {
        if (!message.hasOwnProperty("id")) {
            console.error("Invalid response message received: ", JSON.stringify(message));
            return;
        }
        channel.execCallbacks[message.id](message.data);
        delete channel.execCallbacks[message.id];
    }

    this.handlePropertyUpdate = function(message)
    {
        message.data.forEach(data => {
            var object = channel.objects[data.object];
            if (object) {
                object.propertyUpdate(data.signals, data.properties);
            } else {
                console.warn("Unhandled property update: " + data.object + "::" + data.signal);
            }
        });
        channel.exec({type: QWebChannelMessageTypes.idle});
    }

    this.debug = function(message)
    {
        channel.send({type: QWebChannelMessageTypes.debug, data: message});
    };

    channel.exec({type: QWebChannelMessageTypes.init}, function(data) {
        for (const objectName of Object.keys(data)) {
            new QObject(objectName, data[objectName], channel);
        }

        for (const objectName of Object.keys(channel.objects)) {
            channel.objects[objectName].unwrapProperties();
        }

        if (initCallback) {
            initCallback(channel);
        }
        channel.exec({type: QWebChannelMessageTypes.idle});
    });
};

function QObject(name, data, webChannel)
{
    this.__id__ = name;
    webChannel.objects[name] = this;

    this.__objectSignals__ = {};
    this.__propertyCache__ = {};

    var object = this;

    this.unwrapQObject = function(response)
    {
        for (const converter of webChannel.usedConverters) {
            var result = converter(response);
            if (result !== undefined)
                return result;
        }

        if (response instanceof Array) {
            return response.map(qobj => object.unwrapQObject(qobj))
        }
        if (!(response instanceof Object))
            return response;

        if (!response["__QObject*__"] || response.id === undefined) {
            var jObj = {};
            for (const propName of Object.keys(response)) {
                jObj[propName] = object.unwrapQObject(response[propName]);
            }
            return jObj;
        }

        var objectId = response.id;
        if (webChannel.objects[objectId])
            return webChannel.objects[objectId];

        if (!response.data) {
            console.error("Cannot unwrap unknown QObject " + objectId + " without data.");
            return;
        }

        var qObject = new QObject( objectId, response.data, webChannel );
        qObject.destroyed.connect(function() {
            if (webChannel.objects[objectId] === qObject) {
                delete webChannel.objects[objectId];
                Object.keys(qObject).forEach(name => delete qObject[name]);
            }
        });
        qObject.unwrapProperties();
        return qObject;
    }

    this.unwrapProperties = function()
    {
        for (const propertyIdx of Object.keys(object.__propertyCache__)) {
            object.__propertyCache__[propertyIdx] = object.unwrapQObject(object.__propertyCache__[propertyIdx]);
        }
    }

    function addSignal(signalData, isPropertyNotifySignal)
    {
        var signalName = signalData[0];
        var signalIndex = signalData[1];
        object[signalName] = {
            connect: function(callback) {
                if (typeof(callback) !== "function") {
                    console.error("Bad callback given to connect to signal " + signalName);
                    return;
                }

                object.__objectSignals__[signalIndex] = object.__objectSignals__[signalIndex] || [];
                object.__objectSignals__[signalIndex].push(callback);

                if (isPropertyNotifySignal)
                    return;

                if (signalName === "destroyed" || signalName === "destroyed()" || signalName === "destroyed(QObject*)")
                    return;

                if (object.__objectSignals__[signalIndex].length == 1) {
                    webChannel.exec({
                        type: QWebChannelMessageTypes.connectToSignal,
                        object: object.__id__,
                        signal: signalIndex
                    });
                }
            },
            disconnect: function(callback) {
                if (typeof(callback) !== "function") {
                    console.error("Bad callback given to disconnect from signal " + signalName);
                    return;
                }
                object.__objectSignals__[signalIndex] = (object.__objectSignals__[signalIndex] || []).filter(function(c) {
                  return c != callback;
                });
                if (!isPropertyNotifySignal && object.__objectSignals__[signalIndex].length === 0) {
                    webChannel.exec({
                        type: QWebChannelMessageTypes.disconnectFromSignal,
                        object: object.__id__,
                        signal: signalIndex
                    });
                }
            }
        };
    }

    function invokeSignalCallbacks(signalName, signalArgs)
    {
        var connections = object.__objectSignals__[signalName];
        if (connections) {
            connections.forEach(function(callback) {
                callback.apply(callback, signalArgs);
            });
        }
    }

    this.propertyUpdate = function(signals, propertyMap)
    {
        for (const propertyIndex of Object.keys(propertyMap)) {
            var propertyValue = propertyMap[propertyIndex];
            object.__propertyCache__[propertyIndex] = this.unwrapQObject(propertyValue);
        }

        for (const signalName of Object.keys(signals)) {
            invokeSignalCallbacks(signalName, signals[signalName]);
        }
    }

    this.signalEmitted = function(signalName, signalArgs)
    {
        invokeSignalCallbacks(signalName, this.unwrapQObject(signalArgs));
    }

    function addMethod(methodData)
    {
        var methodName = methodData[0];
        var methodIdx = methodData[1];
        var invokedMethod = methodName[methodName.length - 1] === ')' ? methodIdx : methodName

        object[methodName] = function() {
            var args = [];
            var callback;
            var errCallback;
            for (var i = 0; i < arguments.length; ++i) {
                var argument = arguments[i];
                if (typeof argument === "function")
                    callback = argument;
                else
                    args.push(argument);
            }

            var result;
            if (!callback && (typeof(Promise) === 'function')) {
              result = new Promise(function(resolve, reject) {
                callback = resolve;
                errCallback = reject;
              });
            }

            webChannel.exec({
                "type": QWebChannelMessageTypes.invokeMethod,
                "object": object.__id__,
                "method": invokedMethod,
                "args": args
            }, function(response) {
                if (response !== undefined) {
                    var result = object.unwrapQObject(response);
                    if (callback) {
                        (callback)(result);
                    }
                } else if (errCallback) {
                  (errCallback)();
                }
            });

            return result;
        };
    }

    function bindGetterSetter(propertyInfo)
    {
        var propertyIndex = propertyInfo[0];
        var propertyName = propertyInfo[1];
        var notifySignalData = propertyInfo[2];
        object.__propertyCache__[propertyIndex] = propertyInfo[3];

        if (notifySignalData) {
            if (notifySignalData[0] === 1) {
                notifySignalData[0] = propertyName + "Changed";
            }
            addSignal(notifySignalData, true);
        }

        Object.defineProperty(object, propertyName, {
            configurable: true,
            get: function () {
                var propertyValue = object.__propertyCache__[propertyIndex];
                if (propertyValue === undefined) {
                    console.warn("Undefined value in property cache for property \"" + propertyName + "\" in object " + object.__id__);
                }
                return propertyValue;
            },
            set: function(value) {
                if (value === undefined) {
                    console.warn("Property setter for " + propertyName + " called with undefined value!");
                    return;
                }
                object.__propertyCache__[propertyIndex] = value;
                var valueToSend = value;
                webChannel.exec({
                    "type": QWebChannelMessageTypes.setProperty,
                    "object": object.__id__,
                    "property": propertyIndex,
                    "value": valueToSend
                });
            }
        });
    }

    data.methods.forEach(addMethod);
    data.properties.forEach(bindGetterSetter);
    data.signals.forEach(function(signal) { addSignal(signal, false); });
    Object.assign(object, data.enums);
}

QObject.prototype.toJSON = function() {
    if (this.__id__ === undefined) return {};
    return {
        id: this.__id__,
        "__QObject*__": true
    };
};

if (typeof module === 'object') {
    module.exports = {
        QWebChannel: QWebChannel
    };
}
"""

# --------------------------------------------------------------------------- #
# Per-page JavaScript that talks to the Python backend through QWebChannel.
# --------------------------------------------------------------------------- #
_SPECTRUM_JS = """
console.log('[JS] spectrum page script run via runJavaScript');
var _demoTitle = document.querySelector('.page-title');
var _info = document.querySelector('.status-left');
if (_demoTitle) _demoTitle.textContent = 'DEMO Spectrum Page';
if (typeof qt === 'undefined' || !qt.webChannelTransport) {
    console.error('[JS] qt.webChannelTransport is not available');
    if (_info) _info.textContent = 'Error: qt transport not available';
} else {
    try {
        new QWebChannel(qt.webChannelTransport, function(channel) {
            console.log('[JS] QWebChannel initialized');
            if (!channel.objects.backend) {
                if (_info) _info.textContent = 'Error: backend object not found';
                return;
            }
            channel.objects.backend.get_spectra(function(json) {
                console.log('[JS] get_spectra callback, json length=' + json.length);
                var spectra = JSON.parse(json);
                renderSpectra(spectra);
                logStatus('Loaded ' + spectra.length + ' spectra from Python backend');
            });
        });
    } catch (e) {
        if (_info) _info.textContent = 'QWebChannel error: ' + e.message;
        console.error('[JS] QWebChannel error:', e);
    }
}

function renderSpectra(spectra) {
    var tbody = document.querySelector('.spectrum-table tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    spectra.forEach(function(s) {
        var tr = document.createElement('tr');
        tr.innerHTML = [
            '<td><input type="checkbox" class="row-checkbox" /></td>',
            '<td class="row-name">' + escapeHtml(s.name) + '</td>',
            '<td><span class="row-badge badge-' + badgeClass(s.category) + '">' + escapeHtml(s.category) + '</span></td>',
            '<td><span class="channel-tag channel-' + (s.channel || '-').toLowerCase() + '">' + escapeHtml(s.channel) + '</span></td>',
            '<td class="row-value">' + formatValue(s.peak) + '</td>',
            '<td class="row-value">' + formatValue(s.fwhm) + '</td>',
            '<td class="row-value">' + formatValue(s.thickness) + '</td>'
        ].join('');
        tbody.appendChild(tr);
    });

    var countLabel = document.querySelector('.panel-count');
    if (countLabel) countLabel.textContent = spectra.length + ' spectra • 0 selected';

    var statusItems = document.querySelectorAll('.status-right .status-item');
    if (statusItems.length >= 1) statusItems[0].textContent = 'Total: ' + spectra.length + ' spectra';
    if (statusItems.length >= 2) statusItems[1].textContent = 'Selected: 0';
}

function badgeClass(category) {
    var c = (category || 'unknown').toLowerCase();
    if (c === 'led') return 'led';
    if (c === 'cf') return 'cf';
    if (c === 'qd') return 'qd';
    return 'unknown';
}
"""

_GAMUT_JS = """
document.addEventListener('DOMContentLoaded', function() {
    new QWebChannel(qt.webChannelTransport, function(channel) {
        channel.objects.backend.get_gamut_data(function(json) {
            var data = JSON.parse(json);
            populateSpectrumSelectors(data.spectra);
            updateGamutResults(data.results);
            logStatus('Gamut data loaded from Python backend');
        });
    });
});

function populateSpectrumSelectors(spectra) {
    var selects = document.querySelectorAll('.spectrum-select');
    selects.forEach(function(select) {
        var current = select.value;
        select.innerHTML = '<option>-- Select --</option>';
        spectra.forEach(function(s) {
            var opt = document.createElement('option');
            opt.value = s.id;
            opt.textContent = s.name;
            select.appendChild(opt);
        });
        if (current) select.value = current;
    });
}

function updateGamutResults(results) {
    if (!results || !results.rows) return;
    var tbody = document.querySelector('.gamut-section .gamut-table tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    results.rows.forEach(function(r) {
        var tr = document.createElement('tr');
        tr.innerHTML = '<td>' + escapeHtml(r.standard) + '</td>' +
            '<td class="gamut-value ' + scoreClass(r.coverage) + '">' + formatValue(r.coverage) + '</td>' +
            '<td class="gamut-value ' + scoreClass(r.match) + '">' + formatValue(r.match) + '</td>';
        tbody.appendChild(tr);
    });
}

function scoreClass(v) {
    if (v === null || v === undefined) return '';
    if (v >= 95) return 'gamut-high';
    if (v >= 80) return 'gamut-medium';
    return 'gamut-low';
}
"""

_WHITE_POINT_JS = """
document.addEventListener('DOMContentLoaded', function() {
    new QWebChannel(qt.webChannelTransport, function(channel) {
        channel.objects.backend.get_white_point_data(function(json) {
            var data = JSON.parse(json);
            updateQuickInfo(data);
            updateInputTable(data);
            updateGamutTable(data);
            logStatus('White point calculated by Python backend');
        });
    });
});

function updateQuickInfo(data) {
    var cards = document.querySelectorAll('.quick-info .info-value');
    if (cards.length >= 1) cards[0].textContent = formatXY(data.white_xy);
    if (cards.length >= 2) cards[1].textContent = formatXY(data.white_uv);
    if (cards.length >= 3) cards[2].innerHTML = data.cct + '<span class="info-unit">K</span>';
    if (cards.length >= 4) cards[3].textContent = data.ratio;
}

function updateInputTable(data) {
    var rows = document.querySelectorAll('.input-table tbody tr');
    var channels = data.channels || [];
    rows.forEach(function(row, idx) {
        var ch = channels[idx];
        if (!ch) return;
        var cells = row.querySelectorAll('.output-value, .input-field');
        if (cells.length >= 2) cells[0].textContent = formatValue(ch.x);
        if (cells.length >= 3) cells[1].textContent = formatValue(ch.y);
    });
}

function updateGamutTable(data) {
    if (!data.gamut_rows) return;
    var tbody = document.querySelector('.gamut-section .gamut-table tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    data.gamut_rows.forEach(function(r) {
        var tr = document.createElement('tr');
        tr.innerHTML = '<td style="color:#888;">' + escapeHtml(r.standard) + '</td>' +
            '<td class="gamut-value gamut-high">' + formatValue(r.cov1931) + '</td>' +
            '<td class="gamut-value gamut-high">' + formatValue(r.match1931) + '</td>' +
            '<td class="gamut-value gamut-high">' + formatValue(r.cov1976) + '</td>' +
            '<td class="gamut-value gamut-high">' + formatValue(r.match1976) + '</td>';
        tbody.appendChild(tr);
    });
}

function formatXY(v) {
    if (!v || v.length < 2) return '-';
    return v[0].toFixed(4) + ', ' + v[1].toFixed(4);
}
"""

_OPTIMIZER_JS = """
document.addEventListener('DOMContentLoaded', function() {
    new QWebChannel(qt.webChannelTransport, function(channel) {
        channel.objects.backend.get_optimizer_data(function(json) {
            var data = JSON.parse(json);
            populateSpectrumSelectors(data.spectra);
            renderResults(data.results);
            logStatus('Optimizer results loaded from Python backend');
        });
    });
});

function populateSpectrumSelectors(spectra) {
    var selects = document.querySelectorAll('.spectrum-select');
    selects.forEach(function(select) {
        select.innerHTML = '<option>-- Select --</option>';
        spectra.forEach(function(s) {
            var opt = document.createElement('option');
            opt.value = s.id;
            opt.textContent = s.name;
            select.appendChild(opt);
        });
    });
}

function renderResults(results) {
    if (!results || !results.rows) return;
    var tbody = document.querySelector('.result-table tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    results.rows.forEach(function(r, idx) {
        var tr = document.createElement('tr');
        if (idx === 0) tr.className = 'result-best selected';
        tr.innerHTML = '<td class="result-rank">' + (idx + 1) + '</td>' +
            '<td class="result-value">' + formatValue(r.rcf) + '</td>' +
            '<td class="result-value">' + formatValue(r.gcf) + '</td>' +
            '<td class="result-value">' + formatValue(r.bcf) + '</td>' +
            '<td class="result-value result-cov-high">' + formatValue(r.coverage) + '</td>' +
            '<td class="result-value result-cov-high">' + formatValue(r.match) + '</td>' +
            '<td class="result-value">' + escapeHtml(r.white) + '</td>';
        tbody.appendChild(tr);
    });

    var summary = document.querySelector('.progress-summary');
    if (summary && results.best) {
        summary.textContent = '\u2705 Best result: Coverage = ' + results.best.coverage +
            '% (RCF=' + results.best.rcf + '\u03bcm, GCF=' + results.best.gcf +
            '\u03bcm, BCF=' + results.best.bcf + '\u03bcm)';
    }
}
"""

_COMMON_JS = """
console.log('[JS] common script loaded');
window.onerror = function(msg, url, line) {
    console.error('[JS Global Error] ' + msg + ' at line ' + line);
};

function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatValue(v) {
    return v === null || v === undefined ? '-' : v.toString();
}

function logStatus(message) {
    var left = document.querySelector('.status-left');
    if (left) left.textContent = '\u2705 ' + message;
    console.log('[Python Bridge] ' + message);
}
"""

_PAGE_CONFIG: list[tuple[str, str, str]] = [
    ("Spectrum", "01_spectrum_page_improved.html", _SPECTRUM_JS),
    ("Gamut", "02_gamut_calculator_page_improved.html", _GAMUT_JS),
    ("White Point", "03_white_point_page_improved.html", _WHITE_POINT_JS),
    ("Thickness", "04_thickness_optimizer_page_improved.html", _OPTIMIZER_JS),
]


# --------------------------------------------------------------------------- #
# Python side
# --------------------------------------------------------------------------- #
def _make_gaussian_spectrum(center: float, fwhm: float) -> Spectrum:
    """Create a synthetic gaussian spectrum for demo purposes."""
    wavelengths = np.arange(380.0, 781.0, 1.0)
    sigma = fwhm / 2.355
    values = np.exp(-0.5 * ((wavelengths - center) / sigma) ** 2)
    return Spectrum(wavelengths=wavelengths, values=values)


class Backend(QObject):
    """Backend object exposed to all web pages via QWebChannel."""

    def __init__(
        self,
        spectrum_controller: SpectrumController,
        color_controller: ColorController,
        optimization_controller: OptimizationController,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._spectrum_controller = spectrum_controller
        self._color_controller = color_controller
        self._optimization_controller = optimization_controller

    def _spectra_json(self) -> list[dict]:
        spectra = self._spectrum_controller.list_spectra()
        return [
            {
                "id": s.id,
                "name": s.name,
                "category": s.category or "-",
                "channel": s.channel or "-",
                "peak": None if s.peak_wavelength is None else round(float(s.peak_wavelength), 1),
                "fwhm": None if s.fwhm is None else round(float(s.fwhm), 1),
                "thickness": None if s.thickness_um is None else round(float(s.thickness_um), 2),
            }
            for s in spectra
        ]

    @Slot(result=str)
    def get_spectra(self) -> str:
        """Return the current project's spectra as a JSON string."""
        print("[Python Backend] get_spectra() called")
        return json.dumps(self._spectra_json())

    @Slot(result=str)
    def get_gamut_data(self) -> str:
        """Return spectra list and a simple gamut comparison."""
        print("[Python Backend] get_gamut_data() called")
        spectra = self._spectra_json()
        result: dict = {"spectra": spectra, "results": {"rows": []}}
        specs = self._spectrum_controller.list_spectra()
        if len(specs) >= 3:
            full_specs = [self._spectrum_controller.get_spectrum(s.id) for s in specs[:3]]
            full_specs = [s for s in full_specs if s is not None]
            if len(full_specs) == 3:
                rows = []
                for std in ("sRGB", "NTSC", "DCI-P3", "BT2020"):
                    metric = self._color_controller.project_gamut_coverage(std, full_specs)
                    rows.append(
                        {
                            "standard": std,
                            "coverage": round(metric["coverage"] * 100, 1) if metric else None,
                            "match": round(metric["match"] * 100, 1) if metric else None,
                        }
                    )
                result["results"] = {"rows": rows}
        return json.dumps(result)

    @Slot(result=str)
    def get_white_point_data(self) -> str:
        """Return white-point data computed from the first three RGB spectra."""
        print("[Python Backend] get_white_point_data() called")
        specs = self._spectrum_controller.list_spectra()
        data: dict = {
            "white_xy": [0.3127, 0.3290],
            "white_uv": [0.1978, 0.4683],
            "cct": 6504,
            "ratio": "0.333 : 0.333 : 0.333",
            "channels": [],
            "gamut_rows": [],
        }
        full_specs = [self._spectrum_controller.get_spectrum(s.id) for s in specs[:3]]
        full_specs = [s for s in full_specs if s is not None]
        if len(full_specs) == 3:
            mix = self._color_controller.mix_spectra(full_specs, weights=[1.0, 1.0, 1.0])
            if mix is not None:
                data["white_xy"] = [round(mix.xy.x, 4), round(mix.xy.y, 4)]
                data["cct"] = self._estimate_cct(mix.xy)
            xy_values = []
            for s in full_specs:
                xy = self._color_controller.xy(s)
                xy_values.append(xy)
                data["channels"].append(
                    {"x": round(xy.x, 4), "y": round(xy.y, 4)}
                )
            if len(xy_values) == 3:
                data["white_uv"] = self._xy_to_uv(data["white_xy"][0], data["white_xy"][1])
                for std in ("sRGB", "NTSC", "DCI-P3", "BT2020"):
                    metric = self._color_controller.project_gamut_coverage(std, full_specs)
                    data["gamut_rows"].append(
                        {
                            "standard": std,
                            "cov1931": round(metric["coverage"] * 100, 1) if metric else None,
                            "match1931": round(metric["match"] * 100, 1) if metric else None,
                            "cov1976": round(metric["coverage"] * 100, 1) if metric else None,
                            "match1976": round(metric["match"] * 100, 1) if metric else None,
                        }
                    )
        return json.dumps(data)

    @Slot(result=str)
    def get_optimizer_data(self) -> str:
        """Return simulated optimization results and the spectra list."""
        print("[Python Backend] get_optimizer_data() called")
        spectra = self._spectra_json()
        rows = [
            {"rcf": 1.20, "gcf": 0.80, "bcf": 1.50, "coverage": 95.23, "match": 92.10, "white": "(0.312, 0.329)"},
            {"rcf": 1.25, "gcf": 0.82, "bcf": 1.48, "coverage": 94.87, "match": 91.85, "white": "(0.314, 0.331)"},
            {"rcf": 1.18, "gcf": 0.78, "bcf": 1.52, "coverage": 94.52, "match": 91.60, "white": "(0.310, 0.327)"},
            {"rcf": 1.30, "gcf": 0.85, "bcf": 1.45, "coverage": 94.18, "match": 91.32, "white": "(0.316, 0.333)"},
            {"rcf": 1.15, "gcf": 0.75, "bcf": 1.55, "coverage": 93.85, "match": 91.05, "white": "(0.308, 0.325)"},
        ]
        return json.dumps({"spectra": spectra, "results": {"rows": rows, "best": rows[0]}})

    @staticmethod
    def _estimate_cct(xy) -> int:
        """Very rough CCT estimate for demo display only."""
        # Use a simple McCamy formula approximation
        n = (xy.x - 0.3320) / (xy.y - 0.1858)
        cct = int(-449 * n ** 3 + 3525 * n ** 2 - 6823.3 * n + 5520.33)
        return max(1000, min(25000, cct))

    @staticmethod
    def _xy_to_uv(x: float, y: float) -> list[float]:
        """Convert CIE 1931 xy to CIE 1976 u'v'."""
        denom = -2 * x + 12 * y + 3
        if denom == 0:
            return [0.0, 0.0]
        u = 4 * x / denom
        v = 9 * y / denom
        return [round(u, 4), round(v, 4)]


class DemoWindow(QWidget):
    """Demo window with sidebar navigation and a QWebEngineView page area."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ColorLab Pro — QWebEngineView Multi-Page Demo")
        self.resize(1600, 950)

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # -- Sidebar --
        sidebar = QWidget()
        sidebar.setFixedWidth(180)
        sidebar.setStyleSheet("background: #252526; border-right: 1px solid #444;")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(8, 12, 8, 12)
        sidebar_layout.setSpacing(6)

        self._buttons: list[QPushButton] = []
        for idx, (label, _html, _js) in enumerate(_PAGE_CONFIG):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding: 10px 12px;
                    background: transparent;
                    color: #cccccc;
                    border: none;
                    border-radius: 4px;
                    font-size: 13px;
                }
                QPushButton:hover { background: #3c3c3c; }
                QPushButton:checked { background: #0078d4; color: white; }
            """)
            btn.clicked.connect(lambda checked, i=idx: self._switch_page(i))
            sidebar_layout.addWidget(btn)
            self._buttons.append(btn)
        sidebar_layout.addStretch()
        root_layout.addWidget(sidebar)

        # -- Web view area --
        self._view = QWebEngineView()
        root_layout.addWidget(self._view, 1)

        # -- Application backend --
        self._main = MainController()
        self._main.initialize()
        project_ctrl = ProjectController(self._main)
        pid = project_ctrl.create_project("Web Demo Project")
        if pid is not None:
            self._main.set_current_project(pid)

        self._spectrum_controller = SpectrumController(self._main)
        self._color_controller = ColorController(self._main)
        self._optimization_controller = OptimizationController(self._main)
        self._seed_data()

        # -- Shared QWebChannel --
        self._channel = QWebChannel()
        self._backend = Backend(
            self._spectrum_controller,
            self._color_controller,
            self._optimization_controller,
            parent=self,
        )
        self._channel.registerObject("backend", self._backend)
        self._view.page().setWebChannel(self._channel)

        # -- Build temp HTML files for each page --
        self._page_paths: list[Path] = []
        self._page_scripts: list[str] = []
        for _label, html_name, js_code in _PAGE_CONFIG:
            self._page_paths.append(self._build_page_html(html_name))
            self._page_scripts.append(js_code + "\n" + _COMMON_JS)

        self._current_index = -1
        self._auto_index = 0
        self._view.loadFinished.connect(self._on_load_finished)
        self._switch_page(0)

    def _on_load_finished(self, ok: bool) -> None:
        """Run page JS after the page (and qrc qwebchannel.js) has loaded."""
        print(f"[Demo] page loadFinished: ok={ok}")
        if 0 <= self._current_index < len(self._page_scripts):
            self._view.page().runJavaScript(self._page_scripts[self._current_index])
        QTimer.singleShot(2000, self._save_screenshot)

    def _save_screenshot(self) -> None:
        """Save a screenshot of the current page and advance to the next one."""
        screenshot_path = ROOT / f"web_demo_page_{self._auto_index:02d}.png"
        pixmap = self._view.grab()
        if pixmap.save(str(screenshot_path)):
            print(f"[Demo] screenshot saved to {screenshot_path}")
        else:
            print("[Demo] failed to save screenshot")

        if self._auto_index < len(_PAGE_CONFIG) - 1:
            self._auto_index += 1
            QTimer.singleShot(1000, lambda: self._switch_page(self._auto_index))
        else:
            print("[Demo] all pages captured")

    def _seed_data(self) -> None:
        """Insert a few synthetic spectra into the current project."""
        specs = [
            (_make_gaussian_spectrum(630.0, 21.0), "LED_R_630nm", "R", "LED"),
            (_make_gaussian_spectrum(525.0, 32.0), "LED_G_525nm", "G", "LED"),
            (_make_gaussian_spectrum(450.0, 19.0), "LED_B_450nm", "B", "LED"),
        ]
        for spec, name, channel, category in specs:
            self._spectrum_controller.import_spectrum(
                spec, name=name, channel=channel, category=category
            )

    def _build_page_html(self, html_name: str) -> Path:
        """Copy the mockup HTML to a temp file and reference Qt's qwebchannel.js.

        Page-specific setup is executed from Python via runJavaScript after
        loadFinished to guarantee the page and transport are fully ready.
        """
        original = ROOT / "docs" / "ui_mockups" / html_name
        html = original.read_text(encoding="utf-8")
        injection = '<script src="qrc:///qtwebchannel/qwebchannel.js"></script>'
        html = html.replace("</head>", f"{injection}\n</head>")

        tmp_dir = Path(tempfile.gettempdir()) / "colorlab_pro_web_demo"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        demo_html = tmp_dir / html_name.replace(".html", "_demo.html")
        demo_html.write_text(html, encoding="utf-8")
        return demo_html

    def _switch_page(self, index: int) -> None:
        """Switch the web view to the selected page."""
        if index == self._current_index:
            return
        self._current_index = index
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == index)
        self._view.load(QUrl.fromLocalFile(str(self._page_paths[index])))

    def closeEvent(self, event) -> None:
        """Shut down the controller cleanly on window close."""
        self._main.shutdown()
        super().closeEvent(event)


def main() -> int:
    """Run the multi-page demo."""
    app = QApplication(sys.argv)
    window = DemoWindow()
    window.show()
    return int(app.exec())


if __name__ == "__main__":
    sys.exit(main())
