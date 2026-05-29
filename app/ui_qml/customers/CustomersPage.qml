import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Rectangle {
    color: "#F5F7FA"

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 10

        Label {
            text: "Clientes (QML MVP)"
            font.pixelSize: 22
            font.bold: true
            color: "#0F172A"
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 8
            color: "#FFFFFF"
            border.color: "#E2E8F0"

            RowLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 12

                Rectangle {
                    Layout.preferredWidth: Math.max(320, parent.width * 0.35)
                    Layout.fillHeight: true
                    radius: 8
                    color: "#FFFFFF"
                    border.color: "#E2E8F0"

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 8

                        TextField {
                            id: searchField
                            Layout.fillWidth: true
                            placeholderText: "Buscar cliente..."
                            onTextChanged: customersBridge.loadCustomers(text)
                        }

                        ListView {
                            id: listView
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            model: customersBridge.customers
                            delegate: Rectangle {
                                required property var modelData
                                required property int index
                                width: listView.width
                                height: 42
                                color: ListView.isCurrentItem ? "#E0EDFF" : (ma.containsMouse ? "#F8FAFC" : "#FFFFFF")
                                border.color: "#EEF2F7"

                                MouseArea {
                                    id: ma
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onClicked: {
                                        listView.currentIndex = index
                                        customersBridge.selectCustomer(modelData.cliente_id)
                                    }
                                }

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: 8
                                    spacing: 10
                                    Label { text: modelData.codigo; Layout.preferredWidth: 40 }
                                    Label { text: modelData.nombre; elide: Text.ElideRight; Layout.fillWidth: true }
                                    Label { text: modelData.isla; color: "#64748B"; Layout.preferredWidth: 70; horizontalAlignment: Text.AlignRight }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 8
                    color: "#FFFFFF"
                    border.color: "#E2E8F0"

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 8
                        Label {
                            text: "Detalle de cliente"
                            font.pixelSize: 20
                            font.bold: true
                            color: "#111827"
                        }
                        GridLayout {
                            columns: 2
                            columnSpacing: 12
                            rowSpacing: 8
                            Label { text: "Código"; color: "#475569" }
                            TextField { Layout.fillWidth: true; readOnly: true; text: customersBridge.selectedCustomer.codigo || "" }
                            Label { text: "Nombre Comercial"; color: "#475569" }
                            TextField { Layout.fillWidth: true; readOnly: true; text: customersBridge.selectedCustomer.nombre || "" }
                            Label { text: "Teléfono"; color: "#475569" }
                            TextField { Layout.fillWidth: true; readOnly: true; text: customersBridge.selectedCustomer.telefono || "" }
                            Label { text: "C.I.F."; color: "#475569" }
                            TextField { Layout.fillWidth: true; readOnly: true; text: customersBridge.selectedCustomer.cif || "" }
                            Label { text: "Isla"; color: "#475569" }
                            TextField { Layout.fillWidth: true; readOnly: true; text: customersBridge.selectedCustomer.isla || "" }
                        }
                        Label {
                            visible: customersBridge.errorMessage.length > 0
                            text: customersBridge.errorMessage
                            color: "#B42318"
                            wrapMode: Text.WordWrap
                        }
                        Item { Layout.fillHeight: true }
                    }
                }
            }
        }
    }
}
