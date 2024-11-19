import napari
import numpy as np
from magicgui.widgets import create_widget
from napari_guitils.gui_structures import TabSet, VHGroup
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QButtonGroup,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

# Define class colors and values, eventually will be defined by user
INITIAL_SELECTED_CLASS = "intestine"  # Default class
CLASSES = ["epidermis", "intestine", "other", "error"]
CLASS_COLORS = {
    "epidermis": (1, 0, 0, 1),  # Red
    "intestine": (0, 0, 1, 1),  # Blue
    "other": (1, 1, 0, 1),  # Yellow
    "error": (1, 0.5, 0.5, 1),  # Coral Pink
}
CLASS_VALUES = {"epidermis": 0, "intestine": 1, "other": 2, "error": 3}


class PanopticAnnotatorWidget(QWidget):
    """
    Implementation of a napari widget for adding semantic information to instance segmentation.

    Parameters
    ----------
    napari_viewer: napari.Viewer
        main napari viewer
    """

    def __init__(self, napari_viewer, parent=None):
        super().__init__(parent=parent)
        self.viewer = napari_viewer

        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        self.tab_names = ["Annotator", "Files"]
        self.tabs = TabSet(self.tab_names, tab_layouts=[None, None])
        self.main_layout.addWidget(self.tabs)

        self.tabs.widget(0).layout().setAlignment(Qt.AlignTop)

        self.layer_selection_group = VHGroup(
            "Layer selection", orientation="G"
        )

        self.tabs.add_named_tab("Annotator", self.layer_selection_group.gbox)

        # segmentation layer
        self.select_layer_widget = create_widget(
            annotation=napari.layers.Labels, label="Pick segmentation"
        )
        self.select_layer_widget.reset_choices()
        self.viewer.layers.events.inserted.connect(
            self.select_layer_widget.reset_choices
        )
        self.viewer.layers.events.removed.connect(
            self.select_layer_widget.reset_choices
        )
        # annotation layer
        self.select_annotation_layer_widget = create_widget(
            annotation=napari.layers.Points, label="Pick segmentation"
        )
        self.select_annotation_layer_widget.reset_choices()
        self.viewer.layers.events.inserted.connect(
            self.select_annotation_layer_widget.reset_choices
        )
        self.viewer.layers.events.removed.connect(
            self.select_annotation_layer_widget.reset_choices
        )

        self.layer_selection_group.glayout.addWidget(
            QLabel("Segmentation layer"), 0, 0, 1, 1
        )
        self.layer_selection_group.glayout.addWidget(
            self.select_layer_widget.native, 0, 1, 1, 1
        )
        self.layer_selection_group.glayout.addWidget(
            QLabel("Annotation layer"), 1, 0, 1, 1
        )
        self.layer_selection_group.glayout.addWidget(
            self.select_annotation_layer_widget.native, 1, 1, 1, 1
        )

        self.add_annotation_layer_btn = QPushButton("Add annotation layer")
        self.layer_selection_group.glayout.addWidget(
            self.add_annotation_layer_btn, 2, 0, 1, 2
        )

        self.semantic_annotation_group = VHGroup(
            "Semantic annotation", orientation="G"
        )
        self.tabs.add_named_tab(
            "Annotator", self.semantic_annotation_group.gbox
        )

        self.add_connections()
        self.select_layer()

        # Setup radio buttons for class selection
        self.class_buttons = QButtonGroup(
            self
        )  # Using a button group to manage radio buttons
        class_layout = QVBoxLayout()
        for cls in CLASSES:
            btn = QRadioButton(cls)
            btn.toggled.connect(self.on_class_selected)
            self.class_buttons.addButton(btn)
            class_layout.addWidget(btn)
            if cls == INITIAL_SELECTED_CLASS:
                btn.setChecked(True)  # Set default selected class

    def add_connections(self):
        self.select_layer_widget.changed.connect(self.select_layer)
        self.select_annotation_layer_widget.changed.connect(self.select_layer)
        self.add_annotation_layer_btn.clicked.connect(
            self.add_annotation_layer
        )

    def select_layer(self, newtext=None):
        self.selected_layer = self.select_layer_widget.native.currentText()
        self.selected_annotation_layer = (
            self.select_annotation_layer_widget.native.currentText()
        )

        print(f"Selected layer: {self.selected_layer}")
        print(f"Selected annotation layer: {self.selected_annotation_layer}")

    def add_annotation_layer(self):
        if self.selected_layer is None:
            print("No segmentation layer selected")
            return
        if self.selected_annotation_layer is None:
            segmentation_layer = self.viewer.layers[self.selected_layer]
            z_dim = (
                segmentation_layer.data.shape[0]
                if segmentation_layer.ndim == 3
                else None
            )
            initial_data = (
                np.zeros((0, 3)) if z_dim else np.zeros((0, 2))
            )  # Use ternary operator to set initial_data size
            self.annotation_layer = self.viewer.add_points(
                initial_data, name="Annotations", ndim=3 if z_dim else 2
            )
            print(
                f"Annotation layer added with {'3D' if z_dim else '2D'} capabilities."
            )
            self.selected_annotation_layer = self.points_layer.name

    def on_class_selected(self, checked):
        radio_button = self.sender()
        if checked:
            self.selected_class = radio_button.text()
            self.update_point_tool_color()

    def update_point_tool_color(self):
        if self.selected_annotation_layer == "" or self.selected_layer == "":
            print(
                "No annotation layer selected or no segmentation layer selected."
            )
            return

        # Deselect all points
        self.viewer.layers[self.selected_annotation_layer].selected_data = []
        # Set the current face color to the selected class color
        self.viewer.layers[
            self.selected_annotation_layer
        ].current_face_color = self.class_colors[self.selected_class]
        print(
            f"Ready to add points with color {self.class_colors[self.selected_class]} for class {self.selected_class}."
        )
