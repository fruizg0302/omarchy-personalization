import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import qs.Commons

Item {
    id: root
    property var shell: null
    property var manifest: null
    property bool opened: false
    property int workspaceId: 0
    property string monitorName: ""
    property int selectedIndex: 0
    readonly property var windows: opened ? Hyprland.toplevels.values.filter(function(w) {
        return w.workspace && w.workspace.id === root.workspaceId;
    }) : []

    function open(payload) {
        var monitor = Hyprland.focusedMonitor;
        if (!monitor || !monitor.activeWorkspace) return;
        workspaceId = monitor.activeWorkspace.id;
        monitorName = monitor.name;
        selectedIndex = 0;
        opened = true;
        Qt.callLater(function() { keys.forceActiveFocus(); });
    }
    function close() { opened = false; }
    function dismiss() {
        close();
        if (shell) shell.hide("local.workspace-overview");
    }
    function choose(index) {
        var window = windows[index];
        if (!window) return;
        var address = String(window.address);
        if (!address.startsWith("0x")) address = "0x" + address;
        if (!/^0x[0-9a-fA-F]+$/.test(address)) return;
        dismiss();
        // Let the overlay release keyboard focus before activating the window.
        Qt.callLater(function() {
            Quickshell.execDetached(["hyprctl", "dispatch", "hl.dsp.focus({ window = 'address:" + address + "' })"]);
        });
    }
    function step(delta) {
        if (windows.length) selectedIndex = (selectedIndex + delta + windows.length) % windows.length;
    }

    PanelWindow {
        id: panel
        visible: root.opened
        screen: Quickshell.screens.find(function(s) { return s.name === root.monitorName; }) || Quickshell.screens[0]
        anchors { top: true; bottom: true; left: true; right: true }
        color: "transparent"
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.namespace: "local-workspace-overview"
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

        Rectangle { anchors.fill: parent; color: Color.menu.scrim }
        MouseArea { anchors.fill: parent; onClicked: root.dismiss() }
        Text {
            anchors.top: parent.top; anchors.topMargin: 40
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Workspace " + root.workspaceId + "  ·  Select a window  ·  Esc to close"
            color: Color.menu.text
            font.family: Style.font.family
            font.pixelSize: Style.font.title
        }
        GridView {
            id: grid
            anchors.centerIn: parent
            readonly property int columns: Math.max(1, Math.min(3, root.windows.length))
            width: Math.min(parent.width - 120, columns * 500)
            height: Math.min(parent.height - 180, Math.max(1, Math.ceil(root.windows.length / columns)) * 330)
            cellWidth: width / columns
            cellHeight: Math.min(300, height / Math.max(1, Math.min(2, Math.ceil(root.windows.length / columns))))
            model: root.windows
            clip: true
            currentIndex: root.selectedIndex
            onCurrentIndexChanged: positionViewAtIndex(currentIndex, GridView.Contain)
            delegate: Item {
                id: tile
                required property var modelData
                required property int index
                width: grid.cellWidth; height: grid.cellHeight
                Rectangle {
                    anchors.fill: parent; anchors.margins: 10
                    color: Color.menu.background
                    radius: Style.cornerRadius
                    border.width: 2
                    border.color: tile.index === root.selectedIndex ? Color.menu.text : Color.menu.border
                    Item {
                        id: previewArea
                        anchors { fill: parent; margins: 12; bottomMargin: 44 }
                        ScreencopyView {
                            id: preview
                            anchors.centerIn: parent
                            captureSource: root.opened && tile.modelData ? tile.modelData.wayland : null
                            live: false
                            paintCursor: false
                            constraintSize: Qt.size(Math.max(1, previewArea.width), Math.max(1, previewArea.height))
                        }
                        Text {
                            anchors.centerIn: parent
                            visible: !preview.hasContent
                            text: "Preview unavailable"
                            color: Color.menu.text
                            font.family: Style.font.family
                        }
                    }
                    Text {
                        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 12 }
                        text: tile.modelData ? tile.modelData.title : ""
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        color: Color.menu.text
                        font.family: Style.font.family
                        font.pixelSize: Style.font.body
                    }
                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        onEntered: root.selectedIndex = tile.index
                        onClicked: root.choose(tile.index)
                    }
                }
            }
        }
        Text {
            anchors.centerIn: parent
            visible: root.windows.length === 0
            text: "No windows in this workspace"
            color: Color.menu.text
            font.family: Style.font.family
        }
        Item {
            id: keys
            focus: true
            Keys.onPressed: function(event) {
                if (event.key === Qt.Key_Escape) root.dismiss();
                else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) root.choose(root.selectedIndex);
                else if (event.key === Qt.Key_Right || event.key === Qt.Key_Tab) root.step(1);
                else if (event.key === Qt.Key_Left || event.key === Qt.Key_Backtab) root.step(-1);
                else if (event.key === Qt.Key_Down) root.step(grid.columns);
                else if (event.key === Qt.Key_Up) root.step(-grid.columns);
                else return;
                event.accepted = true;
            }
        }
    }
}
