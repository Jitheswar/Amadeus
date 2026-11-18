# Translating Shell Plugins

Amadeus runs in 50 languages, and a plugin should follow the one picked under Setup > Language the way the built-in plugins do: live, without a shell restart. Ship the plugin's strings as flat JSON catalogs in an `i18n/` directory beside its QML, one file per Amadeus language code (`en.json`, `da.json`, `pt-BR.json`; `$AMADEUS_PATH/default/i18n/locales.json` lists all 50), and read them through `Commons.Translations`:

```qml
import qs.Commons as Commons

Item {
  Commons.Translations { id: strings; directory: Qt.resolvedUrl("i18n") }

  Text {
    textFormat: Text.PlainText
    text: strings.tn("panel.items", count).arg(Commons.I18n.formatNumber(count))
  }
}
```

```json
{ "panel.items": { "one": "%1 item", "other": "%1 items" } }
```

- A string missing from the current language falls back to its base language (`pt-BR` to `pt`), then to `en.json`, then to the key, so a plugin can ship English alone and add languages one file at a time.
- Keep each string whole with `%1` placeholders filled by `.arg()`; never glue translated fragments into a sentence, since other languages reorder words.
- A string that counts something is a plural entry, an object keyed by CLDR category, read with `strings.tn(key, count)`. English needs `one` and `other`; each translation supplies the categories its language uses (Russian `one`, `few`, `many`, `other`; Arabic six; Japanese only `other`; the rules are in `$AMADEUS_PATH/shell/Commons/Plural.js`).
- Write displayed numbers with `Commons.I18n.formatNumber(value, decimals)` so they take the language's decimal separator and digits (`13,1` in Danish).
- Arabic, Hebrew, Persian, and Urdu mirror the layout. A plugin built on `KeyboardPanel` or `PopupCard` is mirrored for free; anything it positions by explicit `x` should follow `LayoutMirroring.enabled`, glyphs that mean back or forward should swap with `Commons.I18n.rightToLeft`, and Left/Right keys should go through `Util.readingKey(event)`.
- Keep calls to `strings.t(...)` inside bindings so a language switch re-renders them. Text built once when something happens keeps the old language until it is rebuilt.
- Format dates with `Qt.locale(Commons.I18n.formatLocale)`, not `Qt.formatDate` or a bare `Qt.locale()`: those follow the locale the shell started with, which changes only when it restarts.
- Keep brand names, units, and keyboard keys as they are, and leave log and diagnostic output in English.
- Use `strings.t()` only for the plugin's own text. `Commons.I18n` holds Amadeus's catalog, which can rename or drop its keys in any update.
