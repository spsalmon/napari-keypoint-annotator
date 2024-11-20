from pathlib import Path

import napari
import numpy as np
import pandas as pd
from magicgui.widgets import create_widget
from napari_guitils.gui_structures import TabSet, VHGroup
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QLabel,
    QLineEdit,
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
            annotation=napari.layers.Points, label="Pick annotation"
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

        # Let the user define the axes order
        self.axes_order = QLineEdit("")
        self.layer_selection_group.glayout.addWidget(
            QLabel("Axes order"), 3, 0, 1, 1
        )
        self.layer_selection_group.glayout.addWidget(
            self.axes_order, 3, 1, 1, 1
        )

        self.semantic_annotation_group = VHGroup(
            "Semantic annotation", orientation="G"
        )
        self.tabs.add_named_tab(
            "Annotator", self.semantic_annotation_group.gbox
        )

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

        self.save_annotations_btn = QPushButton("Save annotations")

        self.semantic_annotation_group.glayout.addWidget(
            QLabel("Select class"), 0, 0, 1, 1
        )
        self.semantic_annotation_group.glayout.addLayout(
            class_layout, 0, 1, 1, 1
        )

        self.semantic_annotation_group.glayout.addWidget(
            self.save_annotations_btn, 1, 0, 1, 2
        )

        self.class_values = CLASS_VALUES
        self.selected_class = INITIAL_SELECTED_CLASS
        self.class_colors = CLASS_COLORS
        # Map colors to class values using tuples as keys
        self.color_to_class = {
            self.class_colors[cls]: self.class_values[cls]
            for cls in self.class_colors
        }
        self.class_values_to_color = {
            self.class_values[cls]: self.class_colors[cls]
            for cls in self.class_colors
        }
        self.class_values_to_name = {
            self.class_values[cls]: cls for cls in self.class_colors
        }

        # bind the key shortcuts (up and down arrows) to cycle through classes
        self.viewer.bind_key("up", self.cycle_class_up)
        self.viewer.bind_key("down", self.cycle_class_down)

        self.add_connections()

    def add_connections(self):
        self.select_layer_widget.changed.connect(self.select_layer)
        self.select_annotation_layer_widget.changed.connect(self.select_layer)
        self.add_annotation_layer_btn.clicked.connect(
            self.add_annotation_layer
        )
        self.save_annotations_btn.clicked.connect(self.save_annotations)

    def select_layer(self, newtext=None):
        self.selected_layer = self.select_layer_widget.native.currentText()
        self.selected_annotation_layer = (
            self.select_annotation_layer_widget.native.currentText()
        )

        print(f"Selected layer: {self.selected_layer}")
        print(f"Selected annotation layer: {self.selected_annotation_layer}")

        if self.selected_layer != "":
            segmentation_layer = self.viewer.layers[self.selected_layer]
            if segmentation_layer.ndim == 3:
                self.axes_order.setText("ZYX")
            else:
                self.axes_order.setText("YX")

    def add_annotation_layer(self):
        if self.selected_layer == "":
            print("No segmentation layer selected")
            return
        if (
            self.selected_annotation_layer == ""
            or self.selected_annotation_layer not in self.viewer.layers
        ):
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
            self.selected_annotation_layer = self.annotation_layer.name

            self.update_point_tool_color()

    def on_class_selected(self, checked):
        radio_button = self.sender()
        if checked:
            self.selected_class = radio_button.text()
            self.update_point_tool_color()

    def update_point_tool_color(self):
        if self.selected_annotation_layer == "":
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

    def cycle_class_down(self, event):
        current_idx = CLASSES.index(self.selected_class)
        new_idx = current_idx + 1
        if new_idx >= len(CLASSES):
            new_idx = 0

        self.selected_class = CLASSES[new_idx]
        self.update_point_tool_color()

        # Update the radio buttons
        for btn in self.class_buttons.buttons():
            if btn.text() == self.selected_class:
                btn.setChecked(True)

    def cycle_class_up(self, event):
        current_idx = CLASSES.index(self.selected_class)
        new_idx = current_idx - 1
        if new_idx < 0:
            new_idx = len(CLASSES) - 1

        self.selected_class = CLASSES[new_idx]
        self.update_point_tool_color()

        # Update the radio buttons
        for btn in self.class_buttons.buttons():
            if btn.text() == self.selected_class:
                btn.setChecked(True)

    def save_annotations(self):
        if self.selected_annotation_layer == "":
            print("No annotation layer selected")
            return

        segmentation_layer = self.viewer.layers[self.selected_layer]
        annotation_layer = self.viewer.layers[self.selected_annotation_layer]
        annotation_data = annotation_layer.data
        label_data = segmentation_layer.data
        print(f"Saving {annotation_data.shape[0]} annotations")
        # Save the annotations to a file

        print(annotation_data)

        three_dimentional = len(self.axes_order.text()) == 3
        rows = []
        for point, color in zip(annotation_data, annotation_layer.face_color):
            point = tuple(round(p) for p in point)
            label_value = label_data[tuple(point)]
            class_value = self.color_to_class.get(tuple(color), -1)
            class_name = self.class_values_to_name.get(class_value, "unknown")
            print(
                f"Point {point} is in class {class_name} with value {class_value}"
            )

            if three_dimentional:
                row = {
                    self.axes_order.text()[0]: point[0],
                    "Label": label_value,
                    "ClassID": class_value,
                    "Class": class_name,
                }
            else:
                row = {
                    "Label": label_value,
                    "ClassID": class_value,
                    "Class": class_name,
                }
            rows.append(row)

        annotations_df = pd.DataFrame(rows)

        print(annotations_df)

        # open the file explorer to save the file
        dialog = QFileDialog()
        save_file, _ = dialog.getSaveFileName(
            self, "Save annotations", "", "CSV Files (*.csv)"
        )
        save_file = Path(save_file)

        if save_file:
            annotations_df.to_csv(save_file, index=False)
            print(f"Annotations saved to {save_file}")
