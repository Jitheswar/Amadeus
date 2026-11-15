// Matching and ranking adapted from Omarchy MenuModel.js (MIT). See OMARCHY-LICENSE.
// Labels and aliases accept partial words; descriptions accept complete words to avoid noise.
function searchableToken(value) {
  return String(value || "").replace(/[._-]+/g, " ")
}

function leafIdFor(id) {
  var parts = String(id || "").split(".")
  return parts.length > 0 ? parts[parts.length - 1] : id
}

function nameSearchText(entry) {
  if (!entry) return ""
  var aliases = []
  var values = (Array.isArray(entry.aliases) ? entry.aliases : []).concat(Array.isArray(entry.searchTerms) ? entry.searchTerms : [])
  for (var i = 0; i < values.length; i++) aliases.push(searchableToken(values[i]))
  return [entry.label, searchableToken(leafIdFor(entry.id)), aliases.join(" ")].join(" ").toLowerCase()
}

function termInSearchWords(term, text) {
  var words = String(text || "").toLowerCase().split(/\s+/)
  for (var i = 0; i < words.length; i++) {
    if (words[i] === term) return true
  }
  return false
}

function descriptionTextMatches(query, text) {
  var terms = String(query || "").toLowerCase().trim().split(/\s+/)
  for (var i = 0; i < terms.length; i++) {
    if (terms[i] && !termInSearchWords(terms[i], text)) return false
  }
  return true
}

function matchesQuery(entry, query, visible) {
  if (!entry || entry.id === "root") return false
  if (!visible) return false

  var nameText = nameSearchText(entry)
  var descriptionText = String(entry.description || "").toLowerCase()
  var terms = String(query || "").toLowerCase().trim().split(/\s+/)

  for (var i = 0; i < terms.length; i++) {
    if (!terms[i]) continue
    if (nameText.indexOf(terms[i]) >= 0) continue
    if (termInSearchWords(terms[i], descriptionText)) continue
    return false
  }

  return true
}

function searchScore(items, entry, query) {
  var needle = String(query || "").toLowerCase().trim()
  var label = entry.label.toLowerCase()
  var nameText = nameSearchText(entry)
  var descriptionText = String(entry.description || "").toLowerCase()
  var score = 80

  if (label === needle) score = entry.parent === "root" ? 2 : 0
  // An installed app whose name contains the query as a whole word ("zen"
  // for Zen Browser) beats exact-labeled menu entries like Install > Zen.
  else if (entry.kind === "app" && label.split(/\s+/).indexOf(needle) >= 0) score = 0
  else if (label.indexOf(needle) === 0) score = 10
  else if (label.indexOf(needle) >= 0) score = 30
  else if (nameText.indexOf(needle) >= 0) score = 40
  else if (descriptionTextMatches(needle, descriptionText)) score = 60

  if (entry.kind === "menu" || entry.kind === "link") score -= 2
  // App rows sort after all menu items, so they lose the tiebreak below to an
  // equal match. Outrank those, but stay inside the tier so better ones win.
  if (entry.kind === "app") score -= 5

  return score * 1000 + (entry.depth || 0) * 25 + entry.order
}


function rows(lines, entries, query, prompt) {
  const q = String(query || "").trim()
  if (!q) return { lines: lines.slice(0, 300), info: {} }
  const local = [], remote = [], info = {}, seen = new Set(), globalSeen = new Set()
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i], label = line.split("\t")[0]
    const entry = { id: "local:" + i, label: label, aliases: [], description: "", order: i, kind: "action" }
    if (!matchesQuery(entry, q, true)) continue
    local.push({ line: line, score: searchScore({}, entry, q) })
    seen.add(label.toLowerCase())
  }
  for (let i = 0; i < entries.length; i++) {
    const value = entries[i]
    if (!value || seen.has(String(value.label).toLowerCase())) continue
    const identity = (value.label + "\t" + value.path).toLowerCase()
    if (globalSeen.has(identity)) continue
    globalSeen.add(identity)
    const entry = { id: value.id, label: value.label, aliases: [value.keywords || ""],
      description: value.description || "", order: i, kind: value.kind === "Application" ? "app" : "action",
      depth: (value.path || "").split(" › ").length }
    if (!matchesQuery(entry, q, true)) continue
    const line = value.label + "\t@global:" + value.id
    info[line] = value
    remote.push({ line: line, score: searchScore({}, entry, q) })
  }
  const sort = (a, b) => a.score - b.score || a.line.localeCompare(b.line)
  local.sort(sort); remote.sort(sort)
  return { lines: local.concat(remote).slice(0, 300).map(x => x.line), info: info }
}

if (typeof module !== "undefined") module.exports = { matchesQuery, searchScore, rows }
