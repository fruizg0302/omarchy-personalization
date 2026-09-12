import QtQuick
import Quickshell
import qs.Commons
import qs.Ui

PopupWindow {
    id: tip
    required property Item target
    property string text: ""
    property string position: "bottom"
    property bool active: false
    property bool ready: false
    readonly property var targetWindow: target.QsWindow.window

    onActiveChanged: {
        ready = false
        if (active) hoverDelay.restart()
        else hoverDelay.stop()
    }
    Timer {
        id: hoverDelay
        interval: 400
        onTriggered: tip.ready = tip.active
    }
    visible: active && ready && text !== "" && targetWindow !== null
    color: "transparent"
    implicitWidth: label.implicitWidth + 20
    implicitHeight: label.implicitHeight + 14
    anchor {
        id: popupAnchor
        window: tip.targetWindow
        adjustment: PopupAdjustment.Slide
        edges: Edges.Top | Edges.Left
        gravity: Edges.Bottom | Edges.Right
        rect.width: 1
        rect.height: 1
        onAnchoring: {
            if (!tip.targetWindow) return
            var x = (tip.target.width - tip.implicitWidth) / 2
            var y = -tip.implicitHeight - 8
            if (tip.position === "top") y = tip.target.height + 8
            if (tip.position === "left" || tip.position === "right") {
                x = tip.position === "left" ? tip.target.width + 8 : -tip.implicitWidth - 8
                y = (tip.target.height - tip.implicitHeight) / 2
            }
            var point = tip.targetWindow.contentItem.mapFromItem(tip.target, x, y)
            popupAnchor.rect.x = Math.round(point.x)
            popupAnchor.rect.y = Math.round(point.y)
        }
    }
    BorderSurface {
        anchors.fill: parent
        color: Color.tooltip.background
        borderSpec: Border.surfaceSpec("tooltip", "border", Color.tooltip.border, 1)
        radius: Style.cornerRadius
        Text {
            id: label
            anchors.centerIn: parent
            text: tip.text
            textFormat: Text.PlainText
            color: Color.tooltip.text
            font.family: Style.font.family
            font.pixelSize: Style.font.body
        }
    }
}
