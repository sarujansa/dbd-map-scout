// ==UserScript==
// @name         DbD Map Scout – match export
// @namespace    dbd-map-scout
// @version      1
// @description  Saves the recent match history of stats.deadbydaylight.com as dbdmapscout-matches.json (download folder) for DbD Map Scout. Only match data (time, map, role, character, status) – no account or login data. Sends nothing anywhere.
// @match        https://stats.deadbydaylight.com/*
// @run-at       document-start
// @grant        none
// @noframes
// ==/UserScript==

// Part of DbD Map Scout (dbdmapscout/matchexport.user.js). The program reads the file, deletes it and
// ties the matches to its own rounds (dbdmapscout/official.py). This script makes no requests of its
// own: it only reads the answer the page itself loads (the same request "DBD Detailed Match History"
// reads) and saves a reduced copy once per page load, only when it holds a match not saved before.
(function () {
    'use strict';

    const SCRIPT_VERSION = 1;
    const FORMAT = 'dbdmapscout-matches';
    const FILE_NAME = 'dbdmapscout-matches.json';
    const API = /\/player-stats\/match-history\/games\/dbd\//;
    const LAST_KEY = 'dbdmapscout.newestSaved';

    const collected = new Map();          // start time -> reduced match
    let saveTimer = null;

    function text(v) {
        return typeof v === 'string' ? v : '';
    }

    function num(v) {
        return typeof v === 'number' && isFinite(v) ? v : null;
    }

    // status object -> its plain fields and the picture path (nothing else)
    function status(o) {
        if (!o || typeof o !== 'object') return null;
        const out = {};
        for (const [k, v] of Object.entries(o)) {
            if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') out[k] = v;
        }
        if (o.image && typeof o.image.path === 'string') out.image = o.image.path;
        return out;
    }

    function player(p, own) {
        if (!p || typeof p !== 'object') return null;
        const out = {
            role: text(p.playerRole),
            character: text(p.characterName && p.characterName.name),
            status: status(p.playerStatus),
        };
        if (own) {
            out.seconds = num(p.playerTimeInMatch);
            out.bp = num(p.bloodpointsEarned);
        }
        return out;
    }

    function reduce(m) {
        const s = m && m.matchStat;
        if (!s || num(s.matchStartTime) === null) return null;
        return {
            start: s.matchStartTime,
            map: text(s.map && s.map.name),
            custom: s.isCustomMatch === true,
            player: player(m.playerStat, true),
            opponents: Array.isArray(m.opponentStat) ? m.opponentStat.map(p => player(p, false)).filter(Boolean) : [],
        };
    }

    // wait: after the page's answer 1.5 s (it may come in parts), after the cached copy alone 10 s
    // (the fresh answer usually follows and replaces it -> one file instead of two)
    function collect(data, wait) {
        if (data && !Array.isArray(data) && Array.isArray(data.data)) data = data.data;
        if (!Array.isArray(data)) return;
        let added = 0;
        for (const m of data) {
            const r = reduce(m);
            if (r) {
                collected.set(r.start, r);
                added++;
            }
        }
        if (added) {
            clearTimeout(saveTimer);
            saveTimer = setTimeout(save, wait || 1500);
        }
    }

    function save() {
        if (!document.body) {
            document.addEventListener('DOMContentLoaded', save, { once: true });
            return;
        }
        const matches = Array.from(collected.values()).sort((a, b) => b.start - a.start);
        if (!matches.length) return;
        const newest = matches[0].start;
        let last = 0;
        try {
            last = Number(localStorage.getItem(LAST_KEY)) || 0;
        } catch (e) { /* storage blocked: save anyway */ }
        if (newest <= last) return;                   // nothing new since the last file
        const body = JSON.stringify({
            format: FORMAT, version: 1, script: SCRIPT_VERSION,
            exported: Math.floor(Date.now() / 1000), matches: matches,
        });
        const url = URL.createObjectURL(new Blob([body], { type: 'application/json' }));
        const a = document.createElement('a');
        a.href = url;
        a.download = FILE_NAME;
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 60000);
        try {
            localStorage.setItem(LAST_KEY, String(newest));
        } catch (e) { /* ignore */ }
        console.log('[DbD Map Scout] saved ' + matches.length + ' matches as ' + FILE_NAME);
    }

    function urlOf(input) {
        if (typeof input === 'string') return input;
        return (input && (input.url || input.href)) || '';
    }

    // --- read the page's own answers (fetch and XMLHttpRequest) ---
    const pageFetch = window.fetch;
    if (typeof pageFetch === 'function') {
        const patched = async function (...args) {
            const response = await pageFetch.apply(this, args);
            try {
                if (API.test(urlOf(args[0]))) {
                    response.clone().json().then(data => collect(data)).catch(() => {});
                }
            } catch (e) { /* never break the page */ }
            return response;
        };
        try {
            Object.defineProperty(window, 'fetch', { value: patched, writable: true, configurable: true });
        } catch (e) {
            try { window.fetch = patched; } catch (e2) { /* XHR and the cache below still work */ }
        }
    }

    const open = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (method, url) {
        this.__dbdmapscoutUrl = String(url || '');
        return open.apply(this, arguments);
    };
    const send = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function () {
        const xhr = this;
        if (API.test(xhr.__dbdmapscoutUrl || '')) {
            xhr.addEventListener('load', () => {
                try {
                    collect(xhr.responseType === 'json' ? xhr.response : JSON.parse(xhr.responseText));
                } catch (e) { /* not JSON */ }
            });
        }
        return send.apply(this, arguments);
    };

    // --- the page keeps the last answer in its own cache (sessionStorage) ---
    function fromCache() {
        try {
            const cache = JSON.parse(sessionStorage.getItem('REACT_QUERY_OFFLINE_CACHE') || 'null');
            const queries = (cache && cache.clientState && cache.clientState.queries) || [];
            for (const q of queries) {
                if (Array.isArray(q.queryKey) && q.queryKey[0] === 'stats.match-history' && q.state) collect(q.state.data, 10000);
            }
        } catch (e) { /* no cache */ }
    }
    fromCache();
    document.addEventListener('DOMContentLoaded', fromCache, { once: true });
})();
