import sys
import os
import copy
import json
import re

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

def load_config(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config


CONFIG = load_config('config.json')
SELECT_TYPES = CONFIG['types']


class TreeNode:
    """
    文件名、总行数、非空行数、空行数
    """

    def __init__(self, path, is_file=False, parent=None):
        self._path = path
        self._is_file = is_file
        self._parent = parent
        self._children = []

        self._name = os.path.basename(path)
        self.all_lines = 0
        self.nonempty_lines = 0
        self.empty_lines = 0

    @property
    def path(self):
        return self._path

    @property
    def is_file(self):
        return self._is_file

    @property
    def parent(self):
        return self._parent

    @property
    def children(self):
        return self._children

    @property
    def name(self):
        return self._name

    def append_children(self, node):
        self._children.append(node)

    def child(self, index):
        return self._children[index]

    def child_count(self):
        return len(self._children)

    def row(self):
        return self._parent.children.index(self) if self._parent else 0

    def count_lines(self):
        if self.is_file:
            res = CodeCounterInterface.count_lines(self.path)
            self.all_lines, self.nonempty_lines, self.empty_lines = res
        else:
            self.all_lines, self.nonempty_lines, self.empty_lines = 0, 0, 0
            for child in self.children:
                self.all_lines += child.all_lines
                self.nonempty_lines += child.nonempty_lines
                self.empty_lines += child.empty_lines


class CodeCounterInterface:
    """代码计数相关接口"""

    @staticmethod
    def filter_files(entries, root_path):
        """过滤目录下的文件"""
        res = []
        for item in entries:
            item_path = os.path.join(root_path, item)
            if os.path.isdir(item_path):
                should_include = True
                for pattern in CONFIG['filter']['dir']:
                    if re.match(pattern, item):
                        should_include = False
                        break
                if should_include:
                    res.append(item)
            elif os.path.isfile(item_path):
                should_include = True
                for pattern in CONFIG['filter']['file']:
                    if re.match(pattern, item):
                        should_include = False
                        break
                if should_include:
                    for type in SELECT_TYPES:
                        if item.endswith(type['suffix']):
                            res.append(item)
                            break

        return res

    @staticmethod
    def count_lines(path):
        all_lines = 0
        nonempty_lines = 0
        empty_lines = 0

        with open(path, 'r', encoding='utf-8') as file:
            for line in file:
                all_lines += 1
                if line.strip():
                    nonempty_lines += 1
                else:
                    empty_lines += 1
        return all_lines, nonempty_lines, empty_lines


def build_tree(root_path, root_node, file_filter=None):
    entries = sorted(os.listdir(root_path), key=lambda x: os.path.isdir(os.path.join(root_path, x)), reverse=True)
    if file_filter:
        entries = file_filter(entries, root_path)
    for item in entries:
        item_path = os.path.join(root_path, item)
        if os.path.isdir(item_path):
            item_node = TreeNode(item_path, parent=root_node)
            root_node.append_children(item_node)
            build_tree(item_path, item_node, file_filter)
        else:
            item_node = TreeNode(item_path, parent=root_node, is_file=True)
            root_node.append_children(item_node)


def delete_empty_dir_node(root_node):
    if root_node.child_count() == 0 or root_node.is_file:
        return
    for node in root_node.children:
        delete_empty_dir_node(node)
    for node in copy.copy(root_node.children):
        if node.child_count() == 0 and not node.is_file:
            root_node.children.remove(node)


def exec_count_lines(root_node):
    for node in root_node.children:
        if not node.is_file:
            exec_count_lines(node)
        else:
            node.count_lines()
    root_node.count_lines()


class TreeModel(QAbstractItemModel):
    def __init__(self, root_path, is_file=False, parent=None):
        super().__init__(parent)
        self._root_path = root_path
        self._is_file = is_file
        self.init_data()

        self._headers = ("文件名", "总行数", "非空行数", "空行数")

    def init_data(self):
        root_path = self._root_path
        is_file = self._is_file
        if is_file:
            self._root_node = TreeNode(root_path, is_file=True)
            self._root_node.count_lines()
        else:
            self._root_node = TreeNode(root_path)
            build_tree(root_path, self._root_node, CodeCounterInterface.filter_files)
            delete_empty_dir_node(self._root_node)
            exec_count_lines(self._root_node)

    @property
    def root_path(self):
        return self._root_path

    @property
    def is_file(self):
        return self._is_file

    @property
    def root_node(self):
        return self._root_node

    def data(self, index, role=...):
        if not index.isValid():
            return None

        item = index.internalPointer()

        if role == Qt.DisplayRole:
            if index.column() == 0:
                return item.name
            elif index.column() == 1:
                return item.all_lines
            elif index.column() == 2:
                return item.nonempty_lines
            elif index.column() == 3:
                return item.empty_lines

    def headerData(self, section, orientation, role=...):
        if role != Qt.DisplayRole:
            return None

        if orientation == Qt.Horizontal:
            return self._headers[section]

    def parent(self, index=...):
        if not index.isValid():
            return QModelIndex()

        child_item = index.internalPointer()
        parent_item = child_item.parent

        if not parent_item:
            return QModelIndex()

        return self.createIndex(parent_item.row(), 0, parent_item)

    def index(self, row, column, parent=...):
        if not parent.isValid():
            return self.createIndex(row, column, self._root_node)

        parent_item = parent.internalPointer()
        child_item = parent_item.child(row)
        return self.createIndex(row, column, child_item)

    def rowCount(self, parent=...):
        if not parent.isValid():
            return 1

        parent_item = parent.internalPointer()
        return parent_item.child_count()

    def columnCount(self, parent=...):
        return len(self._headers)

    def flags(self, index):
        return Qt.NoItemFlags


# 类型选择界面
class TypeSelectWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        hlayout = QHBoxLayout(self)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setColumnWidth(0, 200)
        self.tree.setHeaderLabels(["类型", "文件后缀"])
        hlayout.addWidget(self.tree)
        self.root = QTreeWidgetItem(self.tree)
        self.root.setText(0, "全选")
        self.root.setCheckState(0, Qt.CheckState.Checked)
        for type in CONFIG['types']:
            item = QTreeWidgetItem(self.root, [type['name'], type['suffix']])
            item.setCheckState(0, Qt.CheckState.Checked)
        self.tree.expandAll()
        self.tree.itemChanged.connect(self.item_changed)

        self.setMinimumWidth(400)

    def get_checked_types(self):
        types = []
        for i in range(self.root.childCount()):
            item = self.root.child(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                types.append({'name': item.text(0), 'suffix': item.text(1)})
        return types

    def item_changed(self, item, column):
        if item.checkState(0) == Qt.CheckState.Checked:
            self.set_children_check_state(item, Qt.CheckState.Checked)
        elif item.checkState(0) == Qt.CheckState.Unchecked:
            self.set_children_check_state(item, Qt.CheckState.Unchecked)

    def set_children_check_state(self, parent, check_state):
        for i in range(parent.childCount()):
            child = parent.child(i)
            child.setCheckState(0, check_state)


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowIcon(QIcon(r".\icon\icon.png"))
        self.setWindowTitle("代码统计工具v1.0")
        self.setupUi()

    def setupUi(self):
        widget = QWidget(self)
        vlayout = QVBoxLayout(widget)
        self.setCentralWidget(widget)

        # 工具栏
        self.tool_bar = QToolBar()
        # self.tool_bar.setIconSize(QSize(25, 25))
        self.addToolBar(self.tool_bar)
        self.act_open_dir = QAction(QIcon(r".\icon\open_dir.png"), "打开文件夹", self)
        self.act_open_file = QAction(QIcon(r".\icon\open_file.png"), "打开文件", self)
        self.act_run = QAction(QIcon(r".\icon\run.png"), "重新统计", self)
        self.tool_bar.addAction(self.act_open_dir)
        self.tool_bar.addAction(self.act_open_file)
        self.tool_bar.addAction(self.act_run)
        self.act_open_dir.triggered.connect(self.open_dir)
        self.act_open_file.triggered.connect(self.open_file)
        self.act_run.triggered.connect(self.run)

        # 左侧区域
        self.dock_type = QDockWidget("类型选择", self)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_type)
        self.dock_type.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.dock_type.setFeatures(QDockWidget.DockWidgetFloatable |
                                   QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.type_select_window = TypeSelectWindow()
        self.dock_type.setWidget(self.type_select_window)

        # 中心区域
        self.tab_widget = QTabWidget(self)
        vlayout.addWidget(self.tab_widget)
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.tab_widget.removeTab)# 关闭最后一个tab软件直接闪退，待修复
        self.tab_widget.currentChanged.connect(self.tab_current_changed)

        # 状态栏
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("欢迎使用代码统计工具")
        self.setStatusBar(self.status_bar)

        self.resize(1200, 800)

    def tab_current_changed(self):
        tree_view = self.tab_widget.currentWidget()
        path = tree_view.model().root_node.path
        self.status_bar.showMessage(path)

    def open_dir(self):
        global SELECT_TYPES
        SELECT_TYPES = self.type_select_window.get_checked_types()
        folder_path = QFileDialog.getExistingDirectory(None, "选择文件夹",
                                                       options=QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)

        if folder_path:
            tree_view = QTreeView()
            tree_model = TreeModel(folder_path)
            tree_view.setModel(tree_model)
            tree_view.setColumnWidth(0, 300)
            for i in range(1, tree_model.columnCount()):
                tree_view.setColumnWidth(i, 100)
            tree_view.expand(tree_model.index(0, 0, QModelIndex()))

            index = self.tab_widget.addTab(tree_view, tree_model.root_node.name)
            self.tab_widget.setCurrentIndex(index)

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(None, "选择文件", "", "All Files (*)")
        if file_path:
            try:
                tree_view = QTreeView()
                tree_model = TreeModel(file_path, True)
                tree_view.setModel(tree_model)
                tree_view.setColumnWidth(0, 300)
                for i in range(1, tree_model.columnCount()):
                    tree_view.setColumnWidth(i, 100)
                tree_view.expand(tree_model.index(0, 0, QModelIndex()))

                index = self.tab_widget.addTab(tree_view, tree_model.root_node.name)
                self.tab_widget.setCurrentIndex(index)
            except Exception as e:
                QMessageBox.warning(self, "错误", str(e))

    def run(self):
        global SELECT_TYPES
        SELECT_TYPES = self.type_select_window.get_checked_types()
        tree_view = self.tab_widget.currentWidget()
        if tree_view:
            root_path = tree_view.model().root_path
            is_file = tree_view.model().is_file
            new_model = TreeModel(root_path, is_file)
            tree_view.setModel(new_model)
            tree_view.expand(new_model.index(0, 0, QModelIndex()))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()
