# A Popup Card for a Bar Plugin

- A card that opens on click, for details that don't fit the bar, is a `PopupCard` in the widget, the way the media widget shows the playing track. It grows from the widget and fades, closes when the user clicks anywhere else (by calling the widget's `close()`), and mirrors for right-to-left languages. In the counter above, left click opens it and right click resets:

  ```qml
  property bool popupOpen: false
  function close() { popupOpen = false }

  WidgetButton {
    // ...as above, with:
    onPressed: function(mouseButton) {
      if (mouseButton === Qt.RightButton) { root.count = 0 } else { root.popupOpen = !root.popupOpen }
    }
  }

  PopupCard {
    id: popup
    anchorItem: root
    bar: root.bar
    owner: root
    open: root.popupOpen
    contentWidth: popup.fittedContentWidth(Style.space(280))
    contentHeight: popup.fittedContentHeight(column.implicitHeight)

    Column {
      id: column
      width: parent.width
      spacing: Style.space(6)

      Text {
        textFormat: Text.PlainText
        text: strings.t("title")
        color: Commons.Color.popups.text
        font.family: Style.font.family
        font.pixelSize: Style.font.subtitle
        font.bold: true
      }
      Text {
        textFormat: Text.PlainText
        text: Commons.I18n.formatNumber(root.count)
        color: Commons.Color.popups.text
        font.family: Style.font.family
        font.pixelSize: Style.font.body
      }
    }
  }
  ```

  This needs `import qs.Commons as Commons` beside `import qs.Commons`. A keyboard-driven panel that a hotkey summons is more: `$AMADEUS_PATH/shell/plugins/panels/clock/` is the reference for that, for settings from `shell.json`, and for IPC.
