from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_ShelvesConfig(object):
    def setupUi(self, ShelvesConfig):
        ShelvesConfig.setObjectName("ShelvesConfig")
        ShelvesConfig.resize(400, 400)
        self.verticalLayout = QtWidgets.QVBoxLayout(ShelvesConfig)
        self.label = QtWidgets.QLabel(ShelvesConfig)
        self.label.setText("Known shelf names:")
        self.verticalLayout.addWidget(self.label)
        self.shelfList = QtWidgets.QListWidget(ShelvesConfig)
        self.verticalLayout.addWidget(self.shelfList)
        self.addShelfButton = QtWidgets.QPushButton(ShelvesConfig)
        self.addShelfButton.setText("Add shelf")
        self.verticalLayout.addWidget(self.addShelfButton)
        self.deleteShelfButton = QtWidgets.QPushButton(ShelvesConfig)
        self.deleteShelfButton.setText("Delete selected shelf")
        self.verticalLayout.addWidget(self.deleteShelfButton)
        self.renameScriptLabel = QtWidgets.QLabel(ShelvesConfig)
        self.renameScriptLabel.setText("Rename script fragment (example):")
        self.verticalLayout.addWidget(self.renameScriptLabel)
        self.renameScriptPreview = QtWidgets.QTextEdit(ShelvesConfig)
        self.verticalLayout.addWidget(self.renameScriptPreview)
