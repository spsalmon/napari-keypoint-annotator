import os
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
from skimage.measure import regionprops

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
        self.load_annotations_btn = QPushButton("Load annotations")

        self.semantic_annotation_group.glayout.addWidget(
            QLabel("Select class"), 0, 0, 1, 1
        )
        self.semantic_annotation_group.glayout.addLayout(
            class_layout, 0, 1, 1, 1
        )

        self.semantic_annotation_group.glayout.addWidget(
            self.save_annotations_btn, 1, 0, 1, 2
        )

        self.semantic_annotation_group.glayout.addWidget(
            self.load_annotations_btn, 2, 0, 1, 2
        )

        def create_dir_selector(parent, layout, button_label):
            dir_edit = QLineEdit()
            dir_button = QPushButton(button_label)
            dir_button.clicked.connect(
                lambda: select_directory(parent, dir_edit)
            )
            return dir_edit, dir_button

        def select_directory(parent, dir_edit):
            dir_path = QFileDialog.getExistingDirectory(
                parent, "Select Directory"
            )
            if dir_path:
                dir_edit.setText(dir_path)
                return dir_path
            else:
                print("Directory selection cancelled.")
                return ""

        self.tabs.add_named_tab(
            "Annotator", self.semantic_annotation_group.gbox
        )

        self.project_group = VHGroup("Project", orientation="G")
        self.reference_dir_edit, self.reference_dir_button = (
            create_dir_selector(
                self, self.project_group.glayout, "Select reference directory"
            )
        )
        self.segmentation_dir_edit, self.segmentation_dir_button = (
            create_dir_selector(
                self,
                self.project_group.glayout,
                "Select segmentation directory",
            )
        )

        self.project_group.glayout.addWidget(
            self.reference_dir_edit, 1, 0, 1, 1
        )
        self.project_group.glayout.addWidget(
            self.reference_dir_button, 1, 1, 1, 1
        )

        self.project_group.glayout.addWidget(
            self.segmentation_dir_edit, 2, 0, 1, 1
        )
        self.project_group.glayout.addWidget(
            self.segmentation_dir_button, 2, 1, 1, 1
        )

        self.load_files_btn = QPushButton("Load files")
        self.project_group.glayout.addWidget(self.load_files_btn, 3, 0, 1, 2)

        self.annotation_dir_edit, self.annotation_dir_button = (
            create_dir_selector(
                self, self.project_group.glayout, "Select annotation directory"
            )
        )
        self.project_group.glayout.addWidget(
            self.annotation_dir_edit, 4, 0, 1, 1
        )
        self.project_group.glayout.addWidget(
            self.annotation_dir_button, 4, 1, 1, 1
        )

        self.load_annotation_files_btn = QPushButton("Load annotations")
        self.project_group.glayout.addWidget(
            self.load_annotation_files_btn, 5, 0, 1, 2
        )

        self.tabs.add_named_tab("Annotator", self.project_group.gbox)
        self.reference_files = []
        self.segmentation_files = []
        self.annotation_files = []

        self.files_df = pd.DataFrame(
            {
                "Reference": self.reference_files,
                "Segmentation": self.segmentation_files,
                "Annotation": self.annotation_files,
            }
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
        self.load_annotations_btn.clicked.connect(self.load_annotations)
        self.load_files_btn.clicked.connect(self.load_files)
        self.load_annotation_files_btn.clicked.connect(
            self.load_annotation_files
        )

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

    def load_annotations(self):
        # open the file explorer to load the file
        dialog = QFileDialog()
        load_file, _ = dialog.getOpenFileName(
            self, "Load annotations", "", "CSV Files (*.csv)"
        )
        load_file = Path(load_file)

        if load_file:
            self._load_annotations(load_file)

    def _load_annotations(self, file_path):
        annotations_df = pd.read_csv(file_path)
        annotations_df = pd.read_csv(file_path)
        print(f"Annotations loaded from {file_path}")

        print(annotations_df)

        if self.selected_annotation_layer == "":
            self.add_annotation_layer()
        else:
            # Delete the current annotations layer
            self.viewer.layers.remove(self.selected_annotation_layer)
            self.add_annotation_layer()

        annotation_layer = self.viewer.layers[self.selected_annotation_layer]
        label_data = self.viewer.layers[self.selected_layer].data

        three_dimentional = len(self.axes_order.text()) == 3
        if three_dimentional:
            unique_planes = annotations_df[self.axes_order.text()[0]].unique()
            for plane in unique_planes:
                plane_df = annotations_df[
                    annotations_df[self.axes_order.text()[0]] == plane
                ]
                for _, row in plane_df.iterrows():
                    label, class_value = row["Label"], row["ClassID"]
                    color = self.class_values_to_color.get(class_value)
                    if color is None:
                        print(f"Invalid class value {class_value}")
                        continue
                    mask_of_label = label_data[plane] == label
                    # find the centroid of the mask
                    props = regionprops(mask_of_label.astype(int))[0]
                    centroid = props.centroid
                    point = [plane, centroid[0], centroid[1]]
                    annotation_layer.add(np.array(point))
                    annotation_layer.face_color[-1] = np.array(
                        self.class_values_to_color[class_value]
                    ).astype(float)
        else:
            for _, row in annotations_df.iterrows():
                label, class_value = row["Label"], row["ClassID"]
                color = self.class_values_to_color.get(class_value)
                if color is None:
                    print(f"Invalid class value {class_value}")
                    continue
                mask_of_label = label_data == label
                # find the centroid of the mask
                props = regionprops(mask_of_label.astype(int))[0]
                centroid = props.centroid
                point = [centroid[0], centroid[1]]
                annotation_layer.add(np.array(point))
                annotation_layer.face_color[-1] = np.array(
                    self.class_values_to_color[class_value]
                ).astype(float)

        print(f"Loaded {annotations_df.shape[0]} annotations")

    def load_files(self):
        reference_dir = self.reference_dir_edit.text()
        segmentation_dir = self.segmentation_dir_edit.text()

        if reference_dir == "" or segmentation_dir == "":
            print("Please select both reference and segmentation directories")
            return

        reference_files = sorted(
            [os.path.join(reference_dir, f) for f in os.listdir(reference_dir)]
        )
        segmentation_files = sorted(
            [
                os.path.join(segmentation_dir, f)
                for f in os.listdir(segmentation_dir)
            ]
        )

        print(len(reference_files), len(segmentation_files))

        if len(reference_files) != len(segmentation_files):
            print("Number of reference and segmentation files do not match")
            return

        self.reference_files = reference_files
        self.segmentation_files = segmentation_files

        print(self.reference_files)
        print(self.segmentation_files)

        rows = []

        for (
            reference_file,
            segmentation_file,
        ) in zip(reference_files, segmentation_files):

            row = {
                "Reference": reference_file,
                "Segmentation": segmentation_file,
                "Annotation": "",
            }
            rows.append(row)

        self.files_df = pd.DataFrame(rows)

        print(self.files_df)

        # load the first files in the viewer
        self.viewer.open(reference_files[0])
        # always open the segmentation file as a labels layer with 50% opacity
        self.viewer.open(
            segmentation_files[0], layer_type="labels", opacity=0.5
        )

    def load_annotation_files(self):
        annotation_dir = self.annotation_dir_edit.text()

        if annotation_dir == "":
            print("Please select an annotation directory")
            return

        if self.reference_files == [] or self.segmentation_files == []:
            print("Please load reference and segmentation files first")
            return

        annotation_files = sorted(
            [
                os.path.join(annotation_dir, f)
                for f in os.listdir(annotation_dir)
            ]
        )

        self.annotation_files = annotation_files

        # add the annotation files to the dataframe by matching the names
        for annotation_file in annotation_files:
            name = os.path.splittext(os.path.basename(annotation_file))[0]
            for i, row in self.files_df.iterrows():
                if name in row["Reference"]:
                    self.files_df.loc[i, "Annotation"] = annotation_file
                    break

        self.files_df["Annotation"] = self.files_df["Annotation"].fillna("")

        print(self.files_df)
