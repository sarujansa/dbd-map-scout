// ==UserScript==
// @name         DbD Map Scout – match export
// @namespace    dbd-map-scout
// @version      3
// @description  Saves the recent match history of stats.deadbydaylight.com as dbdmapscout-matches.json (download folder) for DbD Map Scout. Only match data (time, map, mode, role, character, status, your own loadout, emblems and score) – no account or login data, nothing about other players but character and status. Sends nothing anywhere. On request (DbD Map Scout opens the page with #dbdmapscout-structure) once the structure of the page's answer: field names and types, no values.
// @match        https://stats.deadbydaylight.com/*
// @run-at       document-start
// @grant        none
// @noframes
// ==/UserScript==

// Part of DbD Map Scout (dbdmapscout/matchexport.user.js). The program reads the file, deletes it and
// ties the matches to its own rounds (dbdmapscout/official.py). This script makes no requests of its
// own: it only reads the answer the page itself loads (the same request "DBD Detailed Match History"
// reads) and saves a reduced copy once per page load, only when it holds a match not saved before.
// Version 2 (DbD Map Scout 1.8.46): on request also the structure of that answer – which fields the page
// sends, as names and types without any value – so the user can decide whether more fields are worth taking.
// Version 3 (1.8.48, the user's pick from that structure): the match's mode, event, map id and length, and of the
// own player only: loadout (perks, add-ons, offering, power/item), emblems, score categories, prestige, level and
// the killer result – never more of the other players than before (character, role, status).
(function () {
    'use strict';

    const SCRIPT_VERSION = 3;
    const FORMAT = 'dbdmapscout-matches';
    const FILE_NAME = 'dbdmapscout-matches.json';
    const API = /\/player-stats\/match-history\/games\/dbd\//;
    const LAST_KEY = 'dbdmapscout.newestSaved';

    const STRUCTURE_FORMAT = 'dbdmapscout-structure';
    const STRUCTURE_FILE = 'dbdmapscout-structure.json';
    const STRUCTURE_HASH = '#dbdmapscout-structure';
    const STRUCTURE_KEY = 'dbdmapscout.structureUntil';
    const STRUCTURE_WAIT_MS = 15 * 60 * 1000;   // the request survives the login (a redirect drops the hash)
    const FIELD_NAME = /^[A-Za-z_][A-Za-z0-9_]{0,40}$/;

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

    // {id, name} of a perk, add-on, offering, power, mode – no picture
    function ref(o) {
        if (!o || typeof o !== 'object') return null;
        const id = text(o.id), name = text(o.name);
        return id || name ? { id, name } : null;
    }

    function refs(list, most) {
        return Array.isArray(list) ? list.slice(0, most).map(ref).filter(Boolean) : [];
    }

    const SCORE_KEY = /^DBD_(Camper|Slasher)ScoreCat_[A-Za-z]+$/;

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
            const l = p.characterLoadout || {};
            out.loadout = { perks: refs(l.perks, 4), addons: refs(l.addOns, 2), offering: ref(l.offering),
                            power: ref(l.power) };
            out.emblems = Array.isArray(p.emblems) ? p.emblems.slice(0, 8).filter(e => e && typeof e === 'object')
                .map(e => ({ id: text(e.emblem_id), name: text(e.emblem_name), quality: text(e.emblem_quality) })) : [];
            out.score = {};
            for (const [k, v] of Object.entries(p.postGameStat || {})) {
                if (SCORE_KEY.test(k) && num(v) !== null) out.score[k] = v;
            }
            out.prestige = num(p.prestigeLevel);
            out.level = num(p.characterLevel);
            out.killerStatus = text(p.killerMatchStatus);
        }
        return out;
    }

    function reduce(m) {
        const s = m && m.matchStat;
        if (!s || num(s.matchStartTime) === null) return null;
        return {
            start: s.matchStartTime,
            map: text(s.map && s.map.name),
            mapId: text(s.map && s.map.id),
            custom: s.isCustomMatch === true,
            mode: ref(s.gameType),
            event: text(s.specialEventId),
            duration: num(s.matchDuration),
            player: player(m.playerStat, true),
            opponents: Array.isArray(m.opponentStat) ? m.opponentStat.map(p => player(p, false)).filter(Boolean) : [],
        };
    }

    // --- the structure of the answer (on request only): names and types, never a value ---
    function asked() {
        try {
            return String((window.location && window.location.hash) || '') === STRUCTURE_HASH;
        } catch (e) {
            return false;
        }
    }

    function structureWanted() {
        try {
            if (asked()) localStorage.setItem(STRUCTURE_KEY, String(Date.now() + STRUCTURE_WAIT_MS));
            return Number(localStorage.getItem(STRUCTURE_KEY)) > Date.now();
        } catch (e) {
            return asked();
        }
    }

    function merged(a, b) {
        if (a === undefined) return b;
        if (b === undefined || a === b) return a;
        if (a === 'null') return b;
        if (b === 'null') return a;
        if (Array.isArray(a) && Array.isArray(b)) return a.length ? (b.length ? [merged(a[0], b[0])] : a) : b;
        if (typeof a === 'object' && typeof b === 'object' && !Array.isArray(a) && !Array.isArray(b)) {
            const out = Object.assign({}, a);
            for (const k of Object.keys(b)) out[k] = merged(out[k], b[k]);
            return out;
        }
        if (typeof a === 'string' && typeof b === 'string') {
            return Array.from(new Set(a.split('|').concat(b.split('|')))).sort().join('|');
        }
        return 'mixed';
    }

    // a field name that is not a plain identifier (an id, a player name used as a key) never leaves the page
    function shape(v, depth) {
        if (depth > 12) return '...';
        if (v === null || v === undefined) return 'null';
        if (Array.isArray(v)) {
            let item;
            for (const x of v.slice(0, 50)) item = merged(item, shape(x, depth + 1));
            return item === undefined ? [] : [item];
        }
        if (typeof v === 'object') {
            const out = {};
            for (const [k, x] of Object.entries(v)) {
                const key = FIELD_NAME.test(k) && !/^[0-9a-f]{8,}$/i.test(k) ? k : '<key>';
                out[key] = merged(out[key], shape(x, depth + 1));
            }
            return out;
        }
        return typeof v;
    }

    function download(name, body) {
        const url = URL.createObjectURL(new Blob([body], { type: 'application/json' }));
        const a = document.createElement('a');
        a.href = url;
        a.download = name;
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 60000);
    }

    function saveStructure(data) {
        if (!document.body) {
            document.addEventListener('DOMContentLoaded', () => saveStructure(data), { once: true });
            return;
        }
        try {
            localStorage.removeItem(STRUCTURE_KEY);       // once per request
        } catch (e) { /* ignore */ }
        download(STRUCTURE_FILE, JSON.stringify({
            format: STRUCTURE_FORMAT, version: 1, script: SCRIPT_VERSION,
            exported: Math.floor(Date.now() / 1000), shape: shape(data, 0),
        }, null, 1));
        console.log('[DbD Map Scout] saved the structure of the match history as ' + STRUCTURE_FILE);
    }

    let structureDone = false;

    // wait: after the page's answer 1.5 s (it may come in parts), after the cached copy alone 10 s
    // (the fresh answer usually follows and replaces it -> one file instead of two)
    function collect(data, wait) {
        if (!structureDone && data && typeof data === 'object' && structureWanted()) {
            structureDone = true;
            saveStructure(data);
        }
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
        download(FILE_NAME, body);
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
