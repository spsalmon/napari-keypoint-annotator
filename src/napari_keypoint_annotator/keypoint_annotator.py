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
    QListWidget,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

# Define keypoints colors and values, eventually will be defined by user
INITIAL_SELECTED_KEYPOINT = "first_bulb"  # Default class
KEYPOINTS = ["first_bulb", "ismuth", "terminal_bulb"]
KEYPOINT_COLORS = {
    "first_bulb": (1, 0, 0, 1),
    "ismuth": (0, 1, 0, 1),
    "terminal_bulb": (0, 0, 1, 1),
}
KEYPOINT_VALUES = {"first_bulb": 0, "ismuth": 1, "terminal_bulb": 2}


class KeypointAnnotatorWidget(QWidget):
    """
    Implementation of a napari widget for annotating keypoints in 2D.

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

        self.keypoint_annotation_group = VHGroup(
            "Keypoint annotation", orientation="G"
        )
        self.tabs.add_named_tab(
            "Annotator", self.keypoint_annotation_group.gbox
        )

        self.select_layer()

        # Setup radio buttons for keypoint selection
        self.keypoint_buttons = QButtonGroup(
            self
        )  # Using a button group to manage radio buttons
        keypoint_layout = QVBoxLayout()
        for cls in KEYPOINTS:
            btn = QRadioButton(cls)
            btn.toggled.connect(self.on_keypoint_selected)
            self.class_buttons.addButton(btn)
            keypoint_layout.addWidget(btn)
            if cls == INITIAL_SELECTED_KEYPOINT:
                btn.setChecked(True)  # Set default selected keypoint

        self.save_annotations_btn = QPushButton("Save annotations")
        self.load_annotations_btn = QPushButton("Load annotations")

        self.keypoint_annotation_group.glayout.addWidget(
            QLabel("Select keypoint"), 0, 0, 1, 1
        )
        self.keypoint_annotation_group.glayout.addLayout(
            keypoint_layout, 0, 1, 1, 1
        )

        self.keypoint_annotation_group.glayout.addWidget(
            self.save_annotations_btn, 1, 0, 1, 2
        )

        self.keypoint_annotation_group.glayout.addWidget(
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
            "Annotator", self.keypoint_annotation_group.gbox
        )

        self.project_group = VHGroup("Project", orientation="G")
        self.reference_dir_edit, self.reference_dir_button = (
            create_dir_selector(
                self, self.project_group.glayout, "Select reference directory"
            )
        )

        self.project_group.glayout.addWidget(
            self.reference_dir_edit, 1, 0, 1, 1
        )
        self.project_group.glayout.addWidget(
            self.reference_dir_button, 1, 1, 1, 1
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

        self.file_list = QListWidget()
        self.project_group.glayout.addWidget(self.file_list, 6, 0, 1, 2)

        self.next_file_btn = QPushButton("Next file [J]")
        self.previous_file_btn = QPushButton("Previous file [H]")

        self.project_group.glayout.addWidget(
            self.previous_file_btn, 7, 0, 1, 1
        )
        self.project_group.glayout.addWidget(self.next_file_btn, 7, 1, 1, 1)

        self.tabs.add_named_tab("Annotator", self.project_group.gbox)
        self.reference_files = []
        self.annotation_files = []

        self.files_df = pd.DataFrame(
            {
                "Reference": self.reference_files,
                "Annotation": self.annotation_files,
            }
        )

        self.save_annotations_project_btn = QPushButton("Save annotations")
        self.project_group.glayout.addWidget(
            self.save_annotations_project_btn, 8, 0, 1, 2
        )

        self.current_file_idx = 0
        self.reference_layer = None
        self.selected_annotation_layer = ""
        self.keypoint_values = KEYPOINT_VALUES
        self.selected_keypoint = INITIAL_SELECTED_KEYPOINT
        self.keypoint_colors = KEYPOINT_COLORS
        # Map colors to class values using tuples as keys
        self.color_to_keypoint = {
            self.keypoint_colors[cls]: self.keypoint_values[cls]
            for cls in self.keypoint_colors
        }
        self.keypoint_values_to_color = {
            self.keypoint_values[cls]: self.keypoint_colors[cls]
            for cls in self.keypoint_colors
        }
        self.keypoint_values_to_name = {
            self.keypoint_values[cls]: cls for cls in self.keypoint_colors
        }

        self.viewer.bind_key("up", self.cycle_class_up)
        self.viewer.bind_key("down", self.cycle_class_down)

        self.viewer.bind_key("j", self.next_file)
        self.viewer.bind_key("h", self.previous_file)

        self.add_connections()

    def add_connections(self):
        self.select_annotation_layer_widget.changed.connect(self.select_layer)
        self.add_annotation_layer_btn.clicked.connect(
            self.add_annotation_layer
        )
        self.save_annotations_btn.clicked.connect(self.save_annotations)
        self.load_annotations_btn.clicked.connect(self.load_annotations)
        self.load_files_btn.clicked.connect(self.load_files)
        self.file_list.itemClicked.connect(self.choose_file_from_list)
        self.load_annotation_files_btn.clicked.connect(
            self.load_annotation_files
        )

        self.next_file_btn.clicked.connect(self.next_file)
        self.previous_file_btn.clicked.connect(self.previous_file)

        self.save_annotations_project_btn.clicked.connect(
            self.save_annotations_project
        )

    def select_layer(self, newtext=None):
        self.selected_annotation_layer = (
            self.select_annotation_layer_widget.native.currentText()
        )
        print(f"Selected annotation layer: {self.selected_annotation_layer}")

        if self.reference_layer is not None:
            if self.reference_layer.ndim == 3:
                self.axes_order.setText("ZYX")
            else:
                self.axes_order.setText("YX")

    def add_annotation_layer(self):
        if self.reference_layer is None:
            print("No reference layer found")
            return
        if (
            self.selected_annotation_layer == ""
            or self.selected_annotation_layer not in self.viewer.layers
        ):
            reference_layer = self.reference_layer
            z_dim = (
                reference_layer.data.shape[0]
                if reference_layer.ndim == 3
                else None
            )
            initial_data = (
                np.zeros((0, 3)) if z_dim else np.zeros((0, 2))
            )  # Use ternary operator to set initial_data size
            self.annotation_layer = self.viewer.add_points(
                initial_data,
                name="Annotations",
                ndim=3 if z_dim else 2,
                size=2,
            )
            print(
                f"Annotation layer added with {'3D' if z_dim else '2D'} capabilities."
            )
            self.selected_annotation_layer = self.annotation_layer.name

            self.update_point_tool_color()

    def on_class_selected(self, checked):
        radio_button = self.sender()
        if checked:
            self.selected_keypoint = radio_button.text()
            self.update_point_tool_color()

    def update_point_tool_color(self):
        if self.selected_annotation_layer == "":
            return
        # Deselect all points
        self.viewer.layers[self.selected_annotation_layer].selected_data = []
        # Set the current face color to the selected class color
        self.viewer.layers[
            self.selected_annotation_layer
        ].current_face_color = self.keypoint_colors[self.selected_keypoint]
        print(
            f"Ready to add points with color {self.keypoint_colors[self.selected_keypoint]} for class {self.selected_keypoint}."
        )

    def cycle_class_down(self, event):
        current_idx = KEYPOINTS.index(self.selected_keypoint)
        new_idx = current_idx + 1
        if new_idx >= len(KEYPOINTS):
            new_idx = 0

        self.selected_keypoint = KEYPOINTS[new_idx]
        self.update_point_tool_color()

        # Update the radio buttons
        for btn in self.class_buttons.buttons():
            if btn.text() == self.selected_keypoint:
                btn.setChecked(True)

    def cycle_class_up(self, event):
        current_idx = KEYPOINTS.index(self.selected_keypoint)
        new_idx = current_idx - 1
        if new_idx < 0:
            new_idx = len(KEYPOINTS) - 1

        self.selected_keypoint = KEYPOINTS[new_idx]
        self.update_point_tool_color()

        # Update the radio buttons
        for btn in self.class_buttons.buttons():
            if btn.text() == self.selected_keypoint:
                btn.setChecked(True)

    def save_annotations(self):
        annotations_df = self._convert_point_layer_to_df()

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

    def _convert_point_layer_to_df(self):
        if self.selected_annotation_layer == "":
            print("No annotation layer selected")
            return

        annotation_layer = self.viewer.layers[self.selected_annotation_layer]
        annotation_data = annotation_layer.data
        print(f"Saving {annotation_data.shape[0]} annotations")
        # Save the annotations to a file

        print(annotation_data)

        three_dimentional = len(self.axes_order.text()) == 3
        rows = []
        for point, color in zip(annotation_data, annotation_layer.face_color):
            point = tuple(round(p) for p in point)
            keypoint_value = self.color_to_keypoint.get(tuple(color), -1)
            keypoint_name = self.keypoint_values_to_name.get(
                keypoint_value, "unknown"
            )

            if three_dimentional:
                row = {
                    "Name": keypoint_name,
                    "KeypointID": keypoint_value,
                    self.axes_order.text()[0]: point[0],
                    self.axes_order.text()[1]: point[1],
                    self.axes_order.text()[2]: point[2],
                }
            else:
                row = {
                    "Name": keypoint_name,
                    "KeypointID": keypoint_value,
                    self.axes_order.text()[0]: point[0],
                    self.axes_order.text()[1]: point[1],
                }
            rows.append(row)

        return pd.DataFrame(rows)

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
        print(f"Annotations loaded from {file_path}")

        print(annotations_df)

        if self.selected_annotation_layer == "":
            self.add_annotation_layer()
        else:
            # Delete the current annotations layer
            self.viewer.layers.remove(self.selected_annotation_layer)
            self.add_annotation_layer()

        annotation_layer = self.viewer.layers[self.selected_annotation_layer]

        three_dimentional = len(self.axes_order.text()) == 3
        if three_dimentional:
            unique_planes = annotations_df[self.axes_order.text()[0]].unique()
            for plane in unique_planes:
                plane_df = annotations_df[
                    annotations_df[self.axes_order.text()[0]] == plane
                ]
                for _, row in plane_df.iterrows():
                    point = [
                        row[self.axes_order.text()[0]],
                        row[self.axes_order.text()[1]],
                        row[self.axes_order.text()[2]],
                    ]
                    annotation_layer.add(
                        point,
                        face_color=self.keypoint_values_to_color[
                            row["KeypointID"]
                        ],
                    )
        else:
            for _, row in annotations_df.iterrows():
                point = [
                    row[self.axes_order.text()[0]],
                    row[self.axes_order.text()[1]],
                ]
                annotation_layer.add(
                    point,
                    face_color=self.keypoint_values_to_color[
                        row["KeypointID"]
                    ],
                )

        print(f"Loaded {annotations_df.shape[0]} annotations")

    def _load_file(self):
        # clear the current layers
        self.viewer.layers.select_all()
        self.viewer.layers.remove_selected()

        row = self.files_df.iloc[self.current_file_idx]
        reference_file = row["Reference"]
        annotation_file = row["Annotation"]

        self.viewer.open(reference_file)
        if annotation_file != "":
            self._load_annotations(annotation_file)

    def load_files(self):
        reference_dir = self.reference_dir_edit.text()

        if reference_dir == "":
            print("Please select a reference directory")
            return

        reference_files = sorted(
            [os.path.join(reference_dir, f) for f in os.listdir(reference_dir)]
        )

        self.reference_files = reference_files
        self.current_file_idx = 0

        print(self.reference_files)

        rows = []

        for (reference_file,) in self.reference_files:

            row = {
                "Reference": reference_file,
                "Annotation": "",
            }
            rows.append(row)

        self.files_df = pd.DataFrame(rows)

        print(self.files_df)

        # populate the list widget
        self.file_list.clear()
        for _, row in self.files_df.iterrows():
            item = f"{os.path.basename(row['Reference'])}"
            self.file_list.addItem(item)

        self._load_file()

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
            name = os.path.splitext(os.path.basename(annotation_file))[0]
            for i, row in self.files_df.iterrows():
                if name in row["Reference"]:
                    self.files_df.loc[i, "Annotation"] = annotation_file
                    break

        self.files_df["Annotation"] = self.files_df["Annotation"].fillna("")

        print(self.files_df)

        if self.files_df.loc[self.current_file_idx, "Annotation"] != "":
            self._load_annotations(
                self.files_df.loc[self.current_file_idx, "Annotation"]
            )

    def next_file(self, event):
        if self.current_file_idx >= len(self.files_df):
            print("No more files to load")
            return

        self.current_file_idx += 1
        self._load_file()

    def previous_file(self, event):
        if self.current_file_idx <= 0:
            print("No more files to load")
            return

        self.current_file_idx -= 1
        self._load_file()

    def save_annotations_project(self):
        annotations_df = self._convert_point_layer_to_df()

        output_dir = self.annotation_dir_edit.text()
        name = os.path.splitext(
            os.path.basename(self.reference_files[self.current_file_idx])
        )[0]
        output_path = os.path.join(output_dir, f"{name}.csv")
        self.files_df.loc[self.current_file_idx, "Annotation"] = output_path
        annotations_df.to_csv(output_path, index=False)

    def choose_file_from_list(self):
        self.current_file_idx = self.file_list.currentRow()
        self._load_file()
