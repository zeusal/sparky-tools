// Hevy to SparkyFitness, in the browser.
//
// Runs the same hevy_to_sparkyfitness.py as the command line, inside Pyodide
// (Python compiled to WebAssembly), so both give identical files. The user's
// export is written to Pyodide's in-memory file system and never leaves the
// browser. Only the unit choices, your list of exercise names and the chosen
// SparkyFitness names are remembered, in this browser's storage.
(function () {
  'use strict';

  var app = document.getElementById('app');
  var PYODIDE_URL = new URL(app.getAttribute('data-pyodide'), location.href).href;
  var SCRIPT_URL = new URL(app.getAttribute('data-script'), location.href).href;
  var NAMES_URL = new URL('free-exercise-db-names.json', location.href).href;
  var STORE_KEY = 'hevy-to-sparkyfitness-converter';
  var TOOL_PATH = '/tool/hevy_to_sparkyfitness.py';
  var WORK = '/work';

  var KIND_LABELS = {
    weights: 'weight × reps',
    bodyweight: 'bodyweight',
    assisted: 'assisted',
    cardio: 'cardio',
    timed: 'timed'
  };

  // Python side of the bridge: run the converter like the command line does
  // and return what it printed. Results cross as JSON strings.
  var BRIDGE = [
    'import contextlib, csv, importlib.util, io, json, runpy, sys',
    'TOOL = "' + TOOL_PATH + '"',
    'def run_tool(argv):',
    '    out, err = io.StringIO(), io.StringIO()',
    '    code = 0',
    '    sys.argv = ["hevy_to_sparkyfitness.py"] + [str(a) for a in argv]',
    '    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):',
    '        try:',
    '            runpy.run_path(TOOL, run_name="__main__")',
    '        except SystemExit as stop:',
    '            if isinstance(stop.code, str):',
    '                err.write(stop.code + "\\n")',
    '                code = 1',
    '            elif stop.code:',
    '                code = int(stop.code)',
    '        except Exception as error:',
    '            err.write("Error: this file could not be read (%s: %s)\\n" % (type(error).__name__, error))',
    '            code = 1',
    '    return json.dumps({"code": code, "out": out.getvalue(), "err": err.getvalue()})',
    '_tool = None',
    'def tool_module():',
    '    global _tool',
    '    if _tool is None:',
    '        spec = importlib.util.spec_from_file_location("hevy_tool", TOOL)',
    '        module = importlib.util.module_from_spec(spec)',
    '        spec.loader.exec_module(module)',
    '        _tool = module',
    '    return _tool',
    'def read_table_json(path):',
    '    try:',
    '        with contextlib.redirect_stderr(io.StringIO()):',
    '            mapping, _ = tool_module().read_exercise_map(path, require_filled=False)',
    '        return json.dumps({"ok": True, "mapping": mapping})',
    '    except SystemExit as stop:',
    '        return json.dumps({"ok": False, "error": str(stop.code)})',
    'def list_json(path):',
    '    with open(path, newline="", encoding="utf-8-sig") as f:',
    '        return json.dumps(list(csv.DictReader(f)))',
    'def similar_json(names_json):',
    '    return json.dumps(tool_module().similar_names(json.loads(names_json)))'
  ].join('\n');

  function $(id) { return document.getElementById(id); }

  var els = {
    fileInput: $('file-input'), dropzone: $('dropzone'), fileStatus: $('file-status'), fileError: $('file-error'),
    dateOrder: $('date-order'), assistedPositive: $('assisted-positive'),
    namesEmpty: $('names-empty'), namesTools: $('names-tools'), namesBody: $('names-body'), namesSummary: $('names-summary'),
    userNames: $('user-names'), userNamesCount: $('user-names-count'), pasteBox: $('paste-box'),
    applySuggestions: $('apply-suggestions'), loadTableBtn: $('load-table-btn'), loadTable: $('load-table'),
    saveTable: $('save-table'), clearNames: $('clear-names'), filter: $('filter'), options: $('name-options'),
    convert: $('convert'), convertStatus: $('convert-status'), convertError: $('convert-error'),
    namesError: $('names-error'),
    result: $('result'), summary: $('summary'), download: $('download')
  };

  // ---- Remembered choices (this browser only) ----------------------------

  var saved = { weight: 'kg', distance: 'km', userNames: '', targets: {} };
  try {
    var stored = JSON.parse(localStorage.getItem(STORE_KEY) || 'null');
    if (stored && typeof stored === 'object') {
      if (stored.weight === 'kg' || stored.weight === 'lbs') saved.weight = stored.weight;
      if (stored.distance === 'km' || stored.distance === 'miles') saved.distance = stored.distance;
      if (typeof stored.userNames === 'string') saved.userNames = stored.userNames;
      if (stored.targets && typeof stored.targets === 'object') saved.targets = stored.targets;
    }
  } catch (e) { /* storage unavailable: start fresh */ }

  function persist() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(saved)); } catch (e) { /* ignore */ }
  }

  // ---- State ---------------------------------------------------------------

  var state = {
    file: null,          // { name, base, path }
    rows: [],            // { hevy, sets, last, kind, target, tr, input, hint }
    lookAlike: new Map(), // Hevy name -> rows that look like one exercise, most sets first
    byName: new Map(),   // name written to SparkyFitness -> rows written with it
    userNames: [],
    userSet: new Set(),
    userLower: new Map(),
    fedb: [],
    fedbSet: new Set(),
    candidates: [],      // { name, source, tokens }
    downloadUrl: null
  };

  // ---- Engine ---------------------------------------------------------------

  var enginePromise = null;

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var tag = document.createElement('script');
      tag.src = src;
      tag.onload = resolve;
      tag.onerror = function () { reject(new Error('Could not load ' + src)); };
      document.head.appendChild(tag);
    });
  }

  // Let the browser show a status message before Python blocks the page.
  function nextPaint() {
    return new Promise(function (resolve) {
      requestAnimationFrame(function () { setTimeout(resolve, 0); });
    });
  }

  function loadEngine() {
    if (enginePromise) return enginePromise;
    // Pyodide reports a failed download of its engine only as an unhandled
    // rejection, and a stalled one not at all; turn both into an error, so
    // the page can say so and the next try starts afresh.
    var stopWatching = function () {};
    var failed = new Promise(function (resolve, reject) {
      function onRejection(event) {
        reject(event.reason instanceof Error ? event.reason : new Error(String(event.reason)));
      }
      var timer = setTimeout(function () {
        reject(new Error('The download is taking too long'));
      }, 180000);
      window.addEventListener('unhandledrejection', onRejection);
      stopWatching = function () {
        clearTimeout(timer);
        window.removeEventListener('unhandledrejection', onRejection);
      };
    });
    enginePromise = loadScript(PYODIDE_URL).then(function () {
      return Promise.race([window.loadPyodide({ indexURL: new URL('.', PYODIDE_URL).href }), failed]);
    }).then(function (py) {
      return fetch(SCRIPT_URL).then(function (response) {
        if (!response.ok) throw new Error('Could not load the converter script (' + response.status + ')');
        return response.arrayBuffer();
      }).then(function (buffer) {
        py.FS.mkdirTree('/tool');
        py.FS.mkdirTree(WORK);
        py.FS.writeFile(TOOL_PATH, new Uint8Array(buffer));
        py.runPython(BRIDGE);
        return {
          py: py,
          run: function (args) { return JSON.parse(py.globals.get('run_tool')(args)); },
          readTable: function (path) { return JSON.parse(py.globals.get('read_table_json')(path)); },
          list: function (path) { return JSON.parse(py.globals.get('list_json')(path)); },
          similar: function (names) {
            return JSON.parse(py.globals.get('similar_json')(JSON.stringify(names)));
          }
        };
      });
    });
    enginePromise.then(function () { stopWatching(); }, function () {
      stopWatching();
      enginePromise = null;
    });
    return enginePromise;
  }

  function removeFile(py, path) {
    try { py.FS.unlink(path); } catch (e) { /* not there */ }
  }

  // ---- Suggestions ----------------------------------------------------------

  // Words that carry no meaning for matching, including the ones Free Exercise
  // DB adds to its default variation ("Barbell Bench Press - Medium Grip").
  var IGNORED_WORDS = new Set(['a', 'the', 'with', 'on', 'of', 'to', 'and', 'in',
    'medium', 'grip', 'standard', 'regular', 'normal', 'basic']);

  function plain(text) {
    return text.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  }

  function singular(w) {
    if (w.length > 4 && /(ch|sh|x|ss)es$/.test(w)) return w.slice(0, -2);
    if (w.length > 3 && /s$/.test(w) && !/ss$/.test(w)) return w.slice(0, -1);
    return w;
  }

  // A name as its words (singular), plus each pair of neighbours written as
  // one word, so "Pull Up" and "Pullups" can match. Words in brackets, where
  // Hevy puts the equipment ("Bench Press (Barbell)"), count for half.
  function words(name) {
    var list = [];
    var weight = [];
    plain(name).split(/(\([^)]*\))/).forEach(function (part) {
      var inBrackets = part.charAt(0) === '(';
      part.split(/[^a-z0-9]+/).forEach(function (w) {
        if (!w || IGNORED_WORDS.has(w)) return;
        list.push(singular(w));
        weight.push(inBrackets ? 0.5 : 1);
      });
    });
    var joined = new Set();
    for (var i = 0; i + 1 < list.length; i++) joined.add(list[i] + list[i + 1]);
    return { list: list, weight: weight, set: new Set(list), joined: joined };
  }

  // Weighted share of a's words that b also has.
  function coverage(a, b) {
    var hit = a.list.map(function (w) { return b.set.has(w) || b.joined.has(w); });
    for (var i = 0; i + 1 < a.list.length; i++) {
      if (b.set.has(a.list[i] + a.list[i + 1])) { hit[i] = true; hit[i + 1] = true; }
    }
    var total = 0;
    var found = 0;
    a.weight.forEach(function (w, i) { total += w; if (hit[i]) found += w; });
    return total ? found / total : 0;
  }

  // 1 when both names say the same. A word of the Hevy name missing from the
  // suggestion costs more than an extra word in the suggestion.
  function similarity(hevy, candidate) {
    return 0.65 * coverage(hevy, candidate) + 0.35 * coverage(candidate, hevy);
  }

  function rebuildCandidates() {
    var seen = new Set();
    var list = [];
    state.userNames.forEach(function (name) {
      if (!seen.has(name)) { seen.add(name); list.push({ name: name, source: 'yours', words: words(name) }); }
    });
    state.fedb.forEach(function (name) {
      if (!seen.has(name)) { seen.add(name); list.push({ name: name, source: 'fedb', words: words(name) }); }
    });
    state.candidates = list;
    var fragment = document.createDocumentFragment();
    list.forEach(function (c) {
      var option = document.createElement('option');
      option.value = c.name;
      fragment.appendChild(option);
    });
    els.options.textContent = '';
    els.options.appendChild(fragment);
  }

  // The closest name, only when it is clearly close. None when the Hevy name
  // already is one of the user's names, and no Free Exercise DB name when it
  // already is one of those.
  function bestSuggestion(hevyName) {
    if (state.userSet.has(hevyName)) return null;
    var fedbExact = state.fedbSet.has(hevyName);
    var target = words(hevyName);
    var best = null;
    state.candidates.forEach(function (c) {
      if (c.name === hevyName || (fedbExact && c.source === 'fedb')) return;
      var score = similarity(target, c.words) + (c.source === 'yours' ? 0.05 : 0);
      if (score >= 0.75 && (!best || score > best.score)) best = { name: c.name, source: c.source, score: score };
    });
    return best;
  }

  // ---- Exercise table ---------------------------------------------------------

  function setUserNames(text) {
    var names = text.split(/\r?\n/).map(function (n) { return n.trim(); }).filter(Boolean);
    state.userNames = Array.from(new Set(names));
    state.userSet = new Set(state.userNames);
    state.userLower = new Map();
    state.userNames.forEach(function (n) { state.userLower.set(n.toLowerCase(), n); });
    els.userNamesCount.textContent = state.userNames.length
      ? state.userNames.length + ' names in your list.' : '';
    els.applySuggestions.disabled = state.userNames.length === 0;
    rebuildCandidates();
    state.rows.forEach(function (row) { row.suggestion = bestSuggestion(row.hevy); });
    refreshHints();
  }

  function button(label, onClick) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'chip';
    b.textContent = label;
    b.addEventListener('click', onClick);
    return b;
  }

  function setTarget(row, value) {
    els.result.hidden = true; // a file made before this change is out of date
    var before = written(row);
    row.target = value.trim();
    row.input.value = row.target;
    if (row.target) saved.targets[row.hevy] = row.target; else delete saved.targets[row.hevy];
    persist();
    refreshAround(row, before);
    updateSummary();
  }

  // The name an exercise is written with: the chosen name, else its Hevy name.
  // Rows written with the same name become one exercise in SparkyFitness.
  function written(row) { return row.target || row.hevy; }

  function indexNames() {
    state.byName = new Map();
    state.rows.forEach(function (row) {
      var name = written(row);
      if (!state.byName.has(name)) state.byName.set(name, []);
      state.byName.get(name).push(row);
    });
  }

  function refreshHints() {
    indexNames();
    state.rows.forEach(updateHint);
  }

  // After one row's name changed from `before`: only the rows whose hints
  // can change (same old or new name, or names that look alike).
  function refreshAround(row, before) {
    indexNames();
    var now = written(row);
    var alike = state.lookAlike.get(row.hevy) || [];
    state.rows.forEach(function (r) {
      var name = written(r);
      if (r === row || name === before || name === now || alike.indexOf(r) !== -1) updateHint(r);
    });
  }

  function quoted(rows) {
    return rows.map(function (r) { return '“' + r.hevy + '”'; }).join(', ');
  }

  function updateHint(row) {
    var hint = row.hint;
    hint.textContent = '';
    hint.className = 'hint';
    function text(t, into) {
      var s = document.createElement('span');
      s.textContent = t;
      (into || hint).appendChild(s);
    }
    nameHint(row, hint, text);
    joinHint(row, hint, text);
  }

  // A name chosen with a button goes to every Hevy exercise written with the
  // same name, so exercises that were joined stay one.
  function renameGroup(row, value) {
    (state.byName.get(written(row)) || [row]).slice().forEach(function (r) { setTarget(r, value); });
  }

  // Which Hevy exercises become one, and which look like one but don't yet.
  // The button is on every row of a look-alike group, so the person picks
  // the name to keep by picking the row.
  function joinHint(row, hint, text) {
    var box = document.createElement('div');
    box.className = 'join';
    var name = written(row);
    var together = (state.byName.get(name) || []).filter(function (r) { return r !== row; });
    if (together.length) {
      text('Joined with ' + quoted(together) + ' from Hevy: one exercise in SparkyFitness.', box);
    }
    var apart = (state.lookAlike.get(row.hevy) || []).filter(function (r) { return written(r) !== name; });
    if (apart.length) {
      text('Looks like the same exercise as ' + apart.map(function (r) {
        return '“' + r.hevy + '”' + (r.target ? ' (written as “' + r.target + '”)' : '');
      }).join(', ') + '. ', box);
      box.appendChild(button(apart.length === 1 ? 'Use this name for “' + apart[0].hevy + '” too'
        : 'Use this name for them too', function () {
        apart.forEach(function (r) { renameGroup(r, name); });
        row.input.focus();
      }));
    }
    if (box.childNodes.length) hint.appendChild(box);
  }

  function nameHint(row, hint, text) {
    var value = row.target;

    if (!value) {
      if (state.userSet.has(row.hevy)) {
        hint.classList.add('ok');
        text('✓ Same name as one of your exercises: it will be used.');
        return;
      }
      text('Imported as “' + row.hevy + '”. ');
      if (row.suggestion) {
        hint.appendChild(button('Use “' + row.suggestion.name + '”', function () {
          renameGroup(row, row.suggestion.name);
          row.input.focus();
        }));
        text(row.suggestion.source === 'yours' ? ' from your names' : ' from Free Exercise DB');
      }
      return;
    }
    if (state.userSet.has(value)) {
      hint.classList.add('ok');
      text('✓ One of your exercises.');
    } else if (state.userLower.has(value.toLowerCase())) {
      var exact = state.userLower.get(value.toLowerCase());
      hint.classList.add('warn');
      text('Capitals differ from your exercise “' + exact + '”. ');
      hint.appendChild(button('Use “' + exact + '”', function () { renameGroup(row, exact); row.input.focus(); }));
    } else if (state.userNames.length) {
      hint.classList.add('warn');
      text('Not in your list of SparkyFitness names. Check the spelling, or it becomes a new exercise.');
    } else if ((state.byName.get(value) || []).some(function (r) { return !r.target; })) {
      text('Imported as “' + value + '”.');
    } else if (state.fedbSet.has(value)) {
      text('Free Exercise DB name.');
    } else {
      text('Must match your SparkyFitness exercise exactly, or it becomes a new exercise.');
    }
    if (row.kind === 'assisted' && !els.assistedPositive.checked) {
      text(' Assisted: the SparkyFitness exercise must be a bodyweight one.');
    }
  }

  function updateSummary() {
    var renamed = state.rows.filter(function (r) { return r.target; }).length;
    var counts = new Map();
    state.rows.forEach(function (r) { counts.set(written(r), (counts.get(written(r)) || 0) + 1); });
    var joinedRows = 0;
    var joinedInto = 0;
    counts.forEach(function (n) { if (n > 1) { joinedRows += n; joinedInto++; } });
    els.namesSummary.textContent = state.rows.length + ' exercises · ' + renamed + ' with a SparkyFitness name' +
      (joinedRows ? ' · ' + joinedRows + ' joined into ' + joinedInto : '');
  }

  function renderRows(listRows, groups) {
    state.rows = listRows.map(function (r) {
      return {
        hevy: r.hevy_name,
        sets: parseInt(r.sets, 10) || 0,
        last: r.last_done,
        kind: r.kind,
        target: (saved.targets[r.hevy_name] || '').trim()
      };
    }).sort(function (a, b) { return b.sets - a.sets || a.hevy.localeCompare(b.hevy); });

    // Names the converter finds alike, in table order (most sets first).
    var position = new Map(state.rows.map(function (r, i) { return [r.hevy, i]; }));
    state.lookAlike = new Map();
    (groups || []).forEach(function (names) {
      var members = names.filter(function (n) { return position.has(n); })
        .sort(function (a, b) { return position.get(a) - position.get(b); })
        .map(function (n) { return state.rows[position.get(n)]; });
      if (members.length > 1) members.forEach(function (r) { state.lookAlike.set(r.hevy, members); });
    });

    var fragment = document.createDocumentFragment();
    state.rows.forEach(function (row, index) {
      var tr = document.createElement('tr');
      var th = document.createElement('th');
      th.scope = 'row';
      var name = document.createElement('span');
      name.className = 'ex-name';
      name.textContent = row.hevy;
      var meta = document.createElement('span');
      meta.className = 'ex-meta';
      meta.textContent = row.sets + (row.sets === 1 ? ' set' : ' sets') + ' · last ' + row.last +
        ' · ' + (KIND_LABELS[row.kind] || row.kind);
      th.appendChild(name);
      th.appendChild(meta);
      var td = document.createElement('td');
      var input = document.createElement('input');
      input.type = 'text';
      input.id = 'target-' + index;
      input.setAttribute('list', 'name-options');
      input.setAttribute('aria-label', 'SparkyFitness name for ' + row.hevy);
      input.placeholder = 'Keep “' + row.hevy + '”';
      input.autocomplete = 'off';
      input.spellcheck = false;
      input.value = row.target;
      input.addEventListener('change', function () {
        if (input.value.trim() === row.target) {
          // Typing already updated the hints: only remember the name. Drawing
          // them again here would replace a button that is being clicked.
          input.value = row.target;
          if (row.target) saved.targets[row.hevy] = row.target; else delete saved.targets[row.hevy];
          persist();
          return;
        }
        setTarget(row, input.value);
      });
      input.addEventListener('input', function () {
        els.result.hidden = true;
        var before = written(row);
        row.target = input.value.trim();
        refreshAround(row, before);
        updateSummary();
      });
      var hint = document.createElement('div');
      hint.className = 'hint';
      hint.id = 'target-hint-' + index;
      input.setAttribute('aria-describedby', hint.id);
      td.appendChild(input);
      td.appendChild(hint);
      tr.appendChild(th);
      tr.appendChild(td);
      fragment.appendChild(tr);
      row.tr = tr;
      row.input = input;
      row.hint = hint;
      row.suggestion = bestSuggestion(row.hevy);
    });
    els.namesBody.textContent = '';
    els.namesBody.appendChild(fragment);
    refreshHints();
    els.namesEmpty.hidden = true;
    els.namesTools.hidden = false;
    applyFilter();
    updateSummary();
  }

  function applyFilter() {
    var q = plain(els.filter.value.trim());
    state.rows.forEach(function (row) {
      row.tr.hidden = !!q && plain(row.hevy).indexOf(q) < 0 && plain(row.target).indexOf(q) < 0;
    });
  }

  function csvField(value) {
    var s = String(value);
    return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }

  function tableCsv(withDetails) {
    var header = withDetails
      ? ['hevy_name', 'sparkyfitness_name', 'sets', 'last_done', 'kind']
      : ['hevy_name', 'sparkyfitness_name'];
    var lines = [header.join(',')];
    state.rows.forEach(function (row) {
      if (!withDetails && !row.target) return;
      var fields = [row.hevy, row.target];
      if (withDetails) fields.push(row.sets, row.last, row.kind);
      lines.push(fields.map(csvField).join(','));
    });
    if (withDetails) {
      // Names chosen earlier for exercises that aren't in this export stay in
      // the table, as the command line's --list-exercises keeps them.
      var inExport = new Set(state.rows.map(function (r) { return r.hevy; }));
      Object.keys(saved.targets).sort().forEach(function (hevy) {
        if (!inExport.has(hevy) && saved.targets[hevy]) {
          lines.push([hevy, saved.targets[hevy], 0, '', ''].map(csvField).join(','));
        }
      });
    }
    return lines.join('\r\n') + '\r\n';
  }

  function saveBlob(text, filename) {
    var blob = new Blob(['﻿' + text], { type: 'text/csv;charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 10000);
  }

  // ---- Errors and status -------------------------------------------------------

  function showError(box, message) {
    box.textContent = message.trim();
    box.hidden = false;
  }

  function clearError(box) {
    box.textContent = '';
    box.hidden = true;
  }

  // The converter's messages are written for the command line; say what to
  // do on this page instead.
  var WEB_WORDING = [
    [/Use the original file from Hevy, or add --date-order dmy \(or mdy\)\./g,
      'Export the file from Hevy again, or choose the date order under Advanced options in step 2.'],
    [/use --date-order dmy/g, 'choose “Day first” under Advanced options in step 2'],
    [/use --date-order mdy/g, 'choose “Month first” under Advanced options in step 2'],
    [/convert again with --assisted-positive/g,
      'tick the assistance option under Advanced options in step 2 and create the file again'],
    [/ \(create it with --list-exercises\)/g, ''],
    [/with --assisted-positive, /g, 'with the assistance option ticked, '],
    [/, or leave out --assisted-positive\./g, ', or untick the assistance option under Advanced options in step 2.'],
    [/; choose another name with -o/g, ''],
    [/give each group the same sparkyfitness_name in the exercise table and convert again\./g,
      'give each group the same SparkyFitness name in step 3 (the table can join them for you) and create the file again.'],
    [/^Error: /gm, '']
  ];

  function webify(text) {
    var result = text.replace(new RegExp(WORK + '/(in/|out/)?', 'g'), '');
    WEB_WORDING.forEach(function (pair) { result = result.replace(pair[0], pair[1]); });
    return result.trim();
  }

  function friendly(stderr) {
    var text = stderr.replace(/^usage:[\s\S]*?error: /m, '');
    if (/--date-order/.test(text)) document.querySelector('details.advanced').open = true;
    return webify(text);
  }

  // ---- Reading the export --------------------------------------------------------

  function safeName(name) {
    var cleaned = name.replace(/[\\/:*?"<>|\u0000-\u001f]/g, '_').trim();
    return cleaned || 'workout_data.csv';
  }

  function readFile(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () { resolve(new Uint8Array(reader.result)); };
      reader.onerror = function () { reject(reader.error || new Error('Could not read the file')); };
      reader.readAsArrayBuffer(file);
    });
  }

  function listExercises() {
    clearError(els.fileError);
    if (!state.file) return Promise.resolve();
    els.fileStatus.textContent = 'Reading ' + state.file.name + '…';
    return Promise.all([loadEngine(), nextPaint()]).then(function (results) {
      var engine = results[0];
      var tablePath = WORK + '/table.csv';
      removeFile(engine.py, tablePath);
      var args = [state.file.path, '--list-exercises', tablePath];
      if (els.dateOrder.value) args.push('--date-order', els.dateOrder.value);
      var result = engine.run(args);
      if (result.code !== 0) {
        els.fileStatus.textContent = '';
        state.rows = [];
        els.namesBody.textContent = '';
        els.namesTools.hidden = true;
        els.namesEmpty.hidden = false;
        els.convert.disabled = true;
        showError(els.fileError, friendly(result.err));
        return;
      }
      var rows = engine.list(tablePath);
      var groups = engine.similar(rows.map(function (r) { return r.hevy_name; }));
      var total = rows.reduce(function (n, r) { return n + (parseInt(r.sets, 10) || 0); }, 0);
      els.fileStatus.textContent = '✓ ' + state.file.name + ': ' + total + ' sets of ' + rows.length +
        ' exercises. Continue with step 2.';
      renderRows(rows, groups);
      els.convert.disabled = false;
    });
  }

  function chooseFile(file) {
    if (!file) return;
    clearError(els.fileError);
    els.result.hidden = true;
    els.convert.disabled = true;
    els.fileStatus.textContent = enginePromise ? 'Reading…'
      : 'Getting the converter ready. The first time this downloads about 6 MB and takes a few seconds…';
    Promise.all([readFile(file), loadEngine()]).then(function (results) {
      var bytes = results[0];
      var engine = results[1];
      var name = safeName(file.name);
      engine.py.FS.mkdirTree(WORK + '/in');
      var path = WORK + '/in/' + name;
      engine.py.FS.writeFile(path, bytes);
      state.file = { name: name, base: name.replace(/\.[^.]*$/, '') || name, path: path };
      return listExercises();
    }).catch(function (error) {
      els.fileStatus.textContent = '';
      showError(els.fileError, 'The converter could not start: ' + (error && error.message ? error.message : error) +
        '\n\nCheck your internet connection and reload the page. If it keeps happening, try another browser.');
    });
  }

  // ---- Converting -----------------------------------------------------------------

  function convert() {
    clearError(els.convertError);
    els.result.hidden = true;
    if (!state.file) return;
    els.convert.disabled = true;
    els.convertStatus.textContent = 'Creating the file…';
    Promise.all([loadEngine(), nextPaint()]).then(function (results) {
      var engine = results[0];
      var py = engine.py;
      var outPath = WORK + '/out/' + state.file.base + '_sparkyfitness.csv';
      py.FS.mkdirTree(WORK + '/out');
      removeFile(py, outPath);
      var weight = document.querySelector('input[name="weight"]:checked').value;
      var distance = document.querySelector('input[name="distance"]:checked').value;
      var args = [state.file.path, '--weight', weight, '--distance', distance, '-o', outPath];
      var mapPath = WORK + '/map.csv';
      removeFile(py, mapPath);
      if (state.rows.some(function (r) { return r.target; })) {
        py.FS.writeFile(mapPath, new TextEncoder().encode(tableCsv(false)));
        args.push('--exercise-map', mapPath);
      }
      if (els.dateOrder.value) args.push('--date-order', els.dateOrder.value);
      if (els.assistedPositive.checked) args.push('--assisted-positive');
      var result = engine.run(args);
      els.convertStatus.textContent = '';
      if (result.code !== 0) {
        showError(els.convertError, friendly(result.err));
        return;
      }
      var bytes = py.FS.readFile(outPath);
      if (state.downloadUrl) URL.revokeObjectURL(state.downloadUrl);
      state.downloadUrl = URL.createObjectURL(new Blob([bytes], { type: 'text/csv;charset=utf-8' }));
      var filename = state.file.base + '_sparkyfitness.csv';
      els.download.href = state.downloadUrl;
      els.download.download = filename;
      els.download.textContent = 'Download ' + filename;
      els.summary.textContent = webify(result.out);
      // Warnings are worth reading before importing.
      els.summary.closest('details').open = /^Warning:/m.test(els.summary.textContent);
      els.result.hidden = false;
      els.download.focus();
    }).catch(function (error) {
      els.convertStatus.textContent = '';
      showError(els.convertError, 'Something went wrong: ' + (error && error.message ? error.message : error));
    }).then(function () {
      els.convert.disabled = !state.file;
    });
  }

  // ---- Wiring --------------------------------------------------------------------------

  document.querySelectorAll('input[name="weight"], input[name="distance"]').forEach(function (input) {
    if (input.value === saved[input.name]) input.checked = true;
    input.addEventListener('change', function () {
      saved[input.name] = input.value;
      persist();
      els.result.hidden = true;
    });
  });

  els.fileInput.addEventListener('change', function () {
    chooseFile(els.fileInput.files && els.fileInput.files[0]);
  });
  ['dragenter', 'dragover'].forEach(function (type) {
    els.dropzone.addEventListener(type, function (event) {
      event.preventDefault();
      els.dropzone.classList.add('dragging');
    });
  });
  ['dragleave', 'drop'].forEach(function (type) {
    els.dropzone.addEventListener(type, function () { els.dropzone.classList.remove('dragging'); });
  });
  els.dropzone.addEventListener('drop', function (event) {
    event.preventDefault();
    chooseFile(event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0]);
  });

  els.dateOrder.addEventListener('change', function () {
    els.result.hidden = true;
    if (state.file) listExercises().catch(function () { /* shown already */ });
  });
  els.assistedPositive.addEventListener('change', function () {
    els.result.hidden = true;
    refreshHints();
  });

  els.userNames.value = saved.userNames;
  if (saved.userNames) els.pasteBox.open = true;
  els.userNames.addEventListener('input', function () {
    saved.userNames = els.userNames.value;
    persist();
    setUserNames(els.userNames.value);
  });

  els.applySuggestions.addEventListener('click', function () {
    var used = 0;
    state.rows.forEach(function (row) {
      // Only close matches; anything less is left for the person to choose.
      if (!row.target && row.suggestion && row.suggestion.source === 'yours' && row.suggestion.score >= 0.9) {
        used += (state.byName.get(written(row)) || [row]).length;
        renameGroup(row, row.suggestion.name);
      }
    });
    updateSummary();
    els.namesSummary.textContent += ' · ' + used + ' filled in from your names; check the rest by hand';
  });

  els.saveTable.addEventListener('click', function () {
    saveBlob(tableCsv(true), (state.file ? state.file.base : 'workout_data') + '_exercises.csv');
  });

  els.loadTableBtn.addEventListener('click', function () { els.loadTable.click(); });
  els.loadTable.addEventListener('change', function () {
    var file = els.loadTable.files && els.loadTable.files[0];
    if (!file) return;
    clearError(els.namesError);
    Promise.all([readFile(file), loadEngine()]).then(function (results) {
      var path = WORK + '/loaded_table.csv';
      results[1].py.FS.writeFile(path, results[0]);
      var loaded = results[1].readTable(path);
      if (!loaded.ok) {
        showError(els.namesError, webify(loaded.error.split(path).join(file.name)));
        return;
      }
      var known = 0;
      state.rows.forEach(function (row) {
        if (Object.prototype.hasOwnProperty.call(loaded.mapping, row.hevy)) {
          setTarget(row, loaded.mapping[row.hevy]);
          known++;
        }
      });
      // Names for exercises that aren't in this export are kept for later,
      // as the command line's --list-exercises keeps them.
      var inExport = new Set(state.rows.map(function (row) { return row.hevy; }));
      Object.keys(loaded.mapping).forEach(function (hevy) {
        if (!inExport.has(hevy)) saved.targets[hevy] = loaded.mapping[hevy];
      });
      persist();
      var unknown = Object.keys(loaded.mapping).length - known;
      updateSummary();
      els.namesSummary.textContent += ' · loaded ' + known + ' names' +
        (unknown ? ' (' + unknown + ' are not in this export)' : '');
    }).catch(function (error) {
      showError(els.namesError, 'Could not load the table: ' + (error && error.message ? error.message : error));
    }).then(function () { els.loadTable.value = ''; });
  });

  var clearArmed = null;
  els.clearNames.addEventListener('click', function () {
    if (!clearArmed) {
      els.clearNames.textContent = 'Click again to clear every name';
      clearArmed = setTimeout(function () {
        clearArmed = null;
        els.clearNames.textContent = 'Clear all names';
      }, 4000);
      return;
    }
    clearTimeout(clearArmed);
    clearArmed = null;
    els.clearNames.textContent = 'Clear all names';
    state.rows.forEach(function (row) { setTarget(row, ''); });
    saved.targets = {};
    persist();
  });

  els.filter.addEventListener('input', applyFilter);

  $('forget').addEventListener('click', function () {
    try { localStorage.removeItem(STORE_KEY); } catch (e) { /* nothing stored */ }
    saved = { weight: 'kg', distance: 'km', userNames: '', targets: {} };
    els.result.hidden = true;
    els.userNames.value = '';
    setUserNames('');
    state.rows.forEach(function (row) {
      row.target = '';
      row.input.value = '';
    });
    refreshHints();
    updateSummary();
    $('forget-status').textContent = 'Done: this page no longer remembers anything.';
  });
  els.convert.addEventListener('click', convert);

  fetch(NAMES_URL).then(function (r) { return r.ok ? r.json() : { names: [] }; }).catch(function () {
    return { names: [] };
  }).then(function (data) {
    state.fedb = Array.isArray(data.names) ? data.names : [];
    state.fedbSet = new Set(state.fedb);
    setUserNames(els.userNames.value);
  });
})();
