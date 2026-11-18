import QtQuick 2.15

// The Amadeus login screen. #1a1b26 and #ffffff stand for the theme's background and text:
// amadeus-plymouth-set swaps them for the active theme's colours, together with the images,
// so the boot splash and this screen always match the desktop.
Rectangle {
  id: root
  width: 1920; height: 1080
  color: "#1a1b26"

  readonly property color text: "#ffffff"
  readonly property color soft: Qt.rgba(text.r, text.g, text.b, 0.62)
  readonly property color faint: Qt.rgba(text.r, text.g, text.b, 0.10)
  readonly property color failure: "#f7768e"
  readonly property real unit: Math.max(1, Math.min(width / 1920, height / 1080))

  property var users: []
  property int userIndex: 0
  property var sessions: []
  property int sessionIndex: sessionModel.lastIndex
  property bool failed: false

  // One account is preselected; with several, the last one used.
  Repeater {
    model: userModel
    delegate: Item {
      Component.onCompleted: {
        root.users = root.users.concat([{ name: model.name, label: model.realName || model.name }])
        if (model.name === userModel.lastUser) root.userIndex = root.users.length - 1
      }
    }
  }
  // The Amadeus session first, so a new account starts the desktop it was installed with.
  Repeater {
    model: sessionModel
    delegate: Item {
      Component.onCompleted: {
        root.sessions = root.sessions.concat([model.name])
        if (/amadeus/i.test(model.name) && sessionModel.lastIndex < 0) root.sessionIndex = index
      }
    }
  }
  function user() { return users.length ? users[userIndex].name : userModel.lastUser }
  function login() { failed = false; sddm.login(user(), password.text, Math.max(0, sessionIndex)) }

  Connections {
    target: sddm
    function onLoginFailed() { root.failed = true; password.text = ""; shake.start(); password.forceActiveFocus() }
  }

  Column {
    anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 48 * root.unit
    Text {
      id: clock
      anchors.right: parent.right
      color: root.text; font.pixelSize: 64 * root.unit; font.weight: Font.Light
      text: Qt.formatTime(new Date(), "HH:mm")
    }
    Text {
      id: date
      anchors.right: parent.right
      color: root.soft; font.pixelSize: 20 * root.unit
      text: Qt.formatDate(new Date(), "dddd d MMMM")
    }
    Timer { interval: 10000; running: true; repeat: true; triggeredOnStart: true
            onTriggered: { clock.text = Qt.formatTime(new Date(), "HH:mm"); date.text = Qt.formatDate(new Date(), "dddd d MMMM") } }
  }

  Column {
    anchors.centerIn: parent
    spacing: 28 * root.unit
    width: 420 * root.unit

    Image { source: "logo.png"; width: parent.width; fillMode: Image.PreserveAspectFit; smooth: true }

    Row {
      anchors.horizontalCenter: parent.horizontalCenter
      spacing: 18 * root.unit
      visible: root.users.length > 1
      Repeater {
        model: root.users
        Text {
          text: modelData.label
          color: index === root.userIndex ? root.text : root.soft
          font.pixelSize: 18 * root.unit; font.underline: index === root.userIndex
          MouseArea { anchors.fill: parent; onClicked: { root.userIndex = index; password.forceActiveFocus() } }
        }
      }
    }
    Text {
      anchors.horizontalCenter: parent.horizontalCenter
      visible: root.users.length <= 1
      text: root.users.length ? root.users[0].label : ""
      color: root.text; font.pixelSize: 20 * root.unit
    }

    Rectangle {
      id: field
      width: parent.width; height: 52 * root.unit; radius: 10 * root.unit
      color: root.faint
      border.width: 1; border.color: root.failed ? root.failure : Qt.rgba(root.text.r, root.text.g, root.text.b, 0.28)
      TextInput {
        id: password
        anchors.fill: parent; anchors.leftMargin: 18 * root.unit; anchors.rightMargin: 18 * root.unit
        verticalAlignment: TextInput.AlignVCenter
        echoMode: TextInput.Password; passwordCharacter: "•"
        color: root.text; font.pixelSize: 20 * root.unit; focus: true
        Keys.onReturnPressed: root.login()
        Keys.onEnterPressed: root.login()
        Keys.onUpPressed: if (root.users.length > 1) root.userIndex = (root.userIndex + root.users.length - 1) % root.users.length
        Keys.onDownPressed: if (root.users.length > 1) root.userIndex = (root.userIndex + 1) % root.users.length
        onTextChanged: if (text.length) root.failed = false
      }
      Text {
        anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 18 * root.unit
        visible: !password.text.length
        text: root.failed ? "Wrong password" : "Password"
        color: root.failed ? root.failure : root.soft; font.pixelSize: 18 * root.unit
      }
      SequentialAnimation {
        id: shake
        loops: 2
        NumberAnimation { target: field; property: "x"; to: 10 * root.unit; duration: 45 }
        NumberAnimation { target: field; property: "x"; to: -10 * root.unit; duration: 45 }
        NumberAnimation { target: field; property: "x"; to: 0; duration: 45 }
      }
    }
  }

  Row {
    anchors.horizontalCenter: parent.horizontalCenter
    anchors.bottom: parent.bottom; anchors.bottomMargin: 40 * root.unit
    spacing: 32 * root.unit
    Text {
      visible: root.sessions.length > 1
      text: root.sessions[Math.max(0, root.sessionIndex)] || ""
      color: root.soft; font.pixelSize: 16 * root.unit
      MouseArea { anchors.fill: parent; onClicked: root.sessionIndex = (Math.max(0, root.sessionIndex) + 1) % root.sessions.length }
    }
    Repeater {
      model: [{ label: "Suspend", can: sddm.canSuspend, act: function () { sddm.suspend() } },
              { label: "Restart", can: sddm.canReboot, act: function () { sddm.reboot() } },
              { label: "Shut down", can: sddm.canPowerOff, act: function () { sddm.powerOff() } }]
      Text {
        visible: modelData.can
        text: modelData.label
        color: root.soft; font.pixelSize: 16 * root.unit
        MouseArea { anchors.fill: parent; onClicked: modelData.act() }
      }
    }
  }
}
